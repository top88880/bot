"""Agent panel handlers.

This module provides self-service panels for agents to manage their
pricing and view statistics.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from services.agent_service import get_agent_by_id, update_agent_pricing
from services.earnings_service import get_agent_balance
from models.constants import MARKUP_TYPE_PERCENT, MARKUP_TYPE_FIXED
from mongo import bot_db


def agent_panel(update: Update, context: CallbackContext):
    """Show agent control panel."""
    # Determine if this is from a message or callback
    if update.callback_query:
        query = update.callback_query
        query.answer()
        user_id = query.from_user.id
        is_callback = True
    else:
        user_id = update.effective_user.id
        is_callback = False
    
    try:
        # Get agent context
        agent_id = context.bot_data.get('agent_id')
        if not agent_id:
            text = "❌ This feature is only available for agent bots."
            if is_callback:
                query.edit_message_text(text)
            else:
                update.message.reply_text(text)
            return
        
        # Get agent info
        agents_collection = bot_db['agents']
        agent = get_agent_by_id(agents_collection, agent_id)
        
        if not agent:
            text = "❌ Agent information not found"
            if is_callback:
                query.edit_message_text(text)
            else:
                update.message.reply_text(text)
            return
        
        # Get earnings
        ledger_collection = bot_db['agent_ledger']
        balances = get_agent_balance(ledger_collection, agent_id)
        
        # Get pricing info
        pricing = agent.get('pricing', {})
        markup_type = pricing.get('markup_type', MARKUP_TYPE_PERCENT)
        markup_value = pricing.get('markup_value', 0)
        
        text = (
            f"<b>🤖 Agent Panel</b>\n\n"
            f"<b>Agent ID:</b> <code>{agent_id}</code>\n"
            f"<b>Name:</b> {agent.get('name', 'N/A')}\n"
            f"<b>Status:</b> {agent.get('status', 'unknown')}\n\n"
            f"<b>💰 Earnings</b>\n"
            f"  • Available: {balances['available']:.2f} USDT\n"
            f"  • Pending: {balances['pending']:.2f} USDT\n"
            f"  • Total: {balances['total_earned']:.2f} USDT\n\n"
            f"<b>💵 Pricing</b>\n"
            f"  • Markup Type: {markup_type}\n"
            f"  • Markup Value: {markup_value}"
            f"{'%' if markup_type == MARKUP_TYPE_PERCENT else ' USDT'}\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("💰 Wallet", callback_data="agent_wallet_panel")],
            [InlineKeyboardButton("💵 Set Pricing", callback_data="agent_pricing_menu")],
            [InlineKeyboardButton("❌ Close", callback_data=f"close {user_id}")]
        ]
        
        if is_callback:
            query.edit_message_text(
                text=text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            update.message.reply_text(
                text=text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
    except Exception as e:
        logging.error(f"Error in agent_panel: {e}")
        error_text = f"❌ Error loading agent panel: {e}"
        if is_callback:
            query.edit_message_text(error_text)
        else:
            update.message.reply_text(error_text)


def agent_pricing_menu_callback(update: Update, context: CallbackContext):
    """Show pricing configuration menu."""
    query = update.callback_query
    query.answer()
    
    try:
        agent_id = context.bot_data.get('agent_id')
        if not agent_id:
            query.edit_message_text("❌ Agent context not found")
            return
        
        text = (
            "<b>💵 Set Your Pricing</b>\n\n"
            "Choose your markup type:\n\n"
            "<b>Percentage:</b> Markup as % of base price\n"
            "  Example: 10% markup on 100 USDT item = 110 USDT\n\n"
            "<b>Fixed:</b> Fixed amount per item\n"
            "  Example: 5 USDT markup on 100 USDT item = 105 USDT\n"
        )
        
        keyboard = [
            [InlineKeyboardButton(
                "📊 Percentage Markup",
                callback_data="agent_pricing_type_percent"
            )],
            [InlineKeyboardButton(
                "💵 Fixed Markup",
                callback_data="agent_pricing_type_fixed"
            )],
            [InlineKeyboardButton("⬅️ Back", callback_data="agent_panel")],
            [InlineKeyboardButton("❌ Close", callback_data=f"close {query.from_user.id}")]
        ]
        
        query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in agent_pricing_menu_callback: {e}")
        query.edit_message_text(f"❌ Error: {e}")


def agent_pricing_type_callback(update: Update, context: CallbackContext):
    """Handle pricing type selection."""
    query = update.callback_query
    query.answer()
    
    try:
        # Parse type from callback data
        markup_type = query.data.split('_')[-1]  # "percent" or "fixed"
        
        # Store in user_data
        context.user_data['agent_pricing_type'] = markup_type
        context.user_data['agent_pricing_state'] = 'awaiting_value'
        
        if markup_type == MARKUP_TYPE_PERCENT:
            text = (
                "<b>📊 Percentage Markup</b>\n\n"
                "Please reply with the markup percentage.\n\n"
                "Example: <code>10</code> for 10% markup\n"
                "Example: <code>5.5</code> for 5.5% markup"
            )
        else:  # fixed
            text = (
                "<b>💵 Fixed Markup</b>\n\n"
                "Please reply with the fixed markup amount in USDT.\n\n"
                "Example: <code>5</code> for 5 USDT markup\n"
                "Example: <code>2.50</code> for 2.50 USDT markup"
            )
        
        keyboard = [[
            InlineKeyboardButton("❌ Cancel", callback_data="agent_pricing_menu")
        ]]
        
        query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in agent_pricing_type_callback: {e}")
        query.edit_message_text(f"❌ Error: {e}")


def agent_pricing_value_handler(update: Update, context: CallbackContext):
    """Handle pricing value input from agent."""
    # Check if in pricing flow
    if context.user_data.get('agent_pricing_state') != 'awaiting_value':
        return
    
    try:
        agent_id = context.bot_data.get('agent_id')
        if not agent_id:
            return
        
        markup_type = context.user_data.get('agent_pricing_type')
        if not markup_type:
            return
        
        # Parse value
        try:
            markup_value = float(update.message.text.strip())
        except ValueError:
            update.message.reply_text("❌ Invalid value. Please enter a number.")
            return
        
        # Validate value
        if markup_value < 0:
            update.message.reply_text("❌ Markup value cannot be negative.")
            return
        
        if markup_type == MARKUP_TYPE_PERCENT and markup_value > 100:
            update.message.reply_text("❌ Percentage markup cannot exceed 100%.")
            return
        
        # Update pricing
        agents_collection = bot_db['agents']
        success = update_agent_pricing(
            agents_collection,
            agent_id,
            markup_type,
            markup_value
        )
        
        if not success:
            update.message.reply_text("❌ Failed to update pricing")
            return
        
        # Clear state
        context.user_data.pop('agent_pricing_state', None)
        context.user_data.pop('agent_pricing_type', None)
        
        update.message.reply_text(
            f"✅ Pricing updated!\n\n"
            f"<b>Type:</b> {markup_type}\n"
            f"<b>Value:</b> {markup_value}"
            f"{'%' if markup_type == MARKUP_TYPE_PERCENT else ' USDT'}\n\n"
            f"This will apply to all future sales.",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logging.error(f"Error in agent_pricing_value_handler: {e}")
        update.message.reply_text(f"❌ Error updating pricing: {e}")
