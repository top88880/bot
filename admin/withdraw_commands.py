"""Admin commands for managing agent withdrawals.

This module provides commands for admins to review, approve, and process
agent withdrawal requests.
"""

import logging
from decimal import Decimal
from datetime import datetime
from bson import ObjectId
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from mongo import agents, agent_withdrawals
from bot import is_admin


def withdraw_list_command(update: Update, context: CallbackContext):
    """List agent withdrawal requests.
    
    Usage: /withdraw_list [status]
    Status: pending (default), approved, rejected, all
    """
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 仅管理员可用")
        return
    
    args = context.args
    status_filter = args[0] if args else 'pending'
    
    try:
        # Build query
        query = {}
        if status_filter != 'all':
            query['status'] = status_filter
        
        withdrawals = list(agent_withdrawals.find(query).sort('created_at', -1).limit(20))
        
        if not withdrawals:
            update.message.reply_text(f"📭 没有 {status_filter} 状态的提现申请")
            return
        
        text = f"<b>💰 提现申请列表 - {status_filter}</b>\n\n"
        
        for w in withdrawals:
            request_id = w.get('request_id', str(w['_id']))
            agent_id = w.get('agent_id', 'Unknown')
            amount = w.get('amount_usdt', '0')
            fee = w.get('fee_usdt', '0')
            address = w.get('address', 'N/A')
            status = w.get('status', 'unknown')
            created = w.get('created_at')
            created_str = created.strftime('%Y-%m-%d %H:%M') if created else 'N/A'
            
            text += f"<b>申请ID:</b> <code>{request_id}</code>\n"
            text += f"<b>代理:</b> {agent_id}\n"
            text += f"<b>金额:</b> {amount} USDT (手续费: {fee} USDT)\n"
            text += f"<b>地址:</b> <code>{address}</code>\n"
            text += f"<b>状态:</b> {status}\n"
            text += f"<b>申请时间:</b> {created_str}\n"
            
            if status == 'approved':
                text += f"\n<b>审批命令:</b>\n"
                text += f"<code>/withdraw_pay {request_id} [TXID]</code>\n"
            elif status == 'pending':
                text += f"\n<b>操作命令:</b>\n"
                text += f"<code>/withdraw_approve {request_id}</code>\n"
                text += f"<code>/withdraw_reject {request_id} [理由]</code>\n"
            
            text += "\n---\n\n"
        
        if len(withdrawals) == 20:
            text += "<i>仅显示前20条记录</i>"
        
        update.message.reply_text(text, parse_mode='HTML')
        
    except Exception as e:
        logging.error(f"Error in withdraw_list_command: {e}")
        update.message.reply_text(f"❌ 查询失败: {e}")


def withdraw_approve_command(update: Update, context: CallbackContext):
    """Approve a withdrawal request.
    
    Usage: /withdraw_approve <request_id>
    """
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 仅管理员可用")
        return
    
    args = context.args
    if not args:
        update.message.reply_text(
            "❌ 用法: <code>/withdraw_approve &lt;request_id&gt;</code>",
            parse_mode='HTML'
        )
        return
    
    request_id = args[0]
    
    try:
        # Find the withdrawal
        withdrawal = agent_withdrawals.find_one({'request_id': request_id})
        if not withdrawal:
            update.message.reply_text(f"❌ 未找到申请: {request_id}")
            return
        
        if withdrawal.get('status') != 'pending':
            update.message.reply_text(
                f"❌ 申请状态不是 pending (当前: {withdrawal.get('status')})"
            )
            return
        
        # Approve the withdrawal
        agent_withdrawals.update_one(
            {'request_id': request_id},
            {
                '$set': {
                    'status': 'approved',
                    'reviewed_at': datetime.now(),
                    'reviewed_by': update.effective_user.id
                }
            }
        )
        
        agent_id = withdrawal.get('agent_id')
        amount = withdrawal.get('amount_usdt', '0')
        address = withdrawal.get('address', 'N/A')
        
        update.message.reply_text(
            f"✅ 提现申请已批准\n\n"
            f"<b>申请ID:</b> <code>{request_id}</code>\n"
            f"<b>代理:</b> {agent_id}\n"
            f"<b>金额:</b> {amount} USDT\n"
            f"<b>地址:</b> <code>{address}</code>\n\n"
            f"<b>下一步:</b> 处理付款后使用以下命令标记为已支付:\n"
            f"<code>/withdraw_pay {request_id} [TXID]</code>",
            parse_mode='HTML'
        )
        
        # Notify agent owner if possible
        try:
            owner_user_id = withdrawal.get('owner_user_id')
            if owner_user_id:
                context.bot.send_message(
                    chat_id=owner_user_id,
                    text=f"✅ 您的提现申请已审核通过\n\n"
                         f"<b>申请ID:</b> <code>{request_id}</code>\n"
                         f"<b>金额:</b> {amount} USDT\n"
                         f"<b>地址:</b> <code>{address}</code>\n\n"
                         f"我们将尽快处理付款。",
                    parse_mode='HTML'
                )
        except Exception as e:
            logging.warning(f"Could not notify agent owner: {e}")
        
    except Exception as e:
        logging.error(f"Error in withdraw_approve_command: {e}")
        update.message.reply_text(f"❌ 批准失败: {e}")


