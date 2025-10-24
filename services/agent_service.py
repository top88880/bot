"""Agent service for managing agent bots.

This module handles CRUD operations for agent bots including
token encryption, pricing configuration, and status management.
"""

import logging
import time
from typing import Optional, List, Dict
from services.crypto import encrypt_token, decrypt_token
from models.constants import (
    AGENT_STATUS_ACTIVE, AGENT_STATUS_PAUSED, AGENT_STATUS_SUSPENDED,
    MARKUP_TYPE_PERCENT, DEFAULT_MARKUP_PERCENT
)


def create_agent(
    agents_collection,
    agent_id: str,
    bot_token: str,
    name: str,
    markup_type: str = MARKUP_TYPE_PERCENT,
    markup_value: float = DEFAULT_MARKUP_PERCENT,
    created_by_admin_id: int = None
) -> Optional[Dict]:
    """Create a new agent bot.
    
    Args:
        agents_collection: MongoDB collection for agents.
        agent_id: Unique identifier for the agent.
        bot_token: Telegram bot token (will be encrypted).
        name: Display name for the agent.
        markup_type: Type of markup ("fixed" or "percent").
        markup_value: Markup value.
        created_by_admin_id: Admin user ID who created the agent.
    
    Returns:
        Dict: Created agent document, or None on error.
    """
    try:
        # Check if agent_id already exists
        if agents_collection.find_one({'agent_id': agent_id}):
            logging.error(f"Agent ID already exists: {agent_id}")
            return None
        
        # Encrypt the bot token
        encrypted_token = encrypt_token(bot_token)
        
        agent_doc = {
            'agent_id': agent_id,
            'name': name,
            'bot_token_encrypted': encrypted_token,
            'status': AGENT_STATUS_ACTIVE,
            'pricing': {
                'markup_type': markup_type,
                'markup_value': markup_value
            },
            'payout': {
                'wallet_address': None,  # To be set by agent
                'min_withdrawal': 10  # Minimum withdrawal amount
            },
            'branding': {
                'welcome_text': None,  # Optional custom welcome text
                'logo_url': None        # Optional custom logo
            },
            'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'created_by_admin_id': created_by_admin_id,
            'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        result = agents_collection.insert_one(agent_doc)
        agent_doc['_id'] = result.inserted_id
        
        logging.info(f"Created agent: {agent_id} ({name})")
        return agent_doc
        
    except Exception as e:
        logging.error(f"Error creating agent: {e}")
        return None


def get_agent_by_id(agents_collection, agent_id: str) -> Optional[Dict]:
    """Get agent by ID.
    
    Args:
        agents_collection: MongoDB collection for agents.
        agent_id: Agent identifier.
    
    Returns:
        Dict: Agent document, or None if not found.
    """
    try:
        return agents_collection.find_one({'agent_id': agent_id})
    except Exception as e:
        logging.error(f"Error getting agent: {e}")
        return None


def get_active_agents(agents_collection) -> List[Dict]:
    """Get all active agents.
    
    Args:
        agents_collection: MongoDB collection for agents.
    
    Returns:
        List[Dict]: List of active agent documents.
    """
    try:
        return list(agents_collection.find({'status': AGENT_STATUS_ACTIVE}))
    except Exception as e:
        logging.error(f"Error getting active agents: {e}")
        return []


def update_agent_status(
    agents_collection,
    agent_id: str,
    status: str
) -> bool:
    """Update agent status.
    
    Args:
        agents_collection: MongoDB collection for agents.
        agent_id: Agent identifier.
        status: New status (active/paused/suspended).
    
    Returns:
        bool: True if update successful.
    """
    try:
        result = agents_collection.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    'status': status,
                    'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')
                }
            }
        )
        
        if result.modified_count > 0:
            logging.info(f"Updated agent {agent_id} status to {status}")
            return True
        return False
        
    except Exception as e:
        logging.error(f"Error updating agent status: {e}")
        return False


def update_agent_pricing(
    agents_collection,
    agent_id: str,
    markup_type: str,
    markup_value: float
) -> bool:
    """Update agent pricing configuration.
    
    Args:
        agents_collection: MongoDB collection for agents.
        agent_id: Agent identifier.
        markup_type: Type of markup ("fixed" or "percent").
        markup_value: Markup value.
    
    Returns:
        bool: True if update successful.
    """
    try:
        result = agents_collection.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    'pricing.markup_type': markup_type,
                    'pricing.markup_value': markup_value,
                    'updated_at': time.strftime('%Y-%m-%d %H:%M:%S')
                }
            }
        )
        
        if result.modified_count > 0:
            logging.info(
                f"Updated agent {agent_id} pricing: "
                f"{markup_type}={markup_value}"
            )
            return True
        return False
        
    except Exception as e:
        logging.error(f"Error updating agent pricing: {e}")
        return False


def get_agent_bot_token(agents_collection, agent_id: str) -> Optional[str]:
    """Get decrypted bot token for an agent.
    
    Args:
        agents_collection: MongoDB collection for agents.
        agent_id: Agent identifier.
    
    Returns:
        str: Decrypted bot token, or None on error.
    """
    try:
        agent = agents_collection.find_one({'agent_id': agent_id})
        if not agent:
            logging.error(f"Agent not found: {agent_id}")
            return None
        
        encrypted_token = agent.get('bot_token_encrypted')
        if not encrypted_token:
            logging.error(f"No encrypted token for agent: {agent_id}")
            return None
        
        return decrypt_token(encrypted_token)
        
    except Exception as e:
        logging.error(f"Error getting agent bot token: {e}")
        return None


def list_agents(agents_collection, status: str = None) -> List[Dict]:
    """List all agents, optionally filtered by status.
    
    Args:
        agents_collection: MongoDB collection for agents.
        status: Optional status filter.
    
    Returns:
        List[Dict]: List of agent documents.
    """
    try:
        query = {} if status is None else {'status': status}
        return list(agents_collection.find(query))
    except Exception as e:
        logging.error(f"Error listing agents: {e}")
        return []
