"""Agent backend handlers for agent owner self-service.

This module provides the /agent command and related flows for agent owners
to manage their agent bot settings, including markup, links, and withdrawals.
"""

import logging
import re
from decimal import Decimal
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from mongo import agents, agent_withdrawals


def agent_command(update: Update, context: CallbackContext):
    """Handle /agent command - show agent backend panel.
    
    Only works in child agent bots and only for the owner_user_id.
    """
    user_id = update.effective_user.id
    
    # Check if this is an agent bot
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        update.message.reply_text("❌ This command is only available in agent bots.")
        return
    
    # Get agent info
    try:
        agent = agents.find_one({'agent_id': agent_id})
        if not agent:
            update.message.reply_text("❌ Agent information not found.")
            return
        
        # Check if user is the owner
        owner_user_id = agent.get('owner_user_id')
        if not owner_user_id or user_id != owner_user_id:
            update.message.reply_text("❌ This command is only available to the agent owner.")
            return
        
        # Show agent panel
        show_agent_panel(update, context, agent, is_callback=False)
        
    except Exception as e:
        logging.error(f"Error in agent_command: {e}")
        update.message.reply_text(f"❌ Error loading agent panel: {e}")


def show_agent_panel(update: Update, context: CallbackContext, agent: dict = None, is_callback: bool = False):
    """Show agent backend panel with stats and configuration options."""
    agent_id = context.bot_data.get('agent_id')
    
    if not agent:
        agent = agents.find_one({'agent_id': agent_id})
    
    if not agent:
        text = "❌ Agent information not found."
        if is_callback:
            update.callback_query.edit_message_text(text)
        else:
            update.message.reply_text(text)
        return
    
    # Build panel text
    name = agent.get('name', 'Unnamed Agent')
    markup_usdt = agent.get('markup_usdt', '0')
    profit_available = agent.get('profit_available_usdt', '0')
    profit_frozen = agent.get('profit_frozen_usdt', '0')
    total_paid = agent.get('total_paid_usdt', '0')
    
    links = agent.get('links', {})
    support_link = links.get('support_link', '未设置')
    channel_link = links.get('channel_link', '未设置')
    announcement_link = links.get('announcement_link', '未设置')
    extra_links = links.get('extra_links', [])
    
    text = f"""<b>🤖 代理后台 - {name}</b>

<b>📊 财务概况</b>
• 差价设置: {markup_usdt} USDT/件
• 可提现余额: {profit_available} USDT
• 冻结中: {profit_frozen} USDT
• 已提现总额: {total_paid} USDT

<b>🔗 联系方式</b>
• 客服链接: {support_link}
• 频道链接: {channel_link}
• 公告链接: {announcement_link}
• 自定义按钮: {len(extra_links)} 个

<i>提示: 这些设置仅影响您的代理机器人，不会影响主机器人。</i>"""
    
    # Build keyboard
    keyboard = [
        [
            InlineKeyboardButton("💰 设置差价", callback_data="agent_set_markup"),
            InlineKeyboardButton("💸 发起提现", callback_data="agent_withdraw_init")
        ],
        [
            InlineKeyboardButton("📞 设置客服", callback_data="agent_set_support"),
            InlineKeyboardButton("📢 设置频道", callback_data="agent_set_channel")
        ],
        [
            InlineKeyboardButton("📣 设置公告", callback_data="agent_set_announcement"),
            InlineKeyboardButton("🔘 管理按钮", callback_data="agent_manage_buttons")
        ],
        [InlineKeyboardButton("❌ 关闭", callback_data=f"close {update.effective_user.id}")]
    ]
    
    if is_callback:
        update.callback_query.edit_message_text(
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


def agent_panel_callback(update: Update, context: CallbackContext):
    """Refresh agent panel."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        query.edit_message_text("❌ Not an agent bot.")
        return
    
    agent = agents.find_one({'agent_id': agent_id})
    show_agent_panel(update, context, agent, is_callback=True)


def agent_set_markup_callback(update: Update, context: CallbackContext):
    """Initiate markup setting flow."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        query.edit_message_text("❌ Not an agent bot.")
        return
    
    # Set state
    context.user_data['agent_backend_state'] = 'awaiting_markup'
    
    text = """<b>💰 设置差价</b>

请发送您想要设置的每件商品差价（单位：USDT）

示例：
• 发送 <code>0.05</code> 表示每件商品加价 0.05 USDT
• 发送 <code>1</code> 表示每件商品加价 1 USDT
• 发送 <code>0</code> 表示不加价

差价必须 ≥ 0"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="agent_panel")]]
    
    query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def agent_withdraw_init_callback(update: Update, context: CallbackContext):
    """Initiate withdrawal flow."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        query.edit_message_text("❌ Not an agent bot.")
        return
    
    agent = agents.find_one({'agent_id': agent_id})
    if not agent:
        query.edit_message_text("❌ Agent not found.")
        return
    
    available = Decimal(str(agent.get('profit_available_usdt', '0')))
    
    if available < Decimal('10'):
        query.edit_message_text(
            f"❌ 余额不足\n\n"
            f"可提现余额: {available} USDT\n"
            f"最低提现金额: 10 USDT"
        )
        return
    
    # Set state
    context.user_data['agent_backend_state'] = 'awaiting_withdraw_amount'
    context.user_data['agent_available_balance'] = str(available)
    
    text = f"""<b>💸 发起提现</b>

可提现余额: <b>{available} USDT</b>
最低提现: <b>10 USDT</b>
手续费: <b>1 USDT</b>

请发送您想提现的金额（USDT）

示例: <code>20</code> 或 <code>50.5</code>"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="agent_panel")]]
    
    query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def agent_set_link_callback(update: Update, context: CallbackContext):
    """Initiate link setting flow (support/channel/announcement)."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        query.edit_message_text("❌ Not an agent bot.")
        return
    
    # Determine which link type from callback data
    link_type = query.data.replace('agent_set_', '')  # 'support', 'channel', or 'announcement'
    
    link_names = {
        'support': '客服',
        'channel': '频道',
        'announcement': '公告'
    }
    
    # Set state
    context.user_data['agent_backend_state'] = f'awaiting_{link_type}_link'
    
    text = f"""<b>📞 设置{link_names.get(link_type, '')}链接</b>

请发送{link_names.get(link_type, '')}链接

支持的格式：
• Telegram链接: <code>@username</code> 或 <code>https://t.me/username</code>
• 群组链接: <code>https://t.me/+xxx</code>
• 其他链接: <code>https://example.com</code>

发送 <code>清除</code> 可以清除当前设置"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="agent_panel")]]
    
    query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def agent_manage_buttons_callback(update: Update, context: CallbackContext):
    """Show custom button management panel."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        query.edit_message_text("❌ Not an agent bot.")
        return
    
    agent = agents.find_one({'agent_id': agent_id})
    if not agent:
        query.edit_message_text("❌ Agent not found.")
        return
    
    links = agent.get('links', {})
    extra_links = links.get('extra_links', [])
    
    text = "<b>🔘 管理自定义按钮</b>\n\n"
    
    if not extra_links:
        text += "暂无自定义按钮\n\n"
    else:
        text += "当前按钮:\n"
        for idx, link in enumerate(extra_links, 1):
            text += f"{idx}. {link.get('title', 'Untitled')}: {link.get('url', 'No URL')}\n"
        text += "\n"
    
    text += f"您可以添加最多 5 个自定义按钮\n"
    text += f"当前: {len(extra_links)}/5"
    
    keyboard = []
    
    if len(extra_links) < 5:
        keyboard.append([InlineKeyboardButton("➕ 添加按钮", callback_data="agent_add_button")])
    
    if extra_links:
        keyboard.append([InlineKeyboardButton("🗑 删除按钮", callback_data="agent_delete_button")])
    
    keyboard.append([InlineKeyboardButton("⬅️ 返回", callback_data="agent_panel")])
    keyboard.append([InlineKeyboardButton("❌ 关闭", callback_data=f"close {query.from_user.id}")])
    
    query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def agent_text_input_handler(update: Update, context: CallbackContext):
    """Handle text input for agent backend flows."""
    state = context.user_data.get('agent_backend_state')
    
    if not state:
        return  # Not in a flow
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        return
    
    text = update.message.text.strip()
    
    try:
        if state == 'awaiting_markup':
            handle_markup_input(update, context, agent_id, text)
        elif state == 'awaiting_withdraw_amount':
            handle_withdraw_amount_input(update, context, agent_id, text)
        elif state == 'awaiting_withdraw_address':
            handle_withdraw_address_input(update, context, agent_id, text)
        elif state == 'awaiting_support_link':
            handle_link_input(update, context, agent_id, 'support_link', text, '客服')
        elif state == 'awaiting_channel_link':
            handle_link_input(update, context, agent_id, 'channel_link', text, '频道')
        elif state == 'awaiting_announcement_link':
            handle_link_input(update, context, agent_id, 'announcement_link', text, '公告')
        elif state == 'awaiting_button_title':
            context.user_data['button_title'] = text
            context.user_data['agent_backend_state'] = 'awaiting_button_url'
            update.message.reply_text(
                "请发送按钮的链接（URL）\n\n"
                "示例: <code>https://t.me/yourchannel</code>",
                parse_mode='HTML'
            )
        elif state == 'awaiting_button_url':
            handle_button_add(update, context, agent_id, text)
        elif state == 'awaiting_button_delete_index':
            handle_button_delete(update, context, agent_id, text)
    except Exception as e:
        logging.error(f"Error in agent_text_input_handler: {e}")
        update.message.reply_text(f"❌ 处理输入时出错: {e}")
        context.user_data.pop('agent_backend_state', None)


def handle_markup_input(update: Update, context: CallbackContext, agent_id: str, text: str):
    """Handle markup value input."""
    try:
        markup = Decimal(text)
        if markup < 0:
            update.message.reply_text("❌ 差价不能为负数，请重新输入")
            return
        
        # Update agent markup
        agents.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    'markup_usdt': str(markup.quantize(Decimal('0.01'))),
                    'updated_at': datetime.now()
                }
            }
        )
        
        # Clear state
        context.user_data.pop('agent_backend_state', None)
        
        update.message.reply_text(
            f"✅ 差价设置成功！\n\n"
            f"新差价: <b>{markup} USDT/件</b>\n\n"
            f"此后您的机器人销售商品时，每件将加价 {markup} USDT，利润自动累积到您的账户。",
            parse_mode='HTML'
        )
        
    except Exception as e:
        update.message.reply_text(f"❌ 输入格式错误，请输入有效数字")


