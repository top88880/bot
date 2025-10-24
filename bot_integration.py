"""Integration module for multi-tenant agent architecture.

This module provides initialization and integration points for the agent
system. Import and call these functions from bot.py to enable agent features.
"""

import logging
from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, Filters

# Import database and ensure indexes
from mongo import bot_db
from db_indexes import ensure_indexes

# Import services
from services.earnings_service import mature_ledger_entries

# Import admin handlers
from admin.agents_admin import (
    agent_create_command, agent_list_command, agent_pause_command,
    agent_resume_command, agent_pricing_command, agent_panel_callback,
    agent_list_view_callback
)
from admin.withdraw_admin import (
    withdraw_list_command, withdraw_approve_command, withdraw_reject_command,
    withdraw_pay_command, withdraw_panel_callback, withdraw_view_callback
)

# Import agent handlers
from handlers.agent_panel import (
    agent_panel, agent_pricing_menu_callback, agent_pricing_type_callback,
    agent_pricing_value_handler
)
from handlers.agent_wallet import (
    agent_wallet_panel, agent_withdraw_request_callback,
    agent_withdraw_amount_handler, agent_withdraw_list_callback
)

# Import agents runner
from agents_runner import (
    discover_and_start_agents, start_agent_monitoring
)


def init_database_indexes():
    """Initialize database indexes on startup.
    
    This should be called once when the bot starts.
    """
    try:
        logging.info("Initializing database indexes...")
        ensure_indexes(bot_db)
        logging.info("✅ Database indexes initialized")
    except Exception as e:
        logging.error(f"❌ Failed to initialize database indexes: {e}")
        raise


def register_agent_admin_handlers(dispatcher):
    """Register admin handlers for agent management.
    
    Args:
        dispatcher: PTB dispatcher instance.
    """
    try:
        logging.info("Registering agent admin handlers...")
        
        # Admin commands for agent management
        dispatcher.add_handler(CommandHandler('agent_create', agent_create_command, run_async=True))
        dispatcher.add_handler(CommandHandler('agent_list', agent_list_command, run_async=True))
        dispatcher.add_handler(CommandHandler('agent_pause', agent_pause_command, run_async=True))
        dispatcher.add_handler(CommandHandler('agent_resume', agent_resume_command, run_async=True))
        dispatcher.add_handler(CommandHandler('agent_pricing', agent_pricing_command, run_async=True))
        
        # Admin commands for withdrawal management
        dispatcher.add_handler(CommandHandler('withdraw_list', withdraw_list_command, run_async=True))
        dispatcher.add_handler(CommandHandler('withdraw_approve', withdraw_approve_command, run_async=True))
        dispatcher.add_handler(CommandHandler('withdraw_reject', withdraw_reject_command, run_async=True))
        dispatcher.add_handler(CommandHandler('withdraw_pay', withdraw_pay_command, run_async=True))
        
        # Admin callback handlers
        dispatcher.add_handler(CallbackQueryHandler(agent_panel_callback, pattern='^agent_panel$'))
        dispatcher.add_handler(CallbackQueryHandler(agent_list_view_callback, pattern='^agent_list_view$'))
        dispatcher.add_handler(CallbackQueryHandler(withdraw_panel_callback, pattern='^withdraw_panel$'))
        dispatcher.add_handler(CallbackQueryHandler(withdraw_view_callback, pattern='^withdraw_view_'))
        
        logging.info("✅ Agent admin handlers registered")
        
    except Exception as e:
        logging.error(f"❌ Failed to register agent admin handlers: {e}")
        raise


def register_agent_user_handlers(dispatcher):
    """Register agent-side user handlers.
    
    Args:
        dispatcher: PTB dispatcher instance.
    """
    try:
        logging.info("Registering agent user handlers...")
        
        # Agent panel and settings
        dispatcher.add_handler(CallbackQueryHandler(agent_panel, pattern='^agent_panel$'))
        dispatcher.add_handler(CallbackQueryHandler(agent_pricing_menu_callback, pattern='^agent_pricing_menu$'))
        dispatcher.add_handler(CallbackQueryHandler(agent_pricing_type_callback, pattern='^agent_pricing_type_'))
        
        # Agent wallet and withdrawals
        dispatcher.add_handler(CallbackQueryHandler(agent_wallet_panel, pattern='^agent_wallet_panel$'))
        dispatcher.add_handler(CallbackQueryHandler(agent_withdraw_request_callback, pattern='^agent_withdraw_request$'))
        dispatcher.add_handler(CallbackQueryHandler(agent_withdraw_list_callback, pattern='^agent_withdraw_list$'))
        
        # Message handlers for agent flows (pricing, withdrawal)
        # These check user_data state to know when to handle
        dispatcher.add_handler(MessageHandler(
            Filters.text & Filters.private & ~Filters.command,
            agent_pricing_value_handler,
            run_async=True
        ))
        dispatcher.add_handler(MessageHandler(
            Filters.text & Filters.private & ~Filters.command,
            agent_withdraw_amount_handler,
            run_async=True
        ))
        
        logging.info("✅ Agent user handlers registered")
        
    except Exception as e:
        logging.error(f"❌ Failed to register agent user handlers: {e}")
        raise


