"""Admin handlers for agent withdrawal management.

This module provides admin commands and callbacks for approving, rejecting,
and processing agent withdrawal requests.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from bson import ObjectId

from services.earnings_service import (
    list_withdrawals, approve_withdrawal, reject_withdrawal, 
    mark_withdrawal_paid, get_agent_balance
)
from models.constants import (
    WITHDRAWAL_STATUS_REQUESTED, WITHDRAWAL_STATUS_APPROVED,
    WITHDRAWAL_STATUS_PAID, WITHDRAWAL_STATUS_REJECTED
)
from mongo import bot_db


def withdraw_list_command(update: Update, context: CallbackContext):
    """Handle /withdraw_list command to list withdrawal requests.
    
    Usage: /withdraw_list [status]
    Status can be: requested, approved, paid, rejected
    """
    try:
        args = context.args
        status = args[0] if args else WITHDRAWAL_STATUS_REQUESTED
        
        if status not in [WITHDRAWAL_STATUS_REQUESTED, WITHDRAWAL_STATUS_APPROVED, 
                         WITHDRAWAL_STATUS_PAID, WITHDRAWAL_STATUS_REJECTED]:
            update.message.reply_text(
                "❌ Invalid status. Use: requested, approved, paid, or rejected"
            )
            return
        
        withdrawals_collection = bot_db['agent_withdrawals']
        withdrawals = list_withdrawals(withdrawals_collection, status=status)
        
        if not withdrawals:
            update.message.reply_text(f"No withdrawals with status '{status}'")
            return
        
        text = f"<b>💰 Withdrawal Requests ({status})</b>\n\n"
        
        for w in withdrawals[:20]:  # Limit to first 20
            agent_id = w['agent_id']
            amount = w['amount']
            wallet = w['wallet_address']
            requested_at = w['requested_at'].strftime('%Y-%m-%d %H:%M')
            w_id = str(w['_id'])
            
            text += (
                f"<b>Agent:</b> {agent_id}\n"
                f"<b>Amount:</b> {amount} USDT\n"
                f"<b>Wallet:</b> <code>{wallet}</code>\n"
                f"<b>Requested:</b> {requested_at}\n"
                f"<b>ID:</b> <code>{w_id}</code>\n"
            )
            
            if status == WITHDRAWAL_STATUS_PAID:
                text += f"<b>TXID:</b> <code>{w.get('txid', 'N/A')}</code>\n"
            
            text += "\n"
        
        if len(withdrawals) > 20:
            text += f"\n... and {len(withdrawals) - 20} more"
        
        update.message.reply_text(text, parse_mode='HTML')
        
    except Exception as e:
        logging.error(f"Error in withdraw_list_command: {e}")
        update.message.reply_text(f"❌ Error listing withdrawals: {e}")


def withdraw_approve_command(update: Update, context: CallbackContext):
    """Handle /withdraw_approve command to approve a withdrawal.
    
    Usage: /withdraw_approve <withdrawal_id>
    """
    try:
        args = context.args
        if len(args) < 1:
            update.message.reply_text("❌ Usage: /withdraw_approve <withdrawal_id>")
            return
        
        withdrawal_id_str = args[0]
        
        try:
            withdrawal_id = ObjectId(withdrawal_id_str)
        except:
            update.message.reply_text("❌ Invalid withdrawal ID")
            return
        
        withdrawals_collection = bot_db['agent_withdrawals']
        admin_id = update.effective_user.id
        
        success = approve_withdrawal(withdrawals_collection, withdrawal_id, admin_id)
        
        if success:
            update.message.reply_text(
                f"✅ Withdrawal approved!\n\n"
                f"Next step: Process payment and use\n"
                f"/withdraw_pay {withdrawal_id_str} <txid>"
            )
        else:
            update.message.reply_text(
                f"❌ Failed to approve withdrawal. "
                f"It may not exist or already be processed."
            )
        
    except Exception as e:
        logging.error(f"Error in withdraw_approve_command: {e}")
        update.message.reply_text(f"❌ Error approving withdrawal: {e}")


def withdraw_reject_command(update: Update, context: CallbackContext):
    """Handle /withdraw_reject command to reject a withdrawal.
    
    Usage: /withdraw_reject <withdrawal_id> [reason]
    """
    try:
        args = context.args
        if len(args) < 1:
            update.message.reply_text(
                "❌ Usage: /withdraw_reject <withdrawal_id> [reason]"
            )
            return
        
        withdrawal_id_str = args[0]
        reason = ' '.join(args[1:]) if len(args) > 1 else None
        
        try:
            withdrawal_id = ObjectId(withdrawal_id_str)
        except:
            update.message.reply_text("❌ Invalid withdrawal ID")
            return
        
        withdrawals_collection = bot_db['agent_withdrawals']
        admin_id = update.effective_user.id
        
        success = reject_withdrawal(withdrawals_collection, withdrawal_id, admin_id, reason)
        
        if success:
            update.message.reply_text(
                f"✅ Withdrawal rejected.\n"
                f"Reason: {reason or 'No reason provided'}"
            )
        else:
            update.message.reply_text(
                f"❌ Failed to reject withdrawal. "
                f"It may not exist or already be processed."
            )
        
    except Exception as e:
        logging.error(f"Error in withdraw_reject_command: {e}")
        update.message.reply_text(f"❌ Error rejecting withdrawal: {e}")


def withdraw_pay_command(update: Update, context: CallbackContext):
    """Handle /withdraw_pay command to mark withdrawal as paid.
    
    Usage: /withdraw_pay <withdrawal_id> <txid>
    """
    try:
        args = context.args
        if len(args) < 2:
            update.message.reply_text(
                "❌ Usage: /withdraw_pay <withdrawal_id> <txid>"
            )
            return
        
        withdrawal_id_str = args[0]
        txid = args[1]
        
        try:
            withdrawal_id = ObjectId(withdrawal_id_str)
        except:
            update.message.reply_text("❌ Invalid withdrawal ID")
            return
        
        withdrawals_collection = bot_db['agent_withdrawals']
        ledger_collection = bot_db['agent_ledger']
        admin_id = update.effective_user.id
        
        success = mark_withdrawal_paid(
            withdrawals_collection,
            ledger_collection,
            withdrawal_id,
            txid,
            admin_id
        )
        
        if success:
            update.message.reply_text(
                f"✅ Withdrawal marked as paid!\n\n"
                f"<b>TXID:</b> <code>{txid}</code>\n\n"
                f"Ledger entries have been updated.",
                parse_mode='HTML'
            )
        else:
            update.message.reply_text(
                f"❌ Failed to mark withdrawal as paid. "
                f"Check that it's approved and not already processed."
            )
        
    except Exception as e:
        logging.error(f"Error in withdraw_pay_command: {e}")
        update.message.reply_text(f"❌ Error processing payment: {e}")


def withdraw_panel_callback(update: Update, context: CallbackContext):
    """Show withdrawal management panel."""
    query = update.callback_query
    query.answer()
    
    try:
        withdrawals_collection = bot_db['agent_withdrawals']
        
        # Count withdrawals by status
        requested_count = withdrawals_collection.count_documents({
            'status': WITHDRAWAL_STATUS_REQUESTED
        })
        approved_count = withdrawals_collection.count_documents({
            'status': WITHDRAWAL_STATUS_APPROVED
        })
        
        text = (
            "<b>💰 Withdrawal Management</b>\n\n"
            f"<b>Pending Review:</b> {requested_count}\n"
            f"<b>Approved (awaiting payment):</b> {approved_count}\n\n"
            "Commands:\n"
            "  /withdraw_list [status] - List withdrawals\n"
            "  /withdraw_approve <id> - Approve\n"
            "  /withdraw_reject <id> [reason] - Reject\n"
            "  /withdraw_pay <id> <txid> - Mark paid\n"
        )
        
        keyboard = [
            [InlineKeyboardButton(
                f"📋 Pending ({requested_count})",
                callback_data="withdraw_view_requested"
            )],
            [InlineKeyboardButton(
                f"✅ Approved ({approved_count})",
                callback_data="withdraw_view_approved"
            )],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="backstart")],
            [InlineKeyboardButton("❌ Close", callback_data=f"close {query.from_user.id}")]
        ]
        
        query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in withdraw_panel_callback: {e}")
        query.edit_message_text(f"❌ Error loading withdrawal panel: {e}")


def withdraw_view_callback(update: Update, context: CallbackContext):
    """Show withdrawal list with action buttons."""
    query = update.callback_query
    query.answer()
    
    try:
        # Parse status from callback data
        status = query.data.split('_')[-1]  # e.g., "withdraw_view_requested" -> "requested"
        
        withdrawals_collection = bot_db['agent_withdrawals']
        withdrawals = list_withdrawals(withdrawals_collection, status=status)
        
        if not withdrawals:
            query.edit_message_text(
                f"No {status} withdrawals found.\n\n"
                "Use /withdraw_list to see all withdrawals."
            )
            return
        
        text = f"<b>💰 {status.title()} Withdrawals</b>\n\n"
        keyboard = []
        
        for w in withdrawals[:10]:  # Limit to 10
            agent_id = w['agent_id']
            amount = w['amount']
            requested_at = w['requested_at'].strftime('%m-%d %H:%M')
            w_id_short = str(w['_id'])[-8:]  # Last 8 chars for display
            
            text += (
                f"• {agent_id}: {amount} USDT ({requested_at})\n"
                f"  ID: ...{w_id_short}\n"
            )
            
            if status == WITHDRAWAL_STATUS_REQUESTED:
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ Approve {agent_id}",
                        callback_data=f"withdraw_approve {w['_id']}"
                    )
                ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="withdraw_panel")])
        keyboard.append([InlineKeyboardButton("❌ Close", callback_data=f"close {query.from_user.id}")])
        
        query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in withdraw_view_callback: {e}")
        query.edit_message_text(f"❌ Error loading withdrawals: {e}")
