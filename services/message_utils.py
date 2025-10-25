"""Message utilities for safe HTML sending and editing."""

import logging
import html
from telegram import Bot, ParseMode
from telegram.error import BadRequest, TelegramError


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


def safe_edit_message_text(query, text, parse_mode='HTML', reply_markup=None, **kwargs):
    """Safely edit a message, handling 'Message is not modified' errors.
    
    This wrapper prevents errors when trying to edit a message with identical
    content or when only the keyboard has changed.
    
    Args:
        query: CallbackQuery object
        text: New message text
        parse_mode: Parse mode for the text (default: 'HTML')
        reply_markup: New reply markup (optional)
        **kwargs: Additional arguments to pass to edit_message_text
    
    Returns:
        bool: True if edited successfully or no change needed, False on error
    """
    try:
        query.edit_message_text(
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs
        )
        return True
        
    except BadRequest as e:
        error_message = str(e).lower()
        
        # Handle "message is not modified" error
        if "message is not modified" in error_message:
            logging.debug(f"Message not modified for user {query.from_user.id}, skipping edit")
            
            # If only keyboard changed, try to update just the markup
            if reply_markup and "specified new message content and reply markup are exactly the same" not in error_message:
                try:
                    query.edit_message_reply_markup(reply_markup=reply_markup)
                    return True
                except Exception as e2:
                    logging.debug(f"Could not update reply markup: {e2}")
            
            # Not actually an error - message is already in desired state
            return True
        
        # Other BadRequest errors
        logging.error(f"BadRequest error editing message: {e}")
        return False
        
    except TelegramError as e:
        logging.error(f"Telegram error editing message: {e}")
        return False
        
    except Exception as e:
        logging.error(f"Unexpected error editing message: {e}")
        return False