def setup_earnings_maturity_job(job_queue):
    """Setup scheduled job for maturing ledger entries.
    
    Args:
        job_queue: PTB job queue instance.
    """
    try:
        logging.info("Setting up earnings maturity job...")
        
        def mature_job(context):
            """Job to mature pending ledger entries."""
            try:
                ledger_collection = bot_db['agent_ledger']
                count = mature_ledger_entries(ledger_collection)
                if count > 0:
                    logging.info(f"Matured {count} ledger entries")
            except Exception as e:
                logging.error(f"Error in maturity job: {e}")
        
        # Run every 10 minutes
        job_queue.run_repeating(mature_job, interval=600, first=60, name='mature_earnings')
        
        logging.info("✅ Earnings maturity job setup complete")
        
    except Exception as e:
        logging.error(f"❌ Failed to setup maturity job: {e}")
        raise


def start_agents_system():
    """Start the agent bot system.
    
    This discovers active agents and starts their bot instances.
    Should be called after the main bot is initialized.
    """
    try:
        logging.info("Starting agent bot system...")
        
        # Discover and start active agents
        discover_and_start_agents()
        
        # Start monitoring loop
        start_agent_monitoring()
        
        logging.info("✅ Agent bot system started")
        
    except Exception as e:
        logging.error(f"❌ Failed to start agent system: {e}")
        # Don't raise - allow main bot to continue even if agents fail


def inject_master_tenant_context(dispatcher):
    """Inject master tenant context into bot_data.
    
    Args:
        dispatcher: PTB dispatcher instance.
    """
    try:
        from models.constants import TENANT_MASTER
        
        dispatcher.bot_data["tenant"] = TENANT_MASTER
        dispatcher.bot_data["agent"] = None
        dispatcher.bot_data["agent_id"] = None
        
        logging.info(f"✅ Master tenant context injected: {TENANT_MASTER}")
        
    except Exception as e:
        logging.error(f"❌ Failed to inject master tenant context: {e}")
        raise


def initialize_agent_system(dispatcher, job_queue):
    """Complete initialization of the agent system.
    
    This is the main entry point that should be called from bot.py main().
    
    Args:
        dispatcher: PTB dispatcher instance.
        job_queue: PTB job queue instance.
    
    Returns:
        bool: True if initialization successful.
    """
    try:
        logging.info("="*60)
        logging.info("Initializing Multi-Tenant Agent System")
        logging.info("="*60)
        
        # Step 1: Initialize database indexes
        init_database_indexes()
        
        # Step 2: Inject master tenant context for main bot
        inject_master_tenant_context(dispatcher)
        
        # Step 3: Register admin handlers
        register_agent_admin_handlers(dispatcher)
        
        # Step 4: Register agent user handlers
        register_agent_user_handlers(dispatcher)
        
        # Step 5: Setup maturity job
        setup_earnings_maturity_job(job_queue)
        
        # Step 6: Start agent bot system
        start_agents_system()
        
        logging.info("="*60)
        logging.info("✅ Agent System Initialization Complete")
        logging.info("="*60)
        
        return True
        
    except Exception as e:
        logging.error("="*60)
        logging.error(f"❌ Agent System Initialization Failed: {e}")
        logging.error("="*60)
        return False


# Quick integration function for bot.py
def integrate_agent_system(dispatcher, job_queue):
    """Quick integration function to add to bot.py.
    
    Usage in bot.py main():
        from bot_integration import integrate_agent_system
        ...
        dispatcher = updater.dispatcher
        ...
        integrate_agent_system(dispatcher, updater.job_queue)
    
    Args:
        dispatcher: PTB dispatcher.
        job_queue: PTB job queue.
    """
    return initialize_agent_system(dispatcher, job_queue)