def withdraw_reject_command(update: Update, context: CallbackContext):
    """Reject a withdrawal request.
    
    Usage: /withdraw_reject <request_id> [reason]
    """
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 仅管理员可用")
        return
    
    args = context.args
    if not args:
        update.message.reply_text(
            "❌ 用法: <code>/withdraw_reject &lt;request_id&gt; [理由]</code>",
            parse_mode='HTML'
        )
        return
    
    request_id = args[0]
    reason = ' '.join(args[1:]) if len(args) > 1 else '未提供理由'
    
    try:
        # Find the withdrawal
        withdrawal = agent_withdrawals.find_one({'request_id': request_id})
        if not withdrawal:
            update.message.reply_text(f"❌ 未找到申请: {request_id}")
            return
        
        if withdrawal.get('status') != 'pending':
            update.message.reply_text(
                f"❌ 申请状态不是 pending (当前: {withdrawal.get('status')})"
            )
            return
        
        agent_id = withdrawal.get('agent_id')
        amount = Decimal(str(withdrawal.get('amount_usdt', '0')))
        
        # Reject the withdrawal
        agent_withdrawals.update_one(
            {'request_id': request_id},
            {
                '$set': {
                    'status': 'rejected',
                    'reviewed_at': datetime.now(),
                    'reviewed_by': update.effective_user.id,
                    'reject_reason': reason
                }
            }
        )
        
        # Unfreeze the funds (return from frozen to available)
        agent = agents.find_one({'agent_id': agent_id})
        if agent:
            current_available = Decimal(str(agent.get('profit_available_usdt', '0')))
            current_frozen = Decimal(str(agent.get('profit_frozen_usdt', '0')))
            
            new_available = current_available + amount
            new_frozen = current_frozen - amount
            
            agents.update_one(
                {'agent_id': agent_id},
                {
                    '$set': {
                        'profit_available_usdt': str(new_available.quantize(Decimal('0.01'))),
                        'profit_frozen_usdt': str(new_frozen.quantize(Decimal('0.01'))),
                        'updated_at': datetime.now()
                    }
                }
            )
        
        update.message.reply_text(
            f"✅ 提现申请已拒绝\n\n"
            f"<b>申请ID:</b> <code>{request_id}</code>\n"
            f"<b>代理:</b> {agent_id}\n"
            f"<b>金额:</b> {amount} USDT\n"
            f"<b>理由:</b> {reason}\n\n"
            f"<i>冻结的金额已返回可提现余额</i>",
            parse_mode='HTML'
        )
        
        # Notify agent owner if possible
        try:
            owner_user_id = withdrawal.get('owner_user_id')
            if owner_user_id:
                context.bot.send_message(
                    chat_id=owner_user_id,
                    text=f"❌ 您的提现申请已被拒绝\n\n"
                         f"<b>申请ID:</b> <code>{request_id}</code>\n"
                         f"<b>金额:</b> {amount} USDT\n"
                         f"<b>理由:</b> {reason}\n\n"
                         f"<i>资金已返回您的可提现余额</i>",
                    parse_mode='HTML'
                )
        except Exception as e:
            logging.warning(f"Could not notify agent owner: {e}")
        
    except Exception as e:
        logging.error(f"Error in withdraw_reject_command: {e}")
        update.message.reply_text(f"❌ 拒绝失败: {e}")


