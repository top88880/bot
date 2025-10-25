"""TRC20 USDT payment processor for auto-crediting orders.

This module handles:
- Matching TRC20 transfers to pending topup orders
- Idempotent crediting by TXID
- Backfill/rescan of missed payments
- Admin rescan tools
"""

import os
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from mongo import topup, user, qukuai
from tron_helpers import (
    normalize_address_to_base58,
    amount_from_sun,
    amounts_match,
    get_transaction_confirmations,
    get_trc20_transfers_by_address,
    validate_trc20_transfer,
    format_usdt_amount,
    TRON_MIN_CONFIRMATIONS,
    USDT_CONTRACT
)


class TRC20PaymentProcessor:
    """Processor for TRC20 USDT payments."""
    
    def __init__(self):
        self.min_confirmations = TRON_MIN_CONFIRMATIONS
        self.usdt_contract = USDT_CONTRACT
    
    def find_pending_orders_by_address(self, address: str) -> List[Dict]:
        """Find pending topup orders for a specific address.
        
        Args:
            address: Payment address (Base58 format)
        
        Returns:
            List of pending order documents
        """
        try:
            # Normalize address
            address = normalize_address_to_base58(address)
            if not address:
                return []
            
            # Find pending USDT topup orders
            # Orders expire after a certain time (e.g., 30 minutes)
            # We look for orders with status='pending' and cz_type='usdt'
            
            orders = list(topup.find({
                'status': 'pending',
                'cz_type': 'usdt',
                # Note: address field might be stored in various ways
                # We'll need to check the actual schema
            }))
            
            return orders
            
        except Exception as e:
            logging.error(f"Error finding pending orders for {address}: {e}")
            return []
    
    def find_order_by_amount_and_time(
        self,
        amount: Decimal,
        timestamp_ms: int,
        time_window_minutes: int = 60
    ) -> Optional[Dict]:
        """Find pending order by amount and time window.
        
        Args:
            amount: Payment amount in USDT
            timestamp_ms: Payment timestamp in milliseconds
            time_window_minutes: Time window for matching (before and after)
        
        Returns:
            Matching order document or None
        """
        try:
            # Convert timestamp to datetime
            payment_time = datetime.fromtimestamp(timestamp_ms / 1000)
            
            # Define time window
            time_start = payment_time - timedelta(minutes=time_window_minutes)
            time_end = payment_time + timedelta(minutes=time_window_minutes)
            
            # Find orders with matching amount in time window
            orders = list(topup.find({
                'status': 'pending',
                'cz_type': 'usdt',
                'time': {
                    '$gte': time_start,
                    '$lte': time_end
                }
            }))
            
            # Match by amount (within tolerance)
            for order in orders:
                order_amount = Decimal(str(order.get('money', 0)))
                if amounts_match(amount, order_amount):
                    return order
            
            return None
            
        except Exception as e:
            logging.error(f"Error finding order by amount and time: {e}")
            return None
    
    def is_already_credited(self, txid: str) -> bool:
        """Check if a transaction has already been credited.
        
        Args:
            txid: Transaction ID
        
        Returns:
            True if already credited
        """
        try:
            # Check if TXID exists in credited orders
            credited = topup.find_one({
                'txid': txid,
                'status': 'completed'
            })
            return credited is not None
        except Exception as e:
            logging.error(f"Error checking if credited {txid}: {e}")
            return False
    
    def credit_order(self, order: Dict, txid: str, transfer_amount: Decimal) -> bool:
        """Credit a topup order and update user balance.
        
        Args:
            order: Order document from topup collection
            txid: Transaction ID for idempotency
            transfer_amount: Actual transfer amount received
        
        Returns:
            True if credited successfully
        """
        try:
            # Check if already credited
            if self.is_already_credited(txid):
                logging.info(f"Order {order.get('bianhao')} already credited with TXID {txid}")
                return True
            
            user_id = order.get('user_id')
            order_amount = Decimal(str(order.get('money', 0)))
            usdt_amount = Decimal(str(order.get('usdt', 0)))
            
            # Update order status and add TXID
            topup.update_one(
                {'_id': order['_id']},
                {
                    '$set': {
                        'status': 'completed',
                        'txid': txid,
                        'credited_at': datetime.now(),
                        'credited_amount': str(transfer_amount)
                    }
                }
            )
            
            # Update user balance
            user.update_one(
                {'user_id': user_id},
                {'$inc': {'USDT': float(usdt_amount)}}
            )
            
            logging.info(
                f"✅ Credited order {order.get('bianhao')}: "
                f"user={user_id}, amount={format_usdt_amount(usdt_amount)} USDT, "
                f"txid={txid}"
            )
            
            # TODO: Send notification to user
            # This would require bot context which we don't have here
            # Consider adding to a notification queue or handling elsewhere
            
            return True
            
        except Exception as e:
            logging.error(f"❌ Failed to credit order {order.get('bianhao')}: {e}")
            return False
    
    def process_transaction_from_qukuai(self, tx_doc: Dict) -> bool:
        """Process a transaction from qukuai collection.
        
        Args:
            tx_doc: Transaction document from qukuai collection
        
        Returns:
            True if processed (credited or skipped with reason)
        """
        try:
            txid = tx_doc.get('txid')
            to_address = tx_doc.get('to_address')
            value_sun = tx_doc.get('quant', 0)
            block_number = tx_doc.get('number')
            tx_type = tx_doc.get('type')
            
            # Skip if not USDT
            if tx_type != 'USDT':
                logging.debug(f"Skipping non-USDT transaction {txid}")
                return False
            
            # Convert amount
            transfer_amount = amount_from_sun(value_sun)
            
            logging.info(
                f"Processing transaction: txid={txid}, "
                f"to={to_address}, amount={format_usdt_amount(transfer_amount)}"
            )
            
            # Check if already credited
            if self.is_already_credited(txid):
                logging.debug(f"Transaction {txid} already credited")
                return True
            
            # Check confirmations
            confirmations = get_transaction_confirmations(txid)
            if confirmations is None:
                logging.warning(f"Failed to get confirmations for {txid}")
                return False
            
            if confirmations < self.min_confirmations:
                logging.info(
                    f"Insufficient confirmations for {txid}: "
                    f"{confirmations}/{self.min_confirmations}"
                )
                return False
            
            # Try to find matching order by amount and time
            timestamp_ms = tx_doc.get('time', int(datetime.now().timestamp() * 1000))
            order = self.find_order_by_amount_and_time(transfer_amount, timestamp_ms)
            
            if not order:
                logging.warning(
                    f"No matching order found for txid={txid}, "
                    f"amount={format_usdt_amount(transfer_amount)}"
                )
                return False
            
            # Credit the order
            success = self.credit_order(order, txid, transfer_amount)
            
            if success:
                # Mark transaction as processed in qukuai
                qukuai.update_one(
                    {'_id': tx_doc['_id']},
                    {'$set': {'state': 1, 'processed_at': datetime.now()}}
                )
            
            return success
            
        except Exception as e:
            logging.error(f"Error processing transaction from qukuai: {e}")
            return False
    
    def scan_pending_orders(self) -> Dict:
        """Scan all pending orders and try to match with blockchain transfers.
        
        Returns:
            Summary dict with processing results
        """
        summary = {
            'total': 0,
            'credited': 0,
            'pending': 0,
            'expired': 0,
            'failed': 0
        }
        
        try:
            # Find all pending USDT orders
            orders = list(topup.find({
                'status': 'pending',
                'cz_type': 'usdt'
            }))
            
            summary['total'] = len(orders)
            
            for order in orders:
                try:
                    # Check if expired
                    expire_time = order.get('expire_time')
                    if expire_time:
                        expire_dt = datetime.strptime(expire_time, '%Y-%m-%d %H:%M:%S')
                        if datetime.now() > expire_dt:
                            summary['expired'] += 1
                            # Mark as expired
                            topup.update_one(
                                {'_id': order['_id']},
                                {'$set': {'status': 'expired'}}
                            )
                            continue
                    
                    # TODO: Get payment address for this order
                    # The current schema doesn't seem to store the payment address
                    # We would need to either:
                    # 1. Add address field to order when created
                    # 2. Match by amount and time window
                    
                    # For now, we rely on matching by amount and time
                    # which is done when processing qukuai transactions
                    
                    summary['pending'] += 1
                    
                except Exception as e:
                    logging.error(f"Error processing order {order.get('bianhao')}: {e}")
                    summary['failed'] += 1
            
            return summary
            
        except Exception as e:
            logging.error(f"Error scanning pending orders: {e}")
            return summary
    
    def rescan_by_txid(self, txid: str) -> Tuple[bool, str]:
        """Rescan and force-match a specific transaction.
        
        Args:
            txid: Transaction ID to rescan
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Check if already credited
            if self.is_already_credited(txid):
                return True, f"Transaction {txid} already credited"
            
            # Look for transaction in qukuai
            tx_doc = qukuai.find_one({'txid': txid})
            if not tx_doc:
                return False, f"Transaction {txid} not found in database"
            
            # Process it
            success = self.process_transaction_from_qukuai(tx_doc)
            
            if success:
                return True, f"Successfully credited transaction {txid}"
            else:
                return False, f"Failed to credit transaction {txid}"
            
        except Exception as e:
            logging.error(f"Error rescanning txid {txid}: {e}")
            return False, f"Error: {str(e)}"
    
    def rescan_by_order(self, order_id: str) -> Tuple[bool, str]:
        """Rescan and try to find payment for a specific order.
        
        Args:
            order_id: Order bianhao (order number)
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Find the order
            order = topup.find_one({'bianhao': order_id})
            if not order:
                return False, f"Order {order_id} not found"
            
            # Check if already completed
            if order.get('status') == 'completed':
                return True, f"Order {order_id} already completed"
            
            order_amount = Decimal(str(order.get('money', 0)))
            order_time = order.get('time')
            
            if not order_time:
                return False, "Order has no timestamp"
            
            # Search for matching transactions in a wide time window (±2 hours)
            timestamp_ms = int(order_time.timestamp() * 1000)
            
            # Look in qukuai for matching transactions
            time_start = order_time - timedelta(hours=2)
            time_end = order_time + timedelta(hours=2)
            
            transactions = list(qukuai.find({
                'type': 'USDT',
                'time': {
                    '$gte': int(time_start.timestamp() * 1000),
                    '$lte': int(time_end.timestamp() * 1000)
                }
            }))
            
            # Try to match by amount
            for tx_doc in transactions:
                tx_amount = amount_from_sun(tx_doc.get('quant', 0))
                if amounts_match(tx_amount, order_amount):
                    # Found a match, try to credit
                    success = self.process_transaction_from_qukuai(tx_doc)
                    if success:
                        return True, f"Successfully matched and credited order {order_id}"
            
            return False, f"No matching payment found for order {order_id}"
            
        except Exception as e:
            logging.error(f"Error rescanning order {order_id}: {e}")
            return False, f"Error: {str(e)}"


# Global processor instance
payment_processor = TRC20PaymentProcessor()
