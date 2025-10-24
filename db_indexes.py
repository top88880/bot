"""Database index management.

This module ensures all necessary indexes are created for optimal performance
and data integrity in the multi-tenant architecture.
"""

import logging
from pymongo import ASCENDING, DESCENDING


def ensure_indexes(db):
    """Ensure all required indexes exist in the database.
    
    Args:
        db: MongoDB database instance.
    """
    try:
        logging.info("Creating database indexes...")
        
        # User collection indexes
        # Unique index on (tenant, user_id) for multi-tenant support
        db.user.create_index(
            [('tenant', ASCENDING), ('user_id', ASCENDING)],
            unique=True,
            name='idx_user_tenant_userid'
        )
        
        # Index on user_id alone for backward compatibility
        db.user.create_index(
            [('user_id', ASCENDING)],
            name='idx_user_userid'
        )
        
        # gmjlu (order records) collection indexes
        db.gmjlu.create_index(
            [('tenant', ASCENDING)],
            name='idx_gmjlu_tenant'
        )
        
        db.gmjlu.create_index(
            [('sold_by.type', ASCENDING)],
            name='idx_gmjlu_soldby_type'
        )
        
        db.gmjlu.create_index(
            [('sold_by.agent_id', ASCENDING)],
            name='idx_gmjlu_soldby_agentid'
        )
        
        db.gmjlu.create_index(
            [('time', DESCENDING)],
            name='idx_gmjlu_time'
        )
        
        db.gmjlu.create_index(
            [('user_id', ASCENDING), ('time', DESCENDING)],
            name='idx_gmjlu_userid_time'
        )
        
        # topup (recharge records) collection indexes
        db.topup.create_index(
            [('tenant', ASCENDING)],
            name='idx_topup_tenant'
        )
        
        db.topup.create_index(
            [('status', ASCENDING)],
            name='idx_topup_status'
        )
        
        db.topup.create_index(
            [('time', DESCENDING)],
            name='idx_topup_time'
        )
        
        db.topup.create_index(
            [('user_id', ASCENDING), ('status', ASCENDING)],
            name='idx_topup_userid_status'
        )
        
        db.topup.create_index(
            [('bianhao', ASCENDING)],
            name='idx_topup_bianhao'
        )
        
        # hb (inventory) collection indexes
        db.hb.create_index(
            [('nowuid', ASCENDING), ('state', ASCENDING)],
            name='idx_hb_nowuid_state'
        )
        
        db.hb.create_index(
            [('state', ASCENDING)],
            name='idx_hb_state'
        )
        
        # Agents collection indexes
        db.agents.create_index(
            [('agent_id', ASCENDING)],
            unique=True,
            name='idx_agents_agentid'
        )
        
        db.agents.create_index(
            [('status', ASCENDING)],
            name='idx_agents_status'
        )
        
        # Agent ledger collection indexes
        db.agent_ledger.create_index(
            [('agent_id', ASCENDING), ('status', ASCENDING)],
            name='idx_ledger_agentid_status'
        )
        
        db.agent_ledger.create_index(
            [('agent_id', ASCENDING), ('created_at', DESCENDING)],
            name='idx_ledger_agentid_created'
        )
        
        db.agent_ledger.create_index(
            [('status', ASCENDING), ('mature_at', ASCENDING)],
            name='idx_ledger_status_mature'
        )
        
        db.agent_ledger.create_index(
            [('order_id', ASCENDING)],
            name='idx_ledger_orderid'
        )
        
        # Agent withdrawals collection indexes
        db.agent_withdrawals.create_index(
            [('agent_id', ASCENDING), ('status', ASCENDING)],
            name='idx_withdrawals_agentid_status'
        )
        
        db.agent_withdrawals.create_index(
            [('status', ASCENDING), ('requested_at', DESCENDING)],
            name='idx_withdrawals_status_requested'
        )
        
        logging.info("✅ All database indexes created successfully")
        
    except Exception as e:
        logging.error(f"❌ Error creating indexes: {e}")
        raise
