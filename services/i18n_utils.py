"""Centralized i18n (internationalization) utilities for the bot.

This module provides consistent language detection and translation across all views.
"""

import logging
from telegram import Update
from telegram.ext import CallbackContext


def get_locale(update: Update = None, context: CallbackContext = None, user_doc: dict = None) -> str:
    """Get user's preferred language (zh or en).
    
    Priority order:
    1. user_doc['lang'] if provided
    2. Database lookup via user_id
    3. Telegram language_code from update
    4. Default to 'zh'
    
    Args:
        update: Telegram Update object (optional)
        context: CallbackContext (optional, for future use)
        user_doc: User document from database (optional, highest priority)
    
    Returns:
        str: Language code ('zh' or 'en')
    """
    # Check provided user document first
    if user_doc and isinstance(user_doc, dict):
        lang = user_doc.get('lang')
        if lang in ['zh', 'en']:
            return lang
    
    # Try to get from database if we have user_id
    if update and update.effective_user:
        try:
            from mongo import user
            user_id = update.effective_user.id
            user_data = user.find_one({'user_id': user_id})
            if user_data and user_data.get('lang'):
                lang = user_data['lang']
                if lang in ['zh', 'en']:
                    return lang
        except Exception as e:
            logging.debug(f"Could not fetch user language from DB: {e}")
    
    # Check Telegram language code
    if update and update.effective_user and update.effective_user.language_code:
        lang_code = update.effective_user.language_code.lower()
        if lang_code.startswith('zh'):
            return 'zh'
        elif lang_code.startswith('en'):
            return 'en'
    
    # Default to Chinese
    return 'zh'


def set_user_locale(user_id: int, lang: str) -> bool:
    """Persist user's language preference.
    
    Args:
        user_id: Telegram user ID
        lang: Language code ('zh' or 'en')
    
    Returns:
        bool: True if saved successfully
    """
    if lang not in ['zh', 'en']:
        logging.warning(f"Invalid language code: {lang}")
        return False
    
    try:
        from mongo import user
        user.update_one(
            {'user_id': user_id},
            {'$set': {'lang': lang}},
            upsert=False
        )
        return True
    except Exception as e:
        logging.error(f"Failed to set user locale: {e}")
        return False


def render_text(lang: str, key: str, i18n_dict: dict, **kwargs) -> str:
    """Render a translated text with fallback support.
    
    Args:
        lang: Language code ('zh' or 'en')
        key: Translation key
        i18n_dict: Dictionary containing translations {'zh': {...}, 'en': {...}}
        **kwargs: Format parameters for the translation string
    
    Returns:
        str: Translated and formatted string
    """
    # Ensure valid language
    if lang not in i18n_dict:
        lang = 'zh' if 'zh' in i18n_dict else list(i18n_dict.keys())[0]
    
    # Get translation with fallback
    translation = i18n_dict[lang].get(key)
    if translation is None:
        # Fallback to zh, then en, then the key itself
        translation = i18n_dict.get('zh', {}).get(key) or i18n_dict.get('en', {}).get(key) or key
    
    # Format with parameters if provided
    if kwargs:
        try:
            return translation.format(**kwargs)
        except Exception as e:
            logging.error(f"Translation format error for key '{key}': {e}")
            return translation
    
    return translation