def handle_withdraw_amount_input(update: Update, context: CallbackContext, agent_id: str, text: str):
    """Handle withdrawal amount input."""
    try:
        amount = Decimal(text)
        available = Decimal(context.user_data.get('agent_available_balance', '0'))
        
        if amount < Decimal('10'):
            update.message.reply_text("❌ 提现金额不能少于 10 USDT")
            return
        
        if amount > available:
            update.message.reply_text(f"❌ 余额不足\n\n可提现余额: {available} USDT")
            return
        
        # Move to next step: request address
        context.user_data['withdraw_amount'] = str(amount)
        context.user_data['agent_backend_state'] = 'awaiting_withdraw_address'
        
        update.message.reply_text(
            f"💸 提现金额: <b>{amount} USDT</b>\n"
            f"手续费: <b>1 USDT</b>\n"
            f"实际到账: <b>{amount - Decimal('1')} USDT</b>\n\n"
            f"请发送您的 TRC20 USDT 收款地址\n\n"
            f"示例: <code>T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb</code>",
            parse_mode='HTML'
        )
        
    except Exception as e:
        update.message.reply_text(f"❌ 输入格式错误，请输入有效数字")


def handle_withdraw_address_input(update: Update, context: CallbackContext, agent_id: str, text: str):
    """Handle withdrawal address input and create withdrawal request."""
    address = text.strip()
    
    # Simple TRC20 address validation
    if not (address.startswith('T') and len(address) == 34):
        update.message.reply_text(
            "❌ 地址格式错误\n\n"
            "TRC20 USDT 地址应该以 T 开头，长度为 34 个字符\n\n"
            "请重新输入正确的地址"
        )
        return
    
    try:
        amount = Decimal(context.user_data.get('withdraw_amount', '0'))
        
        # Create withdrawal request
        request_id = f"aw_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{agent_id[-6:]}"
        
        withdrawal_doc = {
            'request_id': request_id,
            'agent_id': agent_id,
            'owner_user_id': context.bot_data.get('owner_user_id'),
            'amount_usdt': str(amount.quantize(Decimal('0.01'))),
            'fee_usdt': '1',
            'address': address,
            'status': 'pending',
            'created_at': datetime.now(),
            'reviewed_at': None,
            'reviewed_by': None
        }
        
        agent_withdrawals.insert_one(withdrawal_doc)
        
        # Freeze the amount
        agent = agents.find_one({'agent_id': agent_id})
        current_available = Decimal(str(agent.get('profit_available_usdt', '0')))
        current_frozen = Decimal(str(agent.get('profit_frozen_usdt', '0')))
        
        new_available = current_available - amount
        new_frozen = current_frozen + amount
        
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
        
        # Clear state
        context.user_data.pop('agent_backend_state', None)
        context.user_data.pop('withdraw_amount', None)
        context.user_data.pop('agent_available_balance', None)
        
        update.message.reply_text(
            f"✅ 提现申请已提交！\n\n"
            f"<b>申请编号:</b> <code>{request_id}</code>\n"
            f"<b>提现金额:</b> {amount} USDT\n"
            f"<b>手续费:</b> 1 USDT\n"
            f"<b>实际到账:</b> {amount - Decimal('1')} USDT\n"
            f"<b>收款地址:</b> <code>{address}</code>\n\n"
            f"您的申请将由管理员审核，审核通过后将尽快处理。",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logging.error(f"Error creating withdrawal request: {e}")
        update.message.reply_text(f"❌ 创建提现申请失败: {e}")
        context.user_data.pop('agent_backend_state', None)


def handle_link_input(update: Update, context: CallbackContext, agent_id: str, field: str, text: str, name: str):
    """Handle link input for support/channel/announcement."""
    if text == '清除':
        # Clear the link
        agents.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    f'links.{field}': None,
                    'updated_at': datetime.now()
                },
                '$unset': {f'links.{field}': ""}
            }
        )
        
        context.user_data.pop('agent_backend_state', None)
        update.message.reply_text(f"✅ {name}链接已清除")
        return
    
    # Simple validation
    if not (text.startswith('@') or text.startswith('http://') or text.startswith('https://')):
        update.message.reply_text(
            "❌ 链接格式错误\n\n"
            "请发送以下格式之一:\n"
            "• @username\n"
            "• https://t.me/username\n"
            "• https://example.com"
        )
        return
    
    # Update link
    agents.update_one(
        {'agent_id': agent_id},
        {
            '$set': {
                f'links.{field}': text,
                'updated_at': datetime.now()
            }
        }
    )
    
    context.user_data.pop('agent_backend_state', None)
    update.message.reply_text(f"✅ {name}链接设置成功！\n\n<b>新链接:</b> {text}", parse_mode='HTML')


