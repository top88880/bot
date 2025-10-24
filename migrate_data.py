"""Data migration script for multi-tenant architecture.

This script migrates existing data to support the new tenant-based architecture.
Run this once after deploying the multi-tenant update.

Usage:
    python migrate_data.py
"""

import logging
import time
from datetime import datetime
from mongo import user, gmjlu, topup, hb
from models.constants import TENANT_MASTER, STATE_AVAILABLE, STATE_SOLD

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)


def migrate_users():
    """Add tenant field to existing users."""
    logging.info("Migrating users...")
    
    try:
        # Count users without tenant field
        users_to_migrate = user.count_documents({'tenant': {'$exists': False}})
        
        if users_to_migrate == 0:
            logging.info("No users to migrate")
            return
        
        logging.info(f"Found {users_to_migrate} users to migrate")
        
        # Update all users without tenant to master tenant
        result = user.update_many(
            {'tenant': {'$exists': False}},
            {'$set': {'tenant': TENANT_MASTER}}
        )
        
        logging.info(f"✅ Migrated {result.modified_count} users to master tenant")
        
    except Exception as e:
        logging.error(f"❌ Error migrating users: {e}")


def migrate_orders():
    """Add tenant and sold_by fields to existing orders."""
    logging.info("Migrating orders (gmjlu)...")
    
    try:
        # Count orders without tenant field
        orders_to_migrate = gmjlu.count_documents({'tenant': {'$exists': False}})
        
        if orders_to_migrate == 0:
            logging.info("No orders to migrate")
            return
        
        logging.info(f"Found {orders_to_migrate} orders to migrate")
        
        # Update all orders without tenant
        result = gmjlu.update_many(
            {'tenant': {'$exists': False}},
            {
                '$set': {
                    'tenant': TENANT_MASTER,
                    'sold_by': {
                        'type': 'master',
                        'agent_id': None
                    }
                }
            }
        )
        
        logging.info(f"✅ Migrated {result.modified_count} orders to master tenant")
        
    except Exception as e:
        logging.error(f"❌ Error migrating orders: {e}")


def migrate_topups():
    """Add tenant field to existing topup records."""
    logging.info("Migrating topup records...")
    
    try:
        # Count topups without tenant field
        topups_to_migrate = topup.count_documents({'tenant': {'$exists': False}})
        
        if topups_to_migrate == 0:
            logging.info("No topups to migrate")
            return
        
        logging.info(f"Found {topups_to_migrate} topups to migrate")
        
        # Update all topups without tenant
        result = topup.update_many(
            {'tenant': {'$exists': False}},
            {'$set': {'tenant': TENANT_MASTER}}
        )
        
        logging.info(f"✅ Migrated {result.modified_count} topups to master tenant")
        
        # Also ensure time field exists (convert from timer if needed)
        topups_without_time = topup.count_documents({'time': {'$exists': False}})
        
        if topups_without_time > 0:
            logging.info(f"Converting {topups_without_time} topup timer fields to datetime...")
            
            for t in topup.find({'time': {'$exists': False}}):
                try:
                    timer_str = t.get('timer')
                    if timer_str:
                        time_obj = datetime.strptime(timer_str, '%Y-%m-%d %H:%M:%S')
                        topup.update_one(
                            {'_id': t['_id']},
                            {'$set': {'time': time_obj}}
                        )
                except Exception as e:
                    logging.warning(f"Failed to convert timer for topup {t['_id']}: {e}")
        
    except Exception as e:
        logging.error(f"❌ Error migrating topups: {e}")


def normalize_inventory_states():
    """Normalize inventory states to integers."""
    logging.info("Normalizing inventory states...")
    
    try:
        # Count items with string states
        string_states = hb.count_documents({'state': {'$type': 'string'}})
        
        if string_states == 0:
            logging.info("No string states to normalize")
            return
        
        logging.info(f"Found {string_states} items with string states")
        
        # Map string states to integers
        # Assuming '0' or 'available' -> 0, '1' or 'sold' -> 1
        for item in hb.find({'state': {'$type': 'string'}}):
            state_str = str(item['state']).lower()
            
            if state_str in ['0', 'available']:
                new_state = STATE_AVAILABLE
            elif state_str in ['1', 'sold']:
                new_state = STATE_SOLD
            else:
                logging.warning(f"Unknown state '{state_str}' for item {item['_id']}, defaulting to available")
                new_state = STATE_AVAILABLE
            
            hb.update_one(
                {'_id': item['_id']},
                {'$set': {'state': new_state}}
            )
        
        logging.info("✅ Normalized all inventory states to integers")
        
    except Exception as e:
        logging.error(f"❌ Error normalizing inventory states: {e}")


def main():
    """Run all migrations."""
    logging.info("="*60)
    logging.info("Starting data migration for multi-tenant architecture")
    logging.info("="*60)
    
    start_time = time.time()
    
    # Run migrations
    migrate_users()
    migrate_orders()
    migrate_topups()
    normalize_inventory_states()
    
    elapsed = time.time() - start_time
    
    logging.info("="*60)
    logging.info(f"Migration completed in {elapsed:.2f} seconds")
    logging.info("="*60)
    logging.info("")
    logging.info("Next steps:")
    logging.info("1. Restart the bot to apply changes")
    logging.info("2. Database indexes will be created automatically on startup")
    logging.info("3. Test the bot functionality")
    logging.info("4. Create your first agent with /agent_create")


if __name__ == '__main__':
    main()
