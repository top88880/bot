"""Earnings service for agent profit tracking and withdrawals.

This module manages the agent ledger, profit maturity, and withdrawal lifecycle.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from decimal import Decimal
from models.constants import (
    LEDGER_STATUS_PENDING, LEDGER_STATUS_MATURED, LEDGER_STATUS_WITHDRAWN,
    LEDGER_STATUS_REVERTED, LEDGER_TYPE_SALE, LEDGER_TYPE_REFUND,
    WITHDRAWAL_STATUS_REQUESTED, WITHDRAWAL_STATUS_APPROVED,
    WITHDRAWAL_STATUS_PAID, WITHDRAWAL_STATUS_REJECTED,
    PROFIT_MATURITY_HOURS
)


def add_profit_on_order(
    ledger_collection,
    agent_id: str,
    order_doc: Dict,
    base_price: float,
    agent_price: float,
    qty: int
) -> Optional[Dict]:
    """Record profit when an order is completed.
    
    Args:
        ledger_collection: MongoDB collection for agent ledger.
        agent_id: Agent identifier.
        order_doc: Order document.
        base_price: Base product price.
        agent_price: Final agent price (after markup).
        qty: Quantity purchased.
    
    Returns:
        Dict: Ledger entry document, or None on error.
    """
    try:
        # Calculate profit per item and total profit
        profit_per_item = Decimal(str(agent_price)) - Decimal(str(base_price))
        total_profit = profit_per_item * Decimal(str(qty))
        total_profit = float(total_profit.quantize(Decimal('0.01')))
        
        # Calculate maturity time
        now = datetime.now()
        mature_at = now + timedelta(hours=PROFIT_MATURITY_HOURS)
        
        ledger_entry = {
            'agent_id': agent_id,
            'order_id': order_doc.get('bianhao'),
            'user_id': order_doc.get('user_id'),
            'type': LEDGER_TYPE_SALE,
            'status': LEDGER_STATUS_PENDING,
            'base_price': base_price,
            'agent_price': agent_price,
            'markup_per_item': float(profit_per_item.quantize(Decimal('0.01'))),
            'qty': qty,
            'profit': total_profit,
            'created_at': now,
            'mature_at': mature_at,
            'matured_at': None,
            'withdrawn_at': None,
            'reverted': False,
            'revert_reason': None
        }
        
        result = ledger_collection.insert_one(ledger_entry)
        ledger_entry['_id'] = result.inserted_id
        
        logging.info(
            f"Added profit ledger entry for agent {agent_id}: "
            f"profit={total_profit}, order={order_doc.get('bianhao')}"
        )
        return ledger_entry
        
    except Exception as e:
        logging.error(f"Error adding profit to ledger: {e}")
        return None


def add_refund_entry(
    ledger_collection,
    agent_id: str,
    original_ledger_id,
    refund_reason: str = None
) -> bool:
    """Add a refund entry and mark original as reverted.
    
    Args:
        ledger_collection: MongoDB collection for agent ledger.
        agent_id: Agent identifier.
        original_ledger_id: ID of the original ledger entry to revert.
        refund_reason: Optional reason for refund.
    
    Returns:
        bool: True if successful.
    """
    try:
        # Get the original entry
        original = ledger_collection.find_one({'_id': original_ledger_id})
        if not original or original.get('agent_id') != agent_id:
            logging.error(f"Original ledger entry not found or wrong agent")
            return False
        
        if original.get('reverted'):
            logging.warning(f"Ledger entry already reverted: {original_ledger_id}")
            return False
        
        # Mark original as reverted
        ledger_collection.update_one(
            {'_id': original_ledger_id},
            {
                '$set': {
                    'reverted': True,
                    'revert_reason': refund_reason,
                    'reverted_at': datetime.now()
                }
            }
        )
        
        # Create negative ledger entry for refund
        refund_entry = {
            'agent_id': agent_id,
            'order_id': original.get('order_id'),
            'user_id': original.get('user_id'),
            'type': LEDGER_TYPE_REFUND,
            'status': LEDGER_STATUS_REVERTED,
            'base_price': original.get('base_price'),
            'agent_price': original.get('agent_price'),
            'markup_per_item': original.get('markup_per_item'),
            'qty': original.get('qty'),
            'profit': -original.get('profit'),  # Negative profit
            'created_at': datetime.now(),
            'mature_at': None,
            'matured_at': None,
            'withdrawn_at': None,
            'reverted': False,
            'original_ledger_id': original_ledger_id,
            'revert_reason': refund_reason
        }
        
        ledger_collection.insert_one(refund_entry)
        
        logging.info(
            f"Added refund entry for agent {agent_id}, "
            f"original={original_ledger_id}"
        )
        return True
        
    except Exception as e:
        logging.error(f"Error adding refund entry: {e}")
        return False


def mature_ledger_entries(ledger_collection) -> int:
    """Mature pending ledger entries that have passed their maturity time.
    
    This should be called periodically by a scheduled job.
    
    Args:
        ledger_collection: MongoDB collection for agent ledger.
    
    Returns:
        int: Number of entries matured.
    """
    try:
        now = datetime.now()
        
        result = ledger_collection.update_many(
            {
                'status': LEDGER_STATUS_PENDING,
                'mature_at': {'$lte': now},
                'reverted': False
            },
            {
                '$set': {
                    'status': LEDGER_STATUS_MATURED,
                    'matured_at': now
                }
            }
        )
        
        count = result.modified_count
        if count > 0:
            logging.info(f"Matured {count} ledger entries")
        
        return count
        
    except Exception as e:
        logging.error(f"Error maturing ledger entries: {e}")
        return 0


def get_agent_balance(ledger_collection, agent_id: str) -> Dict[str, float]:
    """Get agent balance summary.
    
    Args:
        ledger_collection: MongoDB collection for agent ledger.
        agent_id: Agent identifier.
    
    Returns:
        Dict with 'pending', 'available', and 'withdrawn' balances.
    """
    try:
        pipeline = [
            {'$match': {'agent_id': agent_id}},
            {
                '$group': {
                    '_id': '$status',
                    'total': {'$sum': '$profit'}
                }
            }
        ]
        
        results = list(ledger_collection.aggregate(pipeline))
        
        balances = {
            'pending': 0.0,
            'available': 0.0,
            'withdrawn': 0.0,
            'total_earned': 0.0
        }
        
        for r in results:
            status = r['_id']
            amount = float(r['total'])
            
            if status == LEDGER_STATUS_PENDING:
                balances['pending'] = amount
            elif status == LEDGER_STATUS_MATURED:
                balances['available'] = amount
            elif status == LEDGER_STATUS_WITHDRAWN:
                balances['withdrawn'] = amount
        
        balances['total_earned'] = (
            balances['pending'] + 
            balances['available'] + 
            balances['withdrawn']
        )
        
        return balances
        
    except Exception as e:
        logging.error(f"Error getting agent balance: {e}")
        return {
            'pending': 0.0,
            'available': 0.0,
            'withdrawn': 0.0,
            'total_earned': 0.0
        }


def request_withdrawal(
    withdrawals_collection,
    ledger_collection,
    agent_id: str,
    amount: float,
    wallet_address: str
) -> Optional[Dict]:
    """Request a withdrawal.
    
    Args:
        withdrawals_collection: MongoDB collection for withdrawals.
        ledger_collection: MongoDB collection for agent ledger.
        agent_id: Agent identifier.
        amount: Amount to withdraw.
        wallet_address: Payout wallet address.
    
    Returns:
        Dict: Withdrawal document, or None if insufficient balance.
    """
    try:
        # Check available balance
        balances = get_agent_balance(ledger_collection, agent_id)
        available = balances['available']
        
        if amount > available:
            logging.warning(
                f"Insufficient balance for withdrawal: "
                f"requested={amount}, available={available}"
            )
            return None
        
        # Create withdrawal request
        withdrawal_doc = {
            'agent_id': agent_id,
            'amount': amount,
            'wallet_address': wallet_address,
            'status': WITHDRAWAL_STATUS_REQUESTED,
            'requested_at': datetime.now(),
            'approved_at': None,
            'paid_at': None,
            'rejected_at': None,
            'txid': None,
            'admin_note': None
        }
        
        result = withdrawals_collection.insert_one(withdrawal_doc)
        withdrawal_doc['_id'] = result.inserted_id
        
        logging.info(
            f"Created withdrawal request for agent {agent_id}: "
            f"amount={amount}, wallet={wallet_address}"
        )
        return withdrawal_doc
        
    except Exception as e:
        logging.error(f"Error requesting withdrawal: {e}")
        return None


def approve_withdrawal(
    withdrawals_collection,
    withdrawal_id,
    admin_id: int
) -> bool:
    """Approve a withdrawal request.
    
    Args:
        withdrawals_collection: MongoDB collection for withdrawals.
        withdrawal_id: Withdrawal document ID.
        admin_id: Admin user ID approving the withdrawal.
    
    Returns:
        bool: True if successful.
    """
    try:
        result = withdrawals_collection.update_one(
            {'_id': withdrawal_id, 'status': WITHDRAWAL_STATUS_REQUESTED},
            {
                '$set': {
                    'status': WITHDRAWAL_STATUS_APPROVED,
                    'approved_at': datetime.now(),
                    'approved_by_admin_id': admin_id
                }
            }
        )
        
        if result.modified_count > 0:
            logging.info(f"Approved withdrawal {withdrawal_id}")
            return True
        return False
        
    except Exception as e:
        logging.error(f"Error approving withdrawal: {e}")
        return False


def mark_withdrawal_paid(
    withdrawals_collection,
    ledger_collection,
    withdrawal_id,
    txid: str,
    admin_id: int
) -> bool:
    """Mark a withdrawal as paid and update ledger.
    
    Args:
        withdrawals_collection: MongoDB collection for withdrawals.
        ledger_collection: MongoDB collection for agent ledger.
        withdrawal_id: Withdrawal document ID.
        txid: Transaction ID of the payment.
        admin_id: Admin user ID marking as paid.
    
    Returns:
        bool: True if successful.
    """
    try:
        # Get the withdrawal
        withdrawal = withdrawals_collection.find_one({'_id': withdrawal_id})
        if not withdrawal:
            logging.error(f"Withdrawal not found: {withdrawal_id}")
            return False
        
        if withdrawal.get('status') != WITHDRAWAL_STATUS_APPROVED:
            logging.error(
                f"Withdrawal not approved: {withdrawal_id}, "
                f"status={withdrawal.get('status')}"
            )
            return False
        
        agent_id = withdrawal['agent_id']
        amount = withdrawal['amount']
        
        # Mark matured ledger entries as withdrawn up to the amount
        now = datetime.now()
        
        # Get matured entries oldest first
        matured_entries = list(ledger_collection.find({
            'agent_id': agent_id,
            'status': LEDGER_STATUS_MATURED,
            'reverted': False
        }).sort('mature_at', 1))
        
        remaining = Decimal(str(amount))
        updated_count = 0
        
        for entry in matured_entries:
            if remaining <= 0:
                break
            
            profit = Decimal(str(entry['profit']))
            
            if profit <= remaining:
                # Mark entire entry as withdrawn
                ledger_collection.update_one(
                    {'_id': entry['_id']},
                    {
                        '$set': {
                            'status': LEDGER_STATUS_WITHDRAWN,
                            'withdrawn_at': now,
                            'withdrawal_id': withdrawal_id
                        }
                    }
                )
                remaining -= profit
                updated_count += 1
            else:
                # This shouldn't happen with proper balance checking
                logging.warning(
                    f"Partial withdrawal not implemented, "
                    f"skipping entry {entry['_id']}"
                )
                break
        
        # Update withdrawal status
        withdrawals_collection.update_one(
            {'_id': withdrawal_id},
            {
                '$set': {
                    'status': WITHDRAWAL_STATUS_PAID,
                    'paid_at': now,
                    'paid_by_admin_id': admin_id,
                    'txid': txid
                }
            }
        )
        
        logging.info(
            f"Marked withdrawal {withdrawal_id} as paid, "
            f"updated {updated_count} ledger entries, txid={txid}"
        )
        return True
        
    except Exception as e:
        logging.error(f"Error marking withdrawal as paid: {e}")
        return False


def reject_withdrawal(
    withdrawals_collection,
    withdrawal_id,
    admin_id: int,
    reason: str = None
) -> bool:
    """Reject a withdrawal request.
    
    Args:
        withdrawals_collection: MongoDB collection for withdrawals.
        withdrawal_id: Withdrawal document ID.
        admin_id: Admin user ID rejecting the withdrawal.
        reason: Optional rejection reason.
    
    Returns:
        bool: True if successful.
    """
    try:
        result = withdrawals_collection.update_one(
            {'_id': withdrawal_id, 'status': WITHDRAWAL_STATUS_REQUESTED},
            {
                '$set': {
                    'status': WITHDRAWAL_STATUS_REJECTED,
                    'rejected_at': datetime.now(),
                    'rejected_by_admin_id': admin_id,
                    'admin_note': reason
                }
            }
        )
        
        if result.modified_count > 0:
            logging.info(f"Rejected withdrawal {withdrawal_id}")
            return True
        return False
        
    except Exception as e:
        logging.error(f"Error rejecting withdrawal: {e}")
        return False


def list_withdrawals(
    withdrawals_collection,
    agent_id: str = None,
    status: str = None
) -> List[Dict]:
    """List withdrawal requests.
    
    Args:
        withdrawals_collection: MongoDB collection for withdrawals.
        agent_id: Optional filter by agent ID.
        status: Optional filter by status.
    
    Returns:
        List[Dict]: List of withdrawal documents.
    """
    try:
        query = {}
        if agent_id:
            query['agent_id'] = agent_id
        if status:
            query['status'] = status
        
        return list(withdrawals_collection.find(query).sort('requested_at', -1))
        
    except Exception as e:
        logging.error(f"Error listing withdrawals: {e}")
        return []