def handle_button_add(update: Update, context: CallbackContext, agent_id: str, url: str):
    """Handle adding a custom button."""
    title = context.user_data.get('button_title', '')
    
    if not (url.startswith('http://') or url.startswith('https://')):
        update.message.reply_text("❌ URL 格式错误，必须以 http:// 或 https:// 开头")
        return
    
    agent = agents.find_one({'agent_id': agent_id})
    links = agent.get('links', {})
    extra_links = links.get('extra_links', [])
    
    if len(extra_links) >= 5:
        update.message.reply_text("❌ 最多只能添加 5 个自定义按钮")
        context.user_data.pop('agent_backend_state', None)
        context.user_data.pop('button_title', None)
        return
    
    # Add new button
    extra_links.append({'title': title, 'url': url})
    
    agents.update_one(
        {'agent_id': agent_id},
        {
            '$set': {
                'links.extra_links': extra_links,
                'updated_at': datetime.now()
            }
        }
    )
    
    context.user_data.pop('agent_backend_state', None)
    context.user_data.pop('button_title', None)
    
    update.message.reply_text(
        f"✅ 按钮添加成功！\n\n"
        f"<b>标题:</b> {title}\n"
        f"<b>链接:</b> {url}",
        parse_mode='HTML'
    )


def handle_button_delete(update: Update, context: CallbackContext, agent_id: str, text: str):
    """Handle deleting a custom button."""
    try:
        index = int(text) - 1  # Convert to 0-based index
        
        agent = agents.find_one({'agent_id': agent_id})
        links = agent.get('links', {})
        extra_links = links.get('extra_links', [])
        
        if index < 0 or index >= len(extra_links):
            update.message.reply_text(f"❌ 无效的按钮编号，请输入 1-{len(extra_links)} 之间的数字")
            return
        
        # Remove button
        deleted = extra_links.pop(index)
        
        agents.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    'links.extra_links': extra_links,
                    'updated_at': datetime.now()
                }
            }
        )
        
        context.user_data.pop('agent_backend_state', None)
        
        update.message.reply_text(
            f"✅ 按钮已删除\n\n"
            f"<b>已删除:</b> {deleted.get('title', 'Untitled')}",
            parse_mode='HTML'
        )
        
    except ValueError:
        update.message.reply_text("❌ 请输入有效的数字")


