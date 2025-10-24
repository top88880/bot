#!/usr/bin/env python3
"""Migration script to backfill agent records with new fields.

This script adds the new fields required for the agent markup and backend system:
- owner_user_id (set to None if not available)
- markup_usdt (default "0")
- profit_available_usdt, profit_frozen_usdt, total_paid_usdt (all default "0")
- links (object with support_link, channel_link, announcement_link, extra_links)
"""

import logging
from datetime import datetime
from mongo import agents

logging.basicConfig(
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    level=logging.INFO
)


def migrate_agents():
    """Add missing fields to existing agent records."""
    logging.info("Starting agent migration...")
    
    # Find all agents
    all_agents = list(agents.find({}))
    logging.info(f"Found {len(all_agents)} agent(s) to check")
    
    updated_count = 0
    
    for agent in all_agents:
        agent_id = agent.get('agent_id', 'unknown')
        updates = {}
        
        # Check and add owner_user_id if missing
        if 'owner_user_id' not in agent:
            updates['owner_user_id'] = None
            logging.info(f"  {agent_id}: Adding owner_user_id=None")
        
        # Check and add markup_usdt if missing
        if 'markup_usdt' not in agent:
            updates['markup_usdt'] = '0'
            logging.info(f"  {agent_id}: Adding markup_usdt='0'")
        
        # Check and add profit fields if missing
        if 'profit_available_usdt' not in agent:
            updates['profit_available_usdt'] = '0'
            logging.info(f"  {agent_id}: Adding profit_available_usdt='0'")
        
        if 'profit_frozen_usdt' not in agent:
            updates['profit_frozen_usdt'] = '0'
            logging.info(f"  {agent_id}: Adding profit_frozen_usdt='0'")
        
        if 'total_paid_usdt' not in agent:
            updates['total_paid_usdt'] = '0'
            logging.info(f"  {agent_id}: Adding total_paid_usdt='0'")
        
        # Check and add links if missing
        if 'links' not in agent:
            updates['links'] = {
                'support_link': None,
                'channel_link': None,
                'announcement_link': None,
                'extra_links': []
            }
            logging.info(f"  {agent_id}: Adding links structure")
        else:
            # Check individual link fields
            links = agent.get('links', {})
            links_updated = False
            
            if 'support_link' not in links:
                links['support_link'] = None
                links_updated = True
            if 'channel_link' not in links:
                links['channel_link'] = None
                links_updated = True
            if 'announcement_link' not in links:
                links['announcement_link'] = None
                links_updated = True
            if 'extra_links' not in links:
                links['extra_links'] = []
                links_updated = True
            
            if links_updated:
                updates['links'] = links
                logging.info(f"  {agent_id}: Updating links structure")
        
        # Apply updates if any
        if updates:
            updates['updated_at'] = datetime.now()
            agents.update_one(
                {'agent_id': agent_id},
                {'$set': updates}
            )
            updated_count += 1
            logging.info(f"  {agent_id}: ✅ Updated")
        else:
            logging.info(f"  {agent_id}: ✓ No migration needed")
    
    logging.info(f"\nMigration complete!")
    logging.info(f"Total agents: {len(all_agents)}")
    logging.info(f"Updated: {updated_count}")
    logging.info(f"No changes: {len(all_agents) - updated_count}")


if __name__ == '__main__':
    try:
        migrate_agents()
    except Exception as e:
        logging.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
