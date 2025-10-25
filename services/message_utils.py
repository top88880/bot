"""Message utilities for safe HTML sending and editing."""

import logging
import html
import hashlib
from telegram import Bot, ParseMode, InlineKeyboardMarkup
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


def compute_view_key(text: str, keyboard: InlineKeyboardMarkup = None) -> str:
    """Compute a stable hash key for a view (text + keyboard).
    
    This is used for de-duplication to avoid redundant edits.
    Uses SHA-256 for better security practices.
    
    Args:
        text: Message text
        keyboard: InlineKeyboardMarkup (optional)
    
    Returns:
        str: SHA-256 hash of the view
    """
    content = text
    if keyboard:
        # Serialize keyboard to stable string representation
        kb_data = []
        for row in keyboard.inline_keyboard:
            row_data = []
            for button in row:
                # Include text and callback_data/url
                row_data.append((button.text, button.callback_data or button.url or ''))
            kb_data.append(tuple(row_data))
        content += str(tuple(kb_data))
    
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def deduplicate_keyboard(keyboard: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    """Remove duplicate buttons from keyboard by callback_data/url.
    
    Args:
        keyboard: InlineKeyboardMarkup to deduplicate
    
    Returns:
        InlineKeyboardMarkup: Deduplicated keyboard
    """
    if not keyboard or not keyboard.inline_keyboard:
        return keyboard
    
    new_rows = []
    for row in keyboard.inline_keyboard:
        seen = set()
        new_row = []
        for button in row:
            # Use callback_data or url as unique identifier
            identifier = button.callback_data or button.url or button.text
            if identifier not in seen:
                seen.add(identifier)
                new_row.append(button)
        if new_row:
            new_rows.append(new_row)
    
    return InlineKeyboardMarkup(new_rows)


def safe_edit_message_text(query, text, parse_mode='HTML', reply_markup=None, 
                           context=None, view_name=None, **kwargs):
    """Safely edit a message, handling 'Message is not modified' errors.
    
    This wrapper prevents errors when trying to edit a message with identical
    content or when only the keyboard has changed. It also supports view 
    de-duplication to avoid redundant edits.
    
    Args:
        query: CallbackQuery object
        text: New message text
        parse_mode: Parse mode for the text (default: 'HTML')
        reply_markup: New reply markup (optional)
        context: CallbackContext for storing view keys (optional)
        view_name: Name of the view for de-duplication (optional)
        **kwargs: Additional arguments to pass to edit_message_text
    
    Returns:
        bool: True if edited successfully or no change needed, False on error
    """
    # Deduplicate keyboard if provided
    if reply_markup:
        reply_markup = deduplicate_keyboard(reply_markup)
    
    # Check if view is unchanged (de-duplication)
    if context and view_name:
        view_key = compute_view_key(text, reply_markup)
        
        # Initialize chat_data if needed
        if not hasattr(context, 'chat_data') or context.chat_data is None:
            context.chat_data = {}
        
        stored_key = context.chat_data.get(f'view_key_{view_name}')
        
        if stored_key == view_key:
            # View hasn't changed, just answer callback
            try:
                lang = context.chat_data.get('lang', 'zh')
                if lang == 'zh':
                    query.answer("已是最新", show_alert=False)
                else:
                    query.answer("Up to date", show_alert=False)
            except TelegramError as e:
                logging.debug(f"Could not answer callback for unchanged view: {e}")
            return True
        
        # Store new view key
        context.chat_data[f'view_key_{view_name}'] = view_key
    
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
            
            # Answer callback to acknowledge
            try:
                query.answer()
            except TelegramError as e_answer:
                logging.debug(f"Could not answer callback: {e_answer}")
            
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


def maybe_answer_latest(query, lang='zh'):
    """Answer callback query with 'Up to date' message.
    
    This is a lightweight response when no edit is needed.
    
    Args:
        query: CallbackQuery object
        lang: Language ('zh' or 'en')
    """
    try:
        if lang == 'zh':
            query.answer("已是最新", show_alert=False)
        else:
            query.answer("Up to date", show_alert=False)
    except (TelegramError, BadRequest) as e:
        logging.debug(f"Could not answer callback: {e}")
