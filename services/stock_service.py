"""Stock service for atomic inventory management.

This module provides atomic operations for stock reservation and rollback
to prevent overselling across multiple concurrent bot instances.
"""

import logging
from typing import List, Dict, Optional
from models.constants import STATE_AVAILABLE, STATE_SOLD


def reserve_stock(hb_collection, nowuid: str, user_id: int, count: int) -> Optional[List[Dict]]:
    """Atomically reserve stock for an order.
    
    This uses find_one_and_update in a loop to atomically reserve items
    one at a time, preventing race conditions.
    
    Args:
        hb_collection: MongoDB collection for inventory (hb).
        nowuid: Product identifier.
        user_id: User ID making the purchase.
        count: Number of items to reserve.
    
    Returns:
        List[Dict]: List of reserved items, or None if insufficient stock.
    """
    reserved_items = []
    
    try:
        for _ in range(count):
            # Atomically find and update one available item
            item = hb_collection.find_one_and_update(
                {
                    'nowuid': nowuid,
                    'state': STATE_AVAILABLE
                },
                {
                    '$set': {
                        'state': STATE_SOLD,
                        'sold_to_user_id': user_id,
                        'reserved_at': logging.time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                },
                return_document=True
            )
            
            if item is None:
                # Not enough stock available
                logging.warning(
                    f"Insufficient stock for nowuid={nowuid}, "
                    f"needed {count}, got {len(reserved_items)}"
                )
                # Rollback what we reserved
                if reserved_items:
                    rollback_stock(hb_collection, [i['_id'] for i in reserved_items])
                return None
            
            reserved_items.append(item)
        
        logging.info(
            f"Reserved {count} items for user {user_id}, "
            f"nowuid={nowuid}"
        )
        return reserved_items
        
    except Exception as e:
        logging.error(f"Error reserving stock: {e}")
        # Rollback on error
        if reserved_items:
            rollback_stock(hb_collection, [i['_id'] for i in reserved_items])
        return None


def rollback_stock(hb_collection, item_ids: List) -> bool:
    """Rollback reserved stock back to available.
    
    Args:
        hb_collection: MongoDB collection for inventory (hb).
        item_ids: List of item _id values to rollback.
    
    Returns:
        bool: True if rollback successful.
    """
    try:
        result = hb_collection.update_many(
            {'_id': {'$in': item_ids}},
            {
                '$set': {'state': STATE_AVAILABLE},
                '$unset': {
                    'sold_to_user_id': '',
                    'reserved_at': ''
                }
            }
        )
        
        logging.info(
            f"Rolled back {result.modified_count} items"
        )
        return True
        
    except Exception as e:
        logging.error(f"Error rolling back stock: {e}")
        return False


def get_available_stock(hb_collection, nowuid: str) -> int:
    """Get the count of available stock for a product.
    
    Args:
        hb_collection: MongoDB collection for inventory (hb).
        nowuid: Product identifier.
    
    Returns:
        int: Count of available items.
    """
    try:
        return hb_collection.count_documents({
            'nowuid': nowuid,
            'state': STATE_AVAILABLE
        })
    except Exception as e:
        logging.error(f"Error getting available stock: {e}")
        return 0
