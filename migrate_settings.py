#!/usr/bin/env python3
"""Migration script to convert agent links to settings structure.

This script migrates existing agents from the old links structure to the new
settings structure. It's safe to run multiple times - it will only migrate
agents that haven't been migrated yet.

Usage:
    python3 migrate_settings.py [--dry-run]
"""

import sys
import logging
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Import mongo
from mongo import agents

def migrate_agent_structure(agent_id: str, dry_run: bool = False) -> bool:
    """Migrate a single agent from links to settings structure.
    
    Args:
        agent_id: Agent identifier
        dry_run: If True, only report what would be done
        
    Returns:
        bool: True if migration performed/needed, False if already migrated
    """
    try:
        agent = agents.find_one({'agent_id': agent_id})
        if not agent:
            logging.warning(f"Agent {agent_id} not found")
            return False
        
        # Check if already has settings structure
        if 'settings' in agent and agent['settings']:
            logging.info(f"Agent {agent_id} already has settings structure - skipping")
            return False
        
        # Check if has old links structure
        links = agent.get('links', {})
        
        # Build new settings structure from old links
        settings = {
            'customer_service': links.get('support_link'),
            'official_channel': links.get('channel_link'),
            'restock_group': links.get('announcement_link'),
            'tutorial_link': None,  # New field, no old equivalent
            'notify_channel_id': None,  # New field, no old equivalent
            'extra_links': links.get('extra_links', [])
        }
        
        # Ensure financial fields have 8 decimal precision
        markup_usdt = agent.get('markup_usdt', '0')
        profit_available = agent.get('profit_available_usdt', '0')
        profit_frozen = agent.get('profit_frozen_usdt', '0')
        total_paid = agent.get('total_paid_usdt', '0')
        
        # Convert to Decimal and back to string with 8 decimal places
        try:
            markup_usdt = str(Decimal(str(markup_usdt)).quantize(Decimal('0.00000001')))
        except (ValueError, TypeError, Exception):
            markup_usdt = '0.00000000'
            
        try:
            profit_available = str(Decimal(str(profit_available)).quantize(Decimal('0.00000001')))
        except (ValueError, TypeError, Exception):
            profit_available = '0.00000000'
            
        try:
            profit_frozen = str(Decimal(str(profit_frozen)).quantize(Decimal('0.00000001')))
        except (ValueError, TypeError, Exception):
            profit_frozen = '0.00000000'
            
        try:
            total_paid = str(Decimal(str(total_paid)).quantize(Decimal('0.00000001')))
        except (ValueError, TypeError, Exception):
            total_paid = '0.00000000'
        
        if dry_run:
            logging.info(f"[DRY RUN] Would migrate agent {agent_id}:")
            logging.info(f"  New settings: {settings}")
            logging.info(f"  Updated markup: {markup_usdt}")
            logging.info(f"  Updated profit_available: {profit_available}")
            logging.info(f"  Updated profit_frozen: {profit_frozen}")
            logging.info(f"  Updated total_paid: {total_paid}")
            return True
        
        # Perform the migration
        result = agents.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    'settings': settings,
                    'markup_usdt': markup_usdt,
                    'profit_available_usdt': profit_available,
                    'profit_frozen_usdt': profit_frozen,
                    'total_paid_usdt': total_paid,
                    'updated_at': datetime.now()
                }
            }
        )
        
        if result.modified_count > 0:
            logging.info(f"✅ Successfully migrated agent {agent_id}")
            return True
        else:
            logging.warning(f"⚠️ No changes made for agent {agent_id}")
            return False
            
    except Exception as e:
        logging.error(f"❌ Error migrating agent {agent_id}: {e}")
        return False


def main():
    """Main migration function."""
    # Check for dry-run flag
    dry_run = '--dry-run' in sys.argv
    
    if dry_run:
        logging.info("🔍 Running in DRY RUN mode - no changes will be made")
    
    try:
        # Get all agents
        all_agents = list(agents.find({}))
        
        if not all_agents:
            logging.info("No agents found in database")
            return
        
        logging.info(f"Found {len(all_agents)} agents")
        
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        for agent in all_agents:
            agent_id = agent.get('agent_id', 'unknown')
            name = agent.get('name', 'Unnamed')
            
            logging.info(f"\nProcessing agent: {name} ({agent_id})")
            
            try:
                result = migrate_agent_structure(agent_id, dry_run=dry_run)
                if result:
                    migrated_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                logging.error(f"Error processing agent {agent_id}: {e}")
                error_count += 1
        
        # Summary
        logging.info("\n" + "="*60)
        logging.info("Migration Summary")
        logging.info("="*60)
        logging.info(f"Total agents: {len(all_agents)}")
        logging.info(f"Migrated: {migrated_count}")
        logging.info(f"Skipped (already migrated): {skipped_count}")
        logging.info(f"Errors: {error_count}")
        
        if dry_run:
            logging.info("\n⚠️ This was a DRY RUN - no changes were made")
            logging.info("Run without --dry-run to perform actual migration")
        else:
            logging.info("\n✅ Migration complete!")
            
    except Exception as e:
        logging.error(f"❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