def agent_add_button_callback(update: Update, context: CallbackContext):
    """Initiate add button flow."""
    query = update.callback_query
    query.answer()
    
    context.user_data['agent_backend_state'] = 'awaiting_button_title'
    
    query.edit_message_text(
        "➕ <b>添加自定义按钮</b>\n\n"
        "请发送按钮的标题\n\n"
        "示例: <code>我的频道</code>",
        parse_mode='HTML'
    )


def agent_delete_button_callback(update: Update, context: CallbackContext):
    """Initiate delete button flow."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        query.edit_message_text("❌ Not an agent bot.")
        return
    
    agent = agents.find_one({'agent_id': agent_id})
    links = agent.get('links', {})
    extra_links = links.get('extra_links', [])
    
    if not extra_links:
        query.edit_message_text("❌ 没有可删除的按钮")
        return
    
    text = "🗑 <b>删除自定义按钮</b>\n\n当前按钮:\n"
    for idx, link in enumerate(extra_links, 1):
        text += f"{idx}. {link.get('title', 'Untitled')}\n"
    text += "\n请发送要删除的按钮编号（1-" + str(len(extra_links)) + "）"
    
    context.user_data['agent_backend_state'] = 'awaiting_button_delete_index'
    
    query.edit_message_text(text=text, parse_mode='HTML')
