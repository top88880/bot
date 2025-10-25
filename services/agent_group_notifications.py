"""Agent group notification service.

This module provides functionality for sending transaction notifications
to agent-specific Telegram groups.
"""

import logging
from typing import Optional, Dict
from decimal import Decimal
from telegram import Bot
from telegram.ext import CallbackContext
from telegram.error import TelegramError


# ===== i18n Templates =====
TEMPLATES = {
    'zh': {
        'order_notification': """🛒收到了一份 采购订单 🛍

❇️用户名：@{agent_bot_username}
ID : {order_sn}
🔅每个利润  : {profit_per_item}U (每个)
➖➖➖➖➖➖
🗓日期|时间：  {ts}
❤️来自用户：{buyer_id}
🛍采购商品：{product_name}
☑️采购数量：{qty}
💰订单总价值：{order_total}U（{unit_price}U*{qty}）
🌐您当前商品的价格: {agent_price}U (每个单元)
🌐原号铺商品的价格: {base_price}U (每个单元)
💸旧余额  :{before_balance}U
🟢用户当前余额：{after_balance}U
➖➖➖➖➖➖
💎您从这笔交易中获得的利润({qty} * {profit_per_item})：{profit_total}U""",
        
        'recharge_notification': """用户: {buyer_name} 充值成功

地址: {address}
充值: {amount} USDT
充值详情: {tx_url_or_cmd}""",
        
        'test_notification': """✅ 测试通知

这是来自您的代理机器人的测试消息。

如果您能看到此消息，说明通知配置正常。

时间：{timestamp}"""
    },
    'en': {
        'order_notification': """🛒 Purchase Order Received 🛍

❇️Username：@{agent_bot_username}
ID : {order_sn}
🔅Profit per item  : {profit_per_item}U (each)
➖➖➖➖➖➖
🗓Date|Time：  {ts}
❤️From user：{buyer_id}
🛍Product：{product_name}
☑️Quantity：{qty}
💰Order total：{order_total}U（{unit_price}U*{qty}）
🌐Your product price: {agent_price}U (per unit)
🌐Base shop price: {base_price}U (per unit)
💸Old balance  :{before_balance}U
🟢User current balance：{after_balance}U
➖➖➖➖➖➖
💎Your profit from this transaction({qty} * {profit_per_item})：{profit_total}U""",
        
        'recharge_notification': """User: {buyer_name} Recharge Successful

Address: {address}
Recharge: {amount} USDT
Details: {tx_url_or_cmd}""",
        
        'test_notification': """✅ Test Notification

This is a test message from your agent bot.

If you see this message, the notification is configured correctly.

Time: {timestamp}"""
    }
}


def get_notify_group_id_for_child(context: CallbackContext) -> Optional[int]:
    """Get notification group ID for child agent.
    
    For child agents, returns the agent's notify_group_id from settings.
    For the main bot, returns None.
    
    Args:
        context: CallbackContext to get agent info
    
    Returns:
        Group chat ID (int) or None if not set or if this is the main bot.
    """
    agent_id = context.bot_data.get('agent_id')
    
    # Main bot - no group notifications
    if not agent_id:
        return None
    
    try:
        from mongo import agents
        
        agent = agents.find_one({'agent_id': agent_id})
        if not agent:
            logging.warning(f"Agent not found: {agent_id}")
            return None
        
        # Get settings from agent document
        settings = agent.get('settings', {})
        notify_group_id = settings.get('notify_group_id')
        
        if notify_group_id is None:
            return None
        
        # Convert to int
        try:
            if isinstance(notify_group_id, str):
                return int(notify_group_id)
            return int(notify_group_id)
        except (ValueError, TypeError):
            logging.warning(f"Invalid notify_group_id for agent {agent_id}: {notify_group_id}")
            return None
    
    except Exception as e:
        logging.error(f"Error getting notify_group_id for agent {agent_id}: {e}")
        return None


