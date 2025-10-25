"""Helper module for managing bot contact links in multi-tenant agent architecture.

This module provides functions to retrieve contact links and notification channels
for both the main bot and child agent bots. Child agents use per-agent settings
from the database, while the main bot falls back to environment variables.
"""

import os
import logging
from typing import Optional, Dict
from telegram.ext import CallbackContext


def get_links_for_child_agent(context: CallbackContext) -> Dict[str, Optional[str]]:
    """Get all contact links for a child agent.
    
    For child agents (context.bot_data has agent_id), returns per-agent settings.
    For the main bot, returns None for all fields (use env variables instead).
    
    Args:
        context: CallbackContext to get agent info
    
    Returns:
        Dict with keys:
        - customer_service: Customer service contact
        - official_channel: Official channel link
        - restock_group: Restock notification group link
        - tutorial_link: Tutorial/help link
        - notify_channel_id: Notification channel ID (as string or int)
        - notify_group_id: Notification group ID (as string or int)
        - extra_links: List of extra link objects
        
        Returns None for each field if not set or if this is the main bot.
    """
    agent_id = context.bot_data.get('agent_id')
    
    # Main bot - return empty dict, should use env variables
    if not agent_id:
        return {
            'customer_service': None,
            'official_channel': None,
            'restock_group': None,
            'tutorial_link': None,
            'notify_channel_id': None,
            'notify_group_id': None,
            'extra_links': []
        }
    
    # Child agent - get from database
    try:
        from mongo import agents
        
        agent = agents.find_one({'agent_id': agent_id})
        if not agent:
            logging.warning(f"Agent not found: {agent_id}")
            return {
                'customer_service': None,
                'official_channel': None,
                'restock_group': None,
                'tutorial_link': None,
                'notify_channel_id': None,
                'notify_group_id': None,
                'extra_links': []
            }
        
        # Get settings from agent document
        settings = agent.get('settings', {})
        
        # Check for global defaults if implemented (currently not in scope)
        # If mongo_config.get_effective_links_for_agent exists, use it here
        # For now, only use agent settings without fallback to global DB defaults
        
        return {
            'customer_service': settings.get('customer_service'),
            'official_channel': settings.get('official_channel'),
            'restock_group': settings.get('restock_group'),
            'tutorial_link': settings.get('tutorial_link'),
            'notify_channel_id': settings.get('notify_channel_id'),
            'notify_group_id': settings.get('notify_group_id'),
            'extra_links': settings.get('extra_links', [])
        }
    except Exception as e:
        logging.error(f"Error getting agent links for {agent_id}: {e}")
        return {
            'customer_service': None,
            'official_channel': None,
            'restock_group': None,
            'tutorial_link': None,
            'notify_channel_id': None,
            'notify_group_id': None,
            'extra_links': []
        }


def format_contacts_block_for_child(context: CallbackContext, lang: str = 'zh') -> str:
    """Format contact information block for display.
    
    For child agents, only shows configured links. For main bot, uses env variables.
    
    Args:
        context: CallbackContext to get agent info
        lang: Language code ('zh' or 'en')
    
    Returns:
        Formatted HTML string with contact information
    """
    agent_id = context.bot_data.get('agent_id')
    
    # Main bot - use env variables
    if not agent_id:
        customer_service = os.getenv('CUSTOMER_SERVICE', '@lwmmm')
        official_channel = os.getenv('OFFICIAL_CHANNEL', '@XCZHCS')
        restock_group = os.getenv('RESTOCK_GROUP', 'https://t.me/+EeTF1qOe_MoyMzQ0')
        
        msg = f"""
<b>{'客服' if lang == 'zh' else 'Support'}：</b>{customer_service}  
<b>{'官方频道' if lang == 'zh' else 'Official Channel'}：</b>{official_channel}  
<b>{'补货通知群' if lang == 'zh' else 'Restock Group'}：</b>{restock_group}"""
        return msg.strip()
    
    # Child agent - use per-agent settings
    links = get_links_for_child_agent(context)
    
    msg_parts = []
    
    if links['customer_service']:
        msg_parts.append(
            f"<b>{'客服' if lang == 'zh' else 'Support'}：</b>{links['customer_service']}"
        )
    
    if links['official_channel']:
        msg_parts.append(
            f"<b>{'官方频道' if lang == 'zh' else 'Official Channel'}：</b>{links['official_channel']}"
        )
    
    if links['restock_group']:
        msg_parts.append(
            f"<b>{'补货通知群' if lang == 'zh' else 'Restock Group'}：</b>{links['restock_group']}"
        )
    
    if links['tutorial_link']:
        msg_parts.append(
            f"<b>{'教程' if lang == 'zh' else 'Tutorial'}：</b>{links['tutorial_link']}"
        )
    
    # Add custom links
    extra_links = links.get('extra_links', [])
    if extra_links:
        msg_parts.append("")  # Empty line
        msg_parts.append(f"<b>{'更多链接' if lang == 'zh' else 'More Links'}：</b>")
        for link_data in extra_links:
            title = link_data.get('title', 'Link')
            url = link_data.get('url', '')
            msg_parts.append(f"• <a href='{url}'>{title}</a>")
    
    if not msg_parts:
        # No links configured
        return f"<i>{'未设置联系方式' if lang == 'zh' else 'No contact information configured'}</i>"
    
    return "\n".join(msg_parts)


