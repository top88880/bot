"""Agent wallet handlers.

This module provides handlers for agents to view their balance,
request withdrawals, and check withdrawal status.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from services.earnings_service import (
    get_agent_balance, request_withdrawal, list_withdrawals
)
from services.agent_service import get_agent_by_id
from models.constants import WITHDRAWAL_STATUS_REQUESTED
from mongo import bot_db


def agent_wallet_panel(update: Update, context: CallbackContext):
    """Show agent wallet panel with balance and withdrawal options.
    
    This is shown to agents when they access their wallet.
    """
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
        # Get agent context from bot_data
        agent_id = context.bot_data.get('agent_id')
        if not agent_id:
            # Not an agent bot, should not happen
            text = "❌ This feature is only available for agent bots."
            if is_callback:
                query.edit_message_text(text)
            else:
                update.message.reply_text(text)
            return
        
        # Get balance
        ledger_collection = bot_db['agent_ledger']
        balances = get_agent_balance(ledger_collection, agent_id)
        
        # Get agent info for min withdrawal
        agents_collection = bot_db['agents']
        agent = get_agent_by_id(agents_collection, agent_id)
        min_withdrawal = agent.get('payout', {}).get('min_withdrawal', 10)
        
        text = (
            "<b>💰 Agent Wallet</b>\n\n"
            f"<b>Available Balance:</b> {balances['available']:.2f} USDT\n"
            f"<b>Pending Balance:</b> {balances['pending']:.2f} USDT\n"
            f"<b>Already Withdrawn:</b> {balances['withdrawn']:.2f} USDT\n"
            f"<b>Total Earned:</b> {balances['total_earned']:.2f} USDT\n\n"
            f"<b>Minimum Withdrawal:</b> {min_withdrawal} USDT\n\n"
            f"💡 Pending balance becomes available after 48 hours."
        )
        
        keyboard = [
            [InlineKeyboardButton(
                "💸 Request Withdrawal",
                callback_data="agent_withdraw_request"
            )],
            [InlineKeyboardButton(
                "📋 My Withdrawals",
                callback_data="agent_withdraw_list"
            )],
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
        logging.error(f"Error in agent_wallet_panel: {e}")
        error_text = f"❌ Error loading wallet: {e}"
        if is_callback:
            query.edit_message_text(error_text)
        else:
            update.message.reply_text(error_text)


def agent_withdraw_request_callback(update: Update, context: CallbackContext):
    """Initiate withdrawal request flow."""
    query = update.callback_query
    query.answer()
    
    try:
        agent_id = context.bot_data.get('agent_id')
        if not agent_id:
            query.edit_message_text("❌ Agent context not found")
            return
        
        # Get available balance
        ledger_collection = bot_db['agent_ledger']
        balances = get_agent_balance(ledger_collection, agent_id)
        available = balances['available']
        
        # Get min withdrawal
        agents_collection = bot_db['agents']
        agent = get_agent_by_id(agents_collection, agent_id)
        min_withdrawal = agent.get('payout', {}).get('min_withdrawal', 10)
        wallet_address = agent.get('payout', {}).get('wallet_address')
        
        if available < min_withdrawal:
            query.edit_message_text(
                f"❌ Insufficient balance.\n\n"
                f"Available: {available:.2f} USDT\n"
                f"Minimum: {min_withdrawal} USDT"
            )
            return
        
        if not wallet_address:
            query.edit_message_text(
                "❌ Please set your payout wallet address first.\n\n"
                "Contact admin to configure your wallet address."
            )
            return
        
        # Store request state in user_data
        context.user_data['agent_withdraw_state'] = 'awaiting_amount'
        context.user_data['agent_withdraw_max'] = available
        context.user_data['agent_withdraw_min'] = min_withdrawal
        
        text = (
            "<b>💸 Withdrawal Request</b>\n\n"
            f"<b>Available Balance:</b> {available:.2f} USDT\n"
            f"<b>Minimum Withdrawal:</b> {min_withdrawal} USDT\n"
            f"<b>Payout Wallet:</b> <code>{wallet_address}</code>\n\n"
            "Please reply with the amount you want to withdraw (in USDT):"
        )
        
        keyboard = [[
            InlineKeyboardButton("❌ Cancel", callback_data="agent_wallet_panel")
        ]]
        
        query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in agent_withdraw_request_callback: {e}")
        query.edit_message_text(f"❌ Error: {e}")


def agent_withdraw_amount_handler(update: Update, context: CallbackContext):
    """Handle withdrawal amount input from agent."""
    # Check if in withdrawal flow
    if context.user_data.get('agent_withdraw_state') != 'awaiting_amount':
        return
    
    try:
        agent_id = context.bot_data.get('agent_id')
        if not agent_id:
            return
        
        # Parse amount
        try:
            amount = float(update.message.text.strip())
        except ValueError:
            update.message.reply_text("❌ Invalid amount. Please enter a number.")
            return
        
        # Validate amount
        min_withdrawal = context.user_data.get('agent_withdraw_min', 10)
        max_withdrawal = context.user_data.get('agent_withdraw_max', 0)
        
        if amount < min_withdrawal:
            update.message.reply_text(
                f"❌ Amount too low. Minimum: {min_withdrawal} USDT"
            )
            return
        
        if amount > max_withdrawal:
            update.message.reply_text(
                f"❌ Amount exceeds available balance: {max_withdrawal:.2f} USDT"
            )
            return
        
        # Get wallet address
        agents_collection = bot_db['agents']
        agent = get_agent_by_id(agents_collection, agent_id)
        wallet_address = agent.get('payout', {}).get('wallet_address')
        
        # Create withdrawal request
        withdrawals_collection = bot_db['agent_withdrawals']
        ledger_collection = bot_db['agent_ledger']
        
        withdrawal = request_withdrawal(
            withdrawals_collection,
            ledger_collection,
            agent_id,
            amount,
            wallet_address
        )
        
        if not withdrawal:
            update.message.reply_text("❌ Failed to create withdrawal request")
            return
        
        # Clear state
        context.user_data.pop('agent_withdraw_state', None)
        context.user_data.pop('agent_withdraw_max', None)
        context.user_data.pop('agent_withdraw_min', None)
        
        update.message.reply_text(
            f"✅ Withdrawal request submitted!\n\n"
            f"<b>Amount:</b> {amount:.2f} USDT\n"
            f"<b>Wallet:</b> <code>{wallet_address}</code>\n"
            f"<b>Request ID:</b> <code>{withdrawal['_id']}</code>\n\n"
            "Your request will be reviewed by admin.",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logging.error(f"Error in agent_withdraw_amount_handler: {e}")
        update.message.reply_text(f"❌ Error processing withdrawal: {e}")


def agent_withdraw_list_callback(update: Update, context: CallbackContext):
    """Show agent's withdrawal history."""
    query = update.callback_query
    query.answer()
    
    try:
        agent_id = context.bot_data.get('agent_id')
        if not agent_id:
            query.edit_message_text("❌ Agent context not found")
            return
        
        withdrawals_collection = bot_db['agent_withdrawals']
        withdrawals = list_withdrawals(withdrawals_collection, agent_id=agent_id)
        
        if not withdrawals:
            query.edit_message_text(
                "No withdrawal requests found.\n\n"
                "Use 'Request Withdrawal' to create one."
            )
            return
        
        text = "<b>📋 My Withdrawals</b>\n\n"
        
        for w in withdrawals[:10]:  # Last 10
            amount = w['amount']
            status = w['status']
            requested_at = w['requested_at'].strftime('%Y-%m-%d %H:%M')
            
            status_emoji = {
                WITHDRAWAL_STATUS_REQUESTED: '⏳',
                'approved': '✅',
                'paid': '💰',
                'rejected': '❌'
            }.get(status, '❓')
            
            text += (
                f"{status_emoji} <b>{amount:.2f} USDT</b> - {status}\n"
                f"  Requested: {requested_at}\n"
            )
            
            if status == 'paid' and w.get('txid'):
                text += f"  TXID: <code>{w['txid']}</code>\n"
            
            if status == 'rejected' and w.get('admin_note'):
                text += f"  Reason: {w['admin_note']}\n"
            
            text += "\n"
        
        keyboard = [[
            InlineKeyboardButton("⬅️ Back to Wallet", callback_data="agent_wallet_panel")
        ]]
        
        query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in agent_withdraw_list_callback: {e}")
        query.edit_message_text(f"❌ Error loading withdrawals: {e}")
