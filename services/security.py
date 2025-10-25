"""Security utilities for bot.

This module provides security functions for protecting sensitive data,
particularly in multi-tenant agent environments.
"""

import logging
from typing import Dict, Any, List


# List of sensitive keys to redact from order payloads
SENSITIVE_KEYS = [
    'credentials',
    'credential',
    'files',
    'file',
    'password',
    'passwords',
    'secret',
    'secrets',
    'deliverables',
    'deliverable',
    'session',
    'sessions',
    'json',
    'token',
    'tokens',
    'keys',
    'key',
    'api_key',
    'api_keys',
    'access_token',
    'refresh_token',
    'private_key',
    'auth',
    'authorization',
    'cookie',
    'cookies',
    'account_data',
    'account_info',
    'login_info',
    'user_data',
    'payload',
]


def redact_order_payload(order_doc: Dict[str, Any], is_child_agent: bool = True) -> Dict[str, Any]:
    """Redact sensitive fields from an order document for child agent viewing.
    
    This function removes all sensitive customer deliverables (account files,
    credentials, sessions, passwords, etc.) while preserving non-sensitive
    metadata like product name, quantity, prices, and timestamps.
    
    Args:
        order_doc: Order document from MongoDB
        is_child_agent: If True, applies redaction. If False, returns original.
    
    Returns:
        Redacted copy of order document safe for child agent viewing
    """
    if not is_child_agent:
        # Main bot admins can see everything
        return order_doc
    
    if not order_doc:
        return order_doc
    
    # Create a shallow copy to avoid modifying original
    redacted = dict(order_doc)
    
    # Remove sensitive top-level keys
    for key in list(redacted.keys()):
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
            redacted[key] = "**REDACTED**"
            logging.debug(f"Redacted sensitive key: {key}")
    
    # Handle nested items array (common in order documents)
    if 'items' in redacted and isinstance(redacted['items'], list):
        redacted_items = []
        for item in redacted['items']:
            if isinstance(item, dict):
                redacted_item = dict(item)
                
                # Keep only non-sensitive fields
                allowed_fields = [
                    'product_id',
                    'product_name',
                    'category',
                    'quantity',
                    'qty',
                    'unit_price',
                    'price',
                    'subtotal',
                    'total',
                    'sku',
                    'description',
                ]
                
                # Remove sensitive fields from item
                for key in list(redacted_item.keys()):
                    key_lower = key.lower()
                    # Remove if sensitive or not in allowed list
                    if any(sensitive in key_lower for sensitive in SENSITIVE_KEYS):
                        redacted_item[key] = "**REDACTED**"
                    elif 'payload' in key_lower or 'data' in key_lower:
                        # These often contain deliverables
                        redacted_item[key] = "**REDACTED**"
                
                redacted_items.append(redacted_item)
            else:
                redacted_items.append(item)
        
        redacted['items'] = redacted_items
    
    # Add redaction notice
    redacted['_redacted'] = True
    redacted['_redaction_note'] = "Sensitive customer data redacted for agent viewing"
    
    return redacted


def is_agent_context(context: Any) -> bool:
    """Check if the current context is a child agent bot.
    
    Args:
        context: Telegram CallbackContext or similar with bot_data
    
    Returns:
        True if this is a child agent bot, False if main bot
    """
    try:
        agent_id = context.bot_data.get('agent_id')
        return agent_id is not None
    except (AttributeError, KeyError):
        return False


def redact_order_list(orders: List[Dict[str, Any]], is_child_agent: bool = True) -> List[Dict[str, Any]]:
    """Redact sensitive fields from a list of order documents.
    
    Args:
        orders: List of order documents
        is_child_agent: If True, applies redaction
    
    Returns:
        List of redacted order documents
    """
    if not is_child_agent:
        return orders
    
    return [redact_order_payload(order, is_child_agent=True) for order in orders]


def get_permission_denied_message(lang: str = 'zh') -> str:
    """Get a permission denied message for blocked actions.
    
    Args:
        lang: Language code ('zh' or 'en')
    
    Returns:
        Localized permission denied message
    """
    messages = {
        'zh': '❌ 无权限\n\n您没有权限访问此敏感数据。\n\n代理机器人只能查看订单和充值的统计信息，不能访问客户账号、文件或凭证。',
        'en': '❌ No Permission\n\nYou do not have permission to access this sensitive data.\n\nAgent bots can only view order and recharge statistics, not customer accounts, files, or credentials.'
    }
    
    return messages.get(lang, messages['zh'])


def should_block_download(context: Any, file_type: str = 'account') -> bool:
    """Check if file download should be blocked for current context.
    
    Args:
        context: Telegram CallbackContext
        file_type: Type of file being accessed
    
    Returns:
        True if download should be blocked (child agent), False otherwise
    """
    # Block all sensitive file downloads for child agents
    if is_agent_context(context):
        logging.warning(f"Blocked {file_type} download attempt in child agent context")
        return True
    
    return False