def withdraw_pay_command(update: Update, context: CallbackContext):
    """Mark a withdrawal as paid.
    
    Usage: /withdraw_pay <request_id> <txid>
    """
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 仅管理员可用")
        return
    
    args = context.args
    if len(args) < 2:
        update.message.reply_text(
            "❌ 用法: <code>/withdraw_pay &lt;request_id&gt; &lt;txid&gt;</code>",
            parse_mode='HTML'
        )
        return
    
    request_id = args[0]
    txid = args[1]
    
    try:
        # Find the withdrawal
        withdrawal = agent_withdrawals.find_one({'request_id': request_id})
        if not withdrawal:
            update.message.reply_text(f"❌ 未找到申请: {request_id}")
            return
        
        if withdrawal.get('status') != 'approved':
            update.message.reply_text(
                f"❌ 申请状态不是 approved (当前: {withdrawal.get('status')})\n"
                f"请先使用 /withdraw_approve 批准申请"
            )
            return
        
        agent_id = withdrawal.get('agent_id')
        amount = Decimal(str(withdrawal.get('amount_usdt', '0')))
        
        # Mark as paid
        agent_withdrawals.update_one(
            {'request_id': request_id},
            {
                '$set': {
                    'status': 'paid',
                    'paid_at': datetime.now(),
                    'paid_by': update.effective_user.id,
                    'txid': txid
                }
            }
        )
        
        # Update agent: move frozen -> paid, update total_paid
        agent = agents.find_one({'agent_id': agent_id})
        if agent:
            current_frozen = Decimal(str(agent.get('profit_frozen_usdt', '0')))
            current_total_paid = Decimal(str(agent.get('total_paid_usdt', '0')))
            
            new_frozen = current_frozen - amount
            new_total_paid = current_total_paid + amount
            
            agents.update_one(
                {'agent_id': agent_id},
                {
                    '$set': {
                        'profit_frozen_usdt': str(new_frozen.quantize(Decimal('0.01'))),
                        'total_paid_usdt': str(new_total_paid.quantize(Decimal('0.01'))),
                        'updated_at': datetime.now()
                    }
                }
            )
        
        update.message.reply_text(
            f"✅ 提现已标记为已支付\n\n"
            f"<b>申请ID:</b> <code>{request_id}</code>\n"
            f"<b>代理:</b> {agent_id}\n"
            f"<b>金额:</b> {amount} USDT\n"
            f"<b>TXID:</b> <code>{txid}</code>\n\n"
            f"<i>代理账户已更新</i>",
            parse_mode='HTML'
        )
        
        # Notify agent owner if possible
        try:
            owner_user_id = withdrawal.get('owner_user_id')
            if owner_user_id:
                context.bot.send_message(
                    chat_id=owner_user_id,
                    text=f"✅ 您的提现已完成！\n\n"
                         f"<b>申请ID:</b> <code>{request_id}</code>\n"
                         f"<b>金额:</b> {amount} USDT\n"
                         f"<b>TXID:</b> <code>{txid}</code>\n\n"
                         f"请检查您的钱包。",
                    parse_mode='HTML'
                )
        except Exception as e:
            logging.warning(f"Could not notify agent owner: {e}")
        
    except Exception as e:
        logging.error(f"Error in withdraw_pay_command: {e}")
        update.message.reply_text(f"❌ 标记失败: {e}")


def withdraw_stats_command(update: Update, context: CallbackContext):
    """Show withdrawal statistics.
    
    Usage: /withdraw_stats
    """
    if not is_admin(update.effective_user.id):
        update.message.reply_text("❌ 仅管理员可用")
        return
    
    try:
        pending_count = agent_withdrawals.count_documents({'status': 'pending'})
        approved_count = agent_withdrawals.count_documents({'status': 'approved'})
        paid_count = agent_withdrawals.count_documents({'status': 'paid'})
        rejected_count = agent_withdrawals.count_documents({'status': 'rejected'})
        
        # Total amounts
        pipeline_pending = [
            {'$match': {'status': 'pending'}},
            {'$group': {'_id': None, 'total': {'$sum': {'$toDecimal': '$amount_usdt'}}}}
        ]
        pipeline_paid = [
            {'$match': {'status': 'paid'}},
            {'$group': {'_id': None, 'total': {'$sum': {'$toDecimal': '$amount_usdt'}}}}
        ]
        
        pending_total = list(agent_withdrawals.aggregate(pipeline_pending))
        paid_total = list(agent_withdrawals.aggregate(pipeline_paid))
        
        pending_amount = float(pending_total[0]['total']) if pending_total else 0.0
        paid_amount = float(paid_total[0]['total']) if paid_total else 0.0
        
        text = f"""<b>💰 提现统计</b>

<b>申请数量:</b>
• 待审核: {pending_count}
• 已批准: {approved_count}
• 已支付: {paid_count}
• 已拒绝: {rejected_count}

<b>金额统计:</b>
• 待审核金额: {pending_amount:.2f} USDT
• 已支付总额: {paid_amount:.2f} USDT

<b>管理命令:</b>
/withdraw_list [status] - 查看申请列表
/withdraw_approve &lt;id&gt; - 批准申请
/withdraw_reject &lt;id&gt; [理由] - 拒绝申请
/withdraw_pay &lt;id&gt; &lt;txid&gt; - 标记已支付"""
        
        update.message.reply_text(text, parse_mode='HTML')
        
    except Exception as e:
        logging.error(f"Error in withdraw_stats_command: {e}")
        update.message.reply_text(f"❌ 获取统计失败: {e}")
