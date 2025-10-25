"""Agent runner for managing multiple bot instances.

This module discovers active agents and starts a separate PTB (Python Telegram Bot)
instance for each agent. Each agent bot shares the same database and inventory but
operates with its own tenant context.
"""

import os
import logging
import threading
import time
from typing import Dict, List
from telegram.ext import Updater, Dispatcher
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import services
from services.agent_service import get_active_agents, get_agent_bot_token
from services.tenant import get_tenant_string

# Import mongo for database access
from mongo import bot_db

# Track running agent bot instances
running_agents: Dict[str, Dict] = {}
running_agents_lock = threading.Lock()


def register_handlers_for_agent(dispatcher: Dispatcher, agent_id: str, agent_doc: dict):
    """Register all handlers for an agent bot.
    
    This should register the same handlers as the master bot, but they will
    operate with the agent's tenant context.
    
    Args:
        dispatcher: PTB dispatcher for the agent bot.
        agent_id: Agent identifier.
        agent_doc: Agent document from database.
    """
    # Import handlers from bot.py
    # We'll defer the actual handler registration to a later phase
    # For now, just log that handlers would be registered
    logging.info(f"Handlers would be registered for agent {agent_id}")
    
    # In the actual implementation, we would import and register handlers like:
    # from bot import start, help_command, textkeyboard, etc.
    # dispatcher.add_handler(CommandHandler('start', start, run_async=True))
    # ... etc
    
    # The key is that all handlers will have access to:
    # - context.bot_data["tenant"] = get_tenant_string(agent_id)
    # - context.bot_data["agent"] = agent_doc
    # - context.bot_data["agent_id"] = agent_id


def start_agent_bot(agent_id: str, agent_doc: dict) -> bool:
    """Start a bot instance for an agent.
    
    Args:
        agent_id: Agent identifier.
        agent_doc: Agent document from database.
    
    Returns:
        bool: True if started successfully.
    """
    try:
        # Get decrypted bot token
        agents_collection = bot_db['agents']
        bot_token = get_agent_bot_token(agents_collection, agent_id)
        
        if not bot_token:
            logging.error(f"Failed to get bot token for agent {agent_id}")
            return False
        
        # Create Updater with agent's bot token
        updater = Updater(
            token=bot_token,
            use_context=True,
            workers=32,  # Fewer workers per agent bot
            request_kwargs={
                'read_timeout': int(os.getenv('REQUEST_TIMEOUT', '20')),
                'connect_timeout': int(os.getenv('REQUEST_TIMEOUT', '20'))
            }
        )
        
        dispatcher = updater.dispatcher
        
        # Inject tenant and agent context into bot_data
        tenant = get_tenant_string(agent_id)
        dispatcher.bot_data["tenant"] = tenant
        dispatcher.bot_data["agent"] = agent_doc
        dispatcher.bot_data["agent_id"] = agent_id
        
        # Cache bot username for notifications
        try:
            bot_info = updater.bot.get_me()
            dispatcher.bot_data["bot_username"] = bot_info.username
            logging.info(f"Cached bot username for agent {agent_id}: @{bot_info.username}")
        except Exception as e:
            logging.warning(f"Failed to cache bot username for agent {agent_id}: {e}")
            dispatcher.bot_data["bot_username"] = "bot"
        
        logging.info(
            f"Initialized agent bot {agent_id} with tenant context: {tenant}"
        )
        
        # Register handlers
        register_handlers_for_agent(dispatcher, agent_id, agent_doc)
        
        # Start polling in a separate thread
        def run_bot():
            try:
                updater.start_polling(timeout=int(os.getenv('BOT_TIMEOUT', '600')))
                logging.info(f"Agent bot {agent_id} started polling")
                updater.idle()
            except Exception as e:
                logging.error(f"Agent bot {agent_id} polling error: {e}")
        
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        
        # Track the running instance
        with running_agents_lock:
            running_agents[agent_id] = {
                'updater': updater,
                'dispatcher': dispatcher,
                'thread': bot_thread,
                'agent_doc': agent_doc,
                'tenant': tenant,
                'started_at': time.time()
            }
        
        logging.info(f"✅ Started agent bot: {agent_id} ({agent_doc.get('name')})")
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed to start agent bot {agent_id}: {e}")
        return False


