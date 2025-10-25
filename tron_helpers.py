"""TRON blockchain helper functions for TRC20 USDT payment processing.

This module provides utilities for:
- Address normalization (Base58 and hex format)
- Decimal comparison with precision
- Confirmation checks
- Event matching to pending orders
- Idempotent crediting by TXID
"""

import os
import logging
import time
from decimal import Decimal, InvalidOperation
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta

import requests
from tronpy import Tron
from tronpy.providers import HTTPProvider
from tronpy.exceptions import TronError, BadAddress

# TRON configuration
USDT_CONTRACT = os.getenv('USDT_CONTRACT', 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t')
TRON_MIN_CONFIRMATIONS = int(os.getenv('TRON_MIN_CONFIRMATIONS', '2'))
TRONGRID_API_KEY = os.getenv('TRONGRID_API_KEY', '')

# Decimal precision for USDT (6 decimals)
USDT_DECIMALS = 6
USDT_UNIT = Decimal(10 ** USDT_DECIMALS)

# Amount tolerance for matching (1e-6 = 0.000001 USDT)
AMOUNT_TOLERANCE = Decimal('0.000001')


def get_tron_client():
    """Get TRON client with API key if configured."""
    if TRONGRID_API_KEY:
        return Tron(HTTPProvider(api_key=TRONGRID_API_KEY))
    return Tron()


def normalize_address_to_base58(address: str) -> Optional[str]:
    """Normalize address to Base58 format (T...).
    
    Args:
        address: Address in Base58 (T...) or hex (41...) format
    
    Returns:
        Base58 address or None if invalid
    """
    if not address:
        return None
    
    address = address.strip()
    
    # Already in Base58 format
    if address.startswith('T') and len(address) == 34:
        return address
    
    # Hex format (41... or 0x41...)
    if address.startswith('0x'):
        address = address[2:]
    
    if address.startswith('41') and len(address) == 42:
        try:
            client = get_tron_client()
            return client.to_base58check_address(address)
        except (BadAddress, Exception) as e:
            logging.warning(f"Failed to convert address {address}: {e}")
            return None
    
    logging.warning(f"Invalid address format: {address}")
    return None


def amount_from_sun(sun_amount: int) -> Decimal:
    """Convert sun (smallest USDT unit) to USDT with proper decimal handling.
    
    Args:
        sun_amount: Amount in sun (1 USDT = 1,000,000 sun)
    
    Returns:
        Decimal amount in USDT
    """
    try:
        return Decimal(sun_amount) / USDT_UNIT
    except (InvalidOperation, Exception) as e:
        logging.error(f"Failed to convert sun amount {sun_amount}: {e}")
        return Decimal('0')


def amounts_match(amount1: Decimal, amount2: Decimal, tolerance: Decimal = AMOUNT_TOLERANCE) -> bool:
    """Check if two amounts match within tolerance.
    
    Args:
        amount1: First amount
        amount2: Second amount
        tolerance: Maximum allowed difference
    
    Returns:
        True if amounts match within tolerance
    """
    try:
        diff = abs(Decimal(amount1) - Decimal(amount2))
        return diff <= tolerance
    except (InvalidOperation, Exception) as e:
        logging.error(f"Failed to compare amounts {amount1} and {amount2}: {e}")
        return False


def get_transaction_confirmations(txid: str) -> Optional[int]:
    """Get number of confirmations for a transaction.
    
    Args:
        txid: Transaction ID
    
    Returns:
        Number of confirmations or None if not found/error
    """
    try:
        client = get_tron_client()
        
        # Get transaction info
        tx_info = client.get_transaction_info(txid)
        if not tx_info or 'blockNumber' not in tx_info:
            logging.warning(f"Transaction {txid} not found or not confirmed")
            return 0
        
        tx_block = tx_info['blockNumber']
        
        # Get latest block
        latest_block = client.get_latest_block_number()
        
        confirmations = latest_block - tx_block + 1
        return confirmations
        
    except TronError as e:
        logging.error(f"TronError getting confirmations for {txid}: {e}")
        return None
    except Exception as e:
        logging.error(f"Error getting confirmations for {txid}: {e}")
        return None


def get_trc20_transfers_by_address(
    address: str,
    start_timestamp: int,
    end_timestamp: int,
    only_to: bool = True,
    max_retries: int = 3
) -> List[Dict]:
    """Get TRC20 USDT transfers for an address using TronGrid API.
    
    Args:
        address: Wallet address (Base58 format)
        start_timestamp: Start time in milliseconds
        end_timestamp: End time in milliseconds
        only_to: If True, only get transfers where address is recipient
        max_retries: Maximum number of retries on failure
    
    Returns:
        List of transfer events
    """
    transfers = []
    
    # Normalize address
    address = normalize_address_to_base58(address)
    if not address:
        logging.error(f"Invalid address format")
        return transfers
    
    # TronGrid API endpoint
    base_url = "https://api.trongrid.io"
    if TRONGRID_API_KEY:
        base_url = f"{base_url}?TRON-PRO-API-KEY={TRONGRID_API_KEY}"
    
    endpoint = f"{base_url}/v1/accounts/{address}/transactions/trc20"
    
    params = {
        'contract_address': USDT_CONTRACT,
        'only_to': 'true' if only_to else 'false',
        'min_timestamp': start_timestamp,
        'max_timestamp': end_timestamp,
        'limit': 200
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(endpoint, params=params, timeout=10)
            
            if response.status_code == 429:
                # Rate limited
                retry_after = int(response.headers.get('Retry-After', 5))
                logging.warning(f"Rate limited, waiting {retry_after}s...")
                time.sleep(retry_after)
                continue
            
            if response.status_code != 200:
                logging.error(f"TronGrid API error: {response.status_code} - {response.text}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return transfers
            
            data = response.json()
            
            if 'data' in data:
                for tx in data['data']:
                    # Parse transfer event
                    try:
                        transfer = {
                            'txid': tx['transaction_id'],
                            'from_address': tx['from'],
                            'to_address': tx['to'],
                            'value_sun': int(tx['value']),
                            'value_usdt': amount_from_sun(int(tx['value'])),
                            'block_timestamp': tx['block_timestamp'],
                            'contract_address': tx.get('token_info', {}).get('address', '')
                        }
                        transfers.append(transfer)
                    except (KeyError, ValueError) as e:
                        logging.warning(f"Failed to parse transfer: {e}")
                        continue
            
            return transfers
            
        except requests.RequestException as e:
            logging.error(f"Request error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return transfers
        except Exception as e:
            logging.error(f"Unexpected error getting transfers: {e}")
            return transfers
    
    return transfers


def validate_trc20_transfer(
    transfer: Dict,
    expected_address: str,
    expected_amount: Decimal,
    min_confirmations: int = TRON_MIN_CONFIRMATIONS
) -> Tuple[bool, str]:
    """Validate a TRC20 transfer against expected criteria.
    
    Args:
        transfer: Transfer data dict
        expected_address: Expected recipient address
        expected_amount: Expected transfer amount
        min_confirmations: Minimum required confirmations
    
    Returns:
        Tuple of (is_valid, reason)
    """
    # Check contract address
    if transfer.get('contract_address') != USDT_CONTRACT:
        return False, f"Wrong contract: {transfer.get('contract_address')}"
    
    # Normalize and check recipient address
    to_address = normalize_address_to_base58(transfer.get('to_address', ''))
    expected_address = normalize_address_to_base58(expected_address)
    
    if not to_address or not expected_address:
        return False, "Invalid address format"
    
    if to_address != expected_address:
        return False, f"Wrong recipient: {to_address} != {expected_address}"
    
    # Check amount
    transfer_amount = transfer.get('value_usdt', Decimal('0'))
    if not amounts_match(transfer_amount, expected_amount):
        return False, f"Amount mismatch: {transfer_amount} != {expected_amount}"
    
    # Check confirmations
    txid = transfer.get('txid')
    if not txid:
        return False, "Missing TXID"
    
    confirmations = get_transaction_confirmations(txid)
    if confirmations is None:
        return False, "Failed to get confirmations"
    
    if confirmations < min_confirmations:
        return False, f"Insufficient confirmations: {confirmations} < {min_confirmations}"
    
    return True, "Valid"


def format_usdt_amount(amount: Decimal) -> str:
    """Format USDT amount for display.
    
    Args:
        amount: USDT amount as Decimal
    
    Returns:
        Formatted string with 6 decimal places
    """
    try:
        return str(Decimal(amount).quantize(Decimal('0.000001')))
    except (InvalidOperation, Exception):
        return "0.000000"
