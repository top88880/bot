"""Message utilities for safe HTML sending."""

import logging
import html
from telegram import Bot, ParseMode
from telegram.error import BadRequest


def safe_send_html(
    bot: Bot,
    chat_id: int,
    text: str,
    **kwargs
) -> bool:
    """Send a message with HTML parsing, falling back to escaped text on failure.
    
    This prevents batch notification failures due to malformed HTML in
    admin-configurable texts.
    
    Args:
        bot: Telegram Bot instance.
        chat_id: Chat ID to send to.
        text: Message text (may contain HTML).
        **kwargs: Additional arguments to pass to send_message.
    
    Returns:
        bool: True if sent successfully.
    """
    try:
        # First try with HTML parse mode
        bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            **kwargs
        )
        return True
        
    except BadRequest as e:
        # If HTML parsing fails, escape the text and try again
        logging.warning(
            f"HTML parsing failed for message to {chat_id}: {e}. "
            "Falling back to escaped text."
        )
        
        try:
            escaped_text = html.escape(text)
            bot.send_message(
                chat_id=chat_id,
                text=escaped_text,
                parse_mode=None,
                **kwargs
            )
            return True
            
        except Exception as e2:
            logging.error(f"Failed to send message to {chat_id}: {e2}")
            return False
    
    except Exception as e:
        logging.error(f"Failed to send message to {chat_id}: {e}")
        return False