def stop_agent_bot(agent_id: str) -> bool:
    """Stop a running agent bot.
    
    Args:
        agent_id: Agent identifier.
    
    Returns:
        bool: True if stopped successfully.
    """
    try:
        with running_agents_lock:
            if agent_id not in running_agents:
                logging.warning(f"Agent bot {agent_id} is not running")
                return False
            
            agent_info = running_agents[agent_id]
            updater = agent_info['updater']
            
            # Stop the bot
            updater.stop()
            
            # Remove from tracking
            del running_agents[agent_id]
        
        logging.info(f"✅ Stopped agent bot: {agent_id}")
        return True
        
    except Exception as e:
        logging.error(f"❌ Failed to stop agent bot {agent_id}: {e}")
        return False


def discover_and_start_agents():
    """Discover active agents and start their bots.
    
    This should be called on startup to start all active agent bots.
    """
    try:
        agents_collection = bot_db['agents']
        active_agents = get_active_agents(agents_collection)
        
        logging.info(f"Found {len(active_agents)} active agents")
        
        for agent_doc in active_agents:
            agent_id = agent_doc['agent_id']
            
            # Check if already running
            with running_agents_lock:
                if agent_id in running_agents:
                    logging.info(f"Agent bot {agent_id} already running")
                    continue
            
            # Start the agent bot
            start_agent_bot(agent_id, agent_doc)
            
            # Small delay between starts to avoid overwhelming the system
            time.sleep(1)
        
        logging.info("✅ Agent discovery and startup complete")
        
    except Exception as e:
        logging.error(f"❌ Error during agent discovery: {e}")


def monitor_agents_loop():
    """Monitoring loop to restart failed agents.
    
    This should run in a background thread to monitor and restart agents
    that have stopped unexpectedly.
    """
    while True:
        try:
            time.sleep(60)  # Check every minute
            
            agents_collection = bot_db['agents']
            active_agents = get_active_agents(agents_collection)
            active_agent_ids = {a['agent_id'] for a in active_agents}
            
            # Check if any active agents are not running
            with running_agents_lock:
                running_agent_ids = set(running_agents.keys())
            
            # Start agents that should be running but aren't
            for agent_doc in active_agents:
                agent_id = agent_doc['agent_id']
                if agent_id not in running_agent_ids:
                    logging.warning(
                        f"Agent {agent_id} should be running but isn't, restarting..."
                    )
                    start_agent_bot(agent_id, agent_doc)
            
            # Stop agents that are running but shouldn't be
            for agent_id in running_agent_ids:
                if agent_id not in active_agent_ids:
                    logging.info(
                        f"Agent {agent_id} is no longer active, stopping..."
                    )
                    stop_agent_bot(agent_id)
            
        except Exception as e:
            logging.error(f"Error in agent monitoring loop: {e}")


def start_agent_monitoring():
    """Start the agent monitoring thread."""
    monitor_thread = threading.Thread(target=monitor_agents_loop, daemon=True)
    monitor_thread.start()
    logging.info("✅ Agent monitoring started")


def get_running_agents() -> List[str]:
    """Get list of currently running agent IDs.
    
    Returns:
        List[str]: List of running agent IDs.
    """
    with running_agents_lock:
        return list(running_agents.keys())


def get_agent_info(agent_id: str) -> dict:
    """Get info about a running agent.
    
    Args:
        agent_id: Agent identifier.
    
    Returns:
        dict: Agent info or None if not running.
    """
    with running_agents_lock:
        return running_agents.get(agent_id)


# Cleanup function for graceful shutdown
def shutdown_all_agents():
    """Stop all running agent bots."""
    logging.info("Shutting down all agent bots...")
    
    with running_agents_lock:
        agent_ids = list(running_agents.keys())
    
    for agent_id in agent_ids:
        stop_agent_bot(agent_id)
    
    logging.info("✅ All agent bots shut down")


# Register cleanup on exit
import atexit
atexit.register(shutdown_all_agents)


if __name__ == '__main__':
    # This allows testing the agent runner independently
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s'
    )
    
    logging.info("Starting agent runner...")
    discover_and_start_agents()
    start_agent_monitoring()
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        logging.info("Received interrupt signal")
        shutdown_all_agents()