def send_agent_group_message(
    context: CallbackContext,
    text: str,
    parse_mode: str = 'HTML',
    disable_web_page_preview: bool = True
) -> bool:
    """Send a message to the agent's notification group.
    
    Args:
        context: CallbackContext to get agent info and bot
        text: Message text to send
        parse_mode: Parse mode for the message ('HTML' or 'Markdown')
        disable_web_page_preview: Whether to disable link previews
    
    Returns:
        True if message sent successfully, False otherwise
    """
    try:
        group_id = get_notify_group_id_for_child(context)
        
        if group_id is None:
            logging.debug("No notification group configured, skipping notification")
            return False
        
        # Send message using bot from context
        bot = context.bot
        bot.send_message(
            chat_id=group_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview
        )
        
        logging.info(f"Successfully sent group notification to {group_id}")
        return True
        
    except TelegramError as e:
        logging.error(f"Failed to send group notification: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error sending group notification: {e}")
        return False


def format_order_notification(
    lang: str,
    order_data: Dict
) -> str:
    """Format an order notification message.
    
    Args:
        lang: Language code ('zh' or 'en')
        order_data: Dictionary containing order information with keys:
            - agent_bot_username: Bot username
            - order_sn: Order number
            - profit_per_item: Profit per item
            - ts: Timestamp
            - buyer_id: Buyer user ID
            - product_name: Product name
            - qty: Quantity
            - order_total: Total order value
            - unit_price: Unit price
            - agent_price: Agent's price
            - base_price: Base price
            - before_balance: Balance before purchase
            - after_balance: Balance after purchase
            - profit_total: Total profit
    
    Returns:
        Formatted notification message
    """
    if lang not in TEMPLATES:
        lang = 'zh'
    
    template = TEMPLATES[lang]['order_notification']
    
    try:
        return template.format(**order_data)
    except KeyError as e:
        logging.error(f"Missing key in order data: {e}")
        return f"Error formatting order notification: missing {e}"


def format_recharge_notification(
    lang: str,
    recharge_data: Dict
) -> str:
    """Format a recharge notification message.
    
    Args:
        lang: Language code ('zh' or 'en')
        recharge_data: Dictionary containing recharge information with keys:
            - buyer_name: User name or ID
            - address: Recharge address
            - amount: Recharge amount
            - tx_url_or_cmd: Transaction URL or command
    
    Returns:
        Formatted notification message
    """
    if lang not in TEMPLATES:
        lang = 'zh'
    
    template = TEMPLATES[lang]['recharge_notification']
    
    try:
        return template.format(**recharge_data)
    except KeyError as e:
        logging.error(f"Missing key in recharge data: {e}")
        return f"Error formatting recharge notification: missing {e}"


def format_test_notification(lang: str, timestamp: str) -> str:
    """Format a test notification message.
    
    Args:
        lang: Language code ('zh' or 'en')
        timestamp: Current timestamp
    
    Returns:
        Formatted test notification message
    """
    if lang not in TEMPLATES:
        lang = 'zh'
    
    template = TEMPLATES[lang]['test_notification']
    return template.format(timestamp=timestamp)


def send_order_group_notification(
    context: CallbackContext,
    order_data: Dict,
    lang: str = 'zh'
) -> bool:
    """Send an order notification to the agent's group.
    
    Args:
        context: CallbackContext to get agent info
        order_data: Order information dictionary
        lang: Language code ('zh' or 'en')
    
    Returns:
        True if sent successfully
    """
    try:
        message = format_order_notification(lang, order_data)
        return send_agent_group_message(context, message)
    except Exception as e:
        logging.error(f"Error sending order group notification: {e}")
        return False


def send_recharge_group_notification(
    context: CallbackContext,
    recharge_data: Dict,
    lang: str = 'zh'
) -> bool:
    """Send a recharge notification to the agent's group.
    
    Args:
        context: CallbackContext to get agent info
        recharge_data: Recharge information dictionary
        lang: Language code ('zh' or 'en')
    
    Returns:
        True if sent successfully
    """
    try:
        message = format_recharge_notification(lang, recharge_data)
        return send_agent_group_message(context, message)
    except Exception as e:
        logging.error(f"Error sending recharge group notification: {e}")
        return False