def build_contact_buttons_for_child(context: CallbackContext, lang: str = 'zh') -> list:
    """Build inline keyboard buttons for contact links.
    
    For child agents, only shows configured buttons. For main bot, uses env variables.
    
    Args:
        context: CallbackContext to get agent info
        lang: Language code ('zh' or 'en')
    
    Returns:
        List of button rows (list of InlineKeyboardButton lists)
    """
    from telegram import InlineKeyboardButton
    
    agent_id = context.bot_data.get('agent_id')
    buttons = []
    
    # Main bot - use env variables
    if not agent_id:
        customer_service = os.getenv('CUSTOMER_SERVICE', '@lwmmm')
        official_channel = os.getenv('OFFICIAL_CHANNEL', '@XCZHCS')
        restock_group = os.getenv('RESTOCK_GROUP', 'https://t.me/+EeTF1qOe_MoyMzQ0')
        
        if customer_service:
            buttons.append([InlineKeyboardButton(
                '📞 ' + ('联系客服' if lang == 'zh' else 'Contact Support'),
                url=f"https://t.me/{customer_service.replace('@', '')}"
            )])
        
        if official_channel:
            buttons.append([InlineKeyboardButton(
                '📢 ' + ('官方频道' if lang == 'zh' else 'Official Channel'),
                url=f"https://t.me/{official_channel.replace('@', '')}"
            )])
        
        return buttons
    
    # Child agent - use per-agent settings
    links = get_links_for_child_agent(context)
    
    if links['customer_service']:
        cs_link = links['customer_service']
        # Handle both @username and full URLs
        if cs_link.startswith('@'):
            url = f"https://t.me/{cs_link.replace('@', '')}"
        elif cs_link.startswith('http'):
            url = cs_link
        else:
            url = f"https://t.me/{cs_link}"
        
        buttons.append([InlineKeyboardButton(
            '📞 ' + ('联系客服' if lang == 'zh' else 'Contact Support'),
            url=url
        )])
    
    if links['official_channel']:
        ch_link = links['official_channel']
        if ch_link.startswith('@'):
            url = f"https://t.me/{ch_link.replace('@', '')}"
        elif ch_link.startswith('http'):
            url = ch_link
        else:
            url = f"https://t.me/{ch_link}"
        
        buttons.append([InlineKeyboardButton(
            '📢 ' + ('官方频道' if lang == 'zh' else 'Official Channel'),
            url=url
        )])
    
    if links['restock_group']:
        rg_link = links['restock_group']
        if rg_link.startswith('http'):
            url = rg_link
        elif rg_link.startswith('@'):
            url = f"https://t.me/{rg_link.replace('@', '')}"
        else:
            url = f"https://t.me/{rg_link}"
        
        buttons.append([InlineKeyboardButton(
            '📣 ' + ('补货通知' if lang == 'zh' else 'Restock Notifications'),
            url=url
        )])
    
    if links['tutorial_link']:
        tut_link = links['tutorial_link']
        if tut_link.startswith('http'):
            url = tut_link
        elif tut_link.startswith('@'):
            url = f"https://t.me/{tut_link.replace('@', '')}"
        else:
            url = f"https://t.me/{tut_link}"
        
        buttons.append([InlineKeyboardButton(
            '📖 ' + ('使用教程' if lang == 'zh' else 'Tutorial'),
            url=url
        )])
    
    # Add extra links
    extra_links = links.get('extra_links', [])
    for link_data in extra_links:
        title = link_data.get('title', 'Link')
        url = link_data.get('url', '')
        if url:
            buttons.append([InlineKeyboardButton(title, url=url)])
    
    return buttons


def get_notify_channel_id_for_child(context: CallbackContext) -> Optional[int]:
    """Get notification channel ID for sending stock notifications.
    
    For child agents, returns the agent's notify_channel_id.
    For the main bot, returns the env variable NOTIFY_CHANNEL_ID.
    
    Args:
        context: CallbackContext to get agent info
    
    Returns:
        Channel ID as integer, or None if not configured
    """
    agent_id = context.bot_data.get('agent_id')
    
    # Main bot - use env variable
    if not agent_id:
        try:
            channel_id = int(os.getenv("NOTIFY_CHANNEL_ID", "0"))
            return channel_id if channel_id != 0 else None
        except (ValueError, TypeError):
            logging.warning("Invalid NOTIFY_CHANNEL_ID in env")
            return None
    
    # Child agent - get from settings
    links = get_links_for_child_agent(context)
    notify_channel_id = links.get('notify_channel_id')
    
    if notify_channel_id is None:
        return None
    
    # Convert to int if it's a string
    try:
        if isinstance(notify_channel_id, str):
            return int(notify_channel_id)
        return int(notify_channel_id)
    except (ValueError, TypeError):
        logging.warning(f"Invalid notify_channel_id for agent {agent_id}: {notify_channel_id}")
        return None


def get_notify_group_id_for_child(context: CallbackContext) -> Optional[int]:
    """Get notification group ID for sending group notifications.
    
    For child agents, returns the agent's notify_group_id.
    For the main bot, returns None (not typically used for main bot).
    
    NOTE: This supports basic group notifications. Future versions may add
    message_thread_id parameter for topic-aware groups.
    
    Args:
        context: CallbackContext to get agent info
    
    Returns:
        Group ID as integer, or None if not configured
    """
    agent_id = context.bot_data.get('agent_id')
    
    # Main bot - not typically used
    if not agent_id:
        return None
    
    # Child agent - get from settings
    links = get_links_for_child_agent(context)
    notify_group_id = links.get('notify_group_id')
    
    if notify_group_id is None:
        return None
    
    # Convert to int if it's a string (or accept @username)
    try:
        # If it starts with @, it's a username - return as-is (will be int conversion error caught below)
        if isinstance(notify_group_id, str):
            if notify_group_id.startswith('@'):
                # Username format - return as string for Telegram to resolve
                return notify_group_id
            return int(notify_group_id)
        return int(notify_group_id)
    except (ValueError, TypeError):
        logging.warning(f"Invalid notify_group_id for agent {agent_id}: {notify_group_id}")
        return None


def get_customer_service_for_child(context: CallbackContext) -> str:
    """Get customer service link.
    
    For child agents, returns agent's customer_service or 'Not Set'.
    For main bot, returns env variable.
    
    Args:
        context: CallbackContext to get agent info
    
    Returns:
        Customer service contact string
    """
    agent_id = context.bot_data.get('agent_id')
    
    if not agent_id:
        return os.getenv('CUSTOMER_SERVICE', '@lwmmm')
    
    links = get_links_for_child_agent(context)
    return links.get('customer_service') or ('未设置' if context.user_data.get('lang') == 'zh' else 'Not Set')


def get_tutorial_link_for_child(context: CallbackContext) -> Optional[str]:
    """Get tutorial link.
    
    For child agents, returns agent's tutorial_link or None.
    For main bot, returns env variable.
    
    Args:
        context: CallbackContext to get agent info
    
    Returns:
        Tutorial link string or None
    """
    agent_id = context.bot_data.get('agent_id')
    
    if not agent_id:
        return os.getenv('TUTORIAL_LINK', 'https://t.me/XCZHCS/106')
    
    links = get_links_for_child_agent(context)
    return links.get('tutorial_link')
