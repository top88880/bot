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
from bot import get_admin_ids


def agent_command(update: Update, context: CallbackContext):
    """Handle /agent command - show agent backend panel.
    
    Only works in child agent bots and only for the owner_user_id.
    Allows first-time binding if owner_user_id is None or an admin ID.
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
        admin_ids = get_admin_ids()
        
        # Allow binding if owner is None or is an admin (one-time claim)
        if owner_user_id is None or owner_user_id in admin_ids:
            # Show bind button
            show_bind_panel(update, context, agent, owner_user_id, is_callback=False)
            return
        
        if user_id != owner_user_id:
            update.message.reply_text("❌ This command is only available to the agent owner.")
            return
        
        # Show agent panel
        show_agent_panel(update, context, agent, is_callback=False)
        
    except Exception as e:
        logging.error(f"Error in agent_command: {e}")
        update.message.reply_text(f"❌ Error loading agent panel: {e}")


def show_bind_panel(update: Update, context: CallbackContext, agent: dict, current_owner_id, is_callback: bool = False):
    """Show panel with bind button for claiming ownership."""
    admin_ids = get_admin_ids()
    
    if current_owner_id is None:
        text = """<b>🤖 代理后台 - 未绑定</b>

此代理机器人尚未绑定拥有者。

作为代理运营者，您需要先绑定为拥有者才能访问代理后台。

点击下方按钮绑定您的账号为此代理的拥有者。"""
    elif current_owner_id in admin_ids:
        text = """<b>🤖 代理后台 - 需要重新绑定</b>

此代理机器人当前绑定的是管理员账号。

作为实际的代理运营者，您可以一次性地将拥有者身份转移到您的账号。

⚠️ <b>注意：</b>此操作只能执行一次，请确认您是该代理的实际运营者。"""
    else:
        text = "❌ 权限错误"
    
    keyboard = [
        [InlineKeyboardButton("🔐 绑定为拥有者", callback_data="agent_claim_owner")],
        [InlineKeyboardButton("❌ 取消", callback_data=f"close {update.effective_user.id}")]
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


def agent_claim_owner_callback(update: Update, context: CallbackContext):
    """Handle owner claim button press."""
    query = update.callback_query
    query.answer()
    
    user_id = query.from_user.id
    agent_id = context.bot_data.get('agent_id')
    
    if not agent_id:
        query.edit_message_text("❌ Agent context not found.")
        return
    
    try:
        agent = agents.find_one({'agent_id': agent_id})
        if not agent:
            query.edit_message_text("❌ Agent not found.")
            return
        
        owner_user_id = agent.get('owner_user_id')
        admin_ids = get_admin_ids()
        
        # Verify this is allowed (None or admin)
        if owner_user_id is not None and owner_user_id not in admin_ids:
            query.edit_message_text("❌ This agent already has a non-admin owner.")
            return
        
        # Bind the user as owner
        agents.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    'owner_user_id': user_id,
                    'updated_at': datetime.now()
                }
            }
        )
        
        logging.info(f"Agent {agent_id} owner bound to user {user_id}")
        
        # Show success and then the agent panel
        query.edit_message_text(
            f"✅ <b>绑定成功！</b>\n\n"
            f"您已成功绑定为此代理的拥有者。\n\n"
            f"请再次使用 /agent 命令打开代理后台。",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logging.error(f"Error in agent_claim_owner_callback: {e}")
        query.edit_message_text(f"❌ 绑定失败: {e}")


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
    
    # Get settings (new structure)
    settings = agent.get('settings', {})
    customer_service = settings.get('customer_service', '未设置')
    official_channel = settings.get('official_channel', '未设置')
    restock_group = settings.get('restock_group', '未设置')
    tutorial_link = settings.get('tutorial_link', '未设置')
    notify_channel_id = settings.get('notify_channel_id', '未设置')
    
    text = f"""<b>🤖 代理后台 - {name}</b>

<b>📊 财务概况</b>
• 差价设置: {markup_usdt} USDT/件
• 可提现余额: {profit_available} USDT
• 冻结中: {profit_frozen} USDT
• 已提现总额: {total_paid} USDT

<b>🔗 联系方式</b>
• 客服: {customer_service}
• 官方频道: {official_channel}
• 补货通知群: {restock_group}
• 教程链接: {tutorial_link}
• 通知频道ID: {notify_channel_id}

<i>提示: 这些设置仅影响您的代理机器人，不会影响主机器人。</i>"""
    
    # Build keyboard
    keyboard = [
        [
            InlineKeyboardButton("💰 设置差价", callback_data="agent_set_markup"),
            InlineKeyboardButton("💸 发起提现", callback_data="agent_withdraw_init")
        ],
        [
            InlineKeyboardButton("📞 设置客服", callback_data="agent_cfg_cs"),
            InlineKeyboardButton("📢 设置官方频道", callback_data="agent_cfg_official")
        ],
        [
            InlineKeyboardButton("📣 设置补货通知群", callback_data="agent_cfg_restock"),
            InlineKeyboardButton("📖 设置教程链接", callback_data="agent_cfg_tutorial")
        ],
        [
            InlineKeyboardButton("🔔 设置通知频道ID", callback_data="agent_cfg_notify"),
            InlineKeyboardButton("🔘 管理链接按钮", callback_data="agent_links_btns")
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
    """Initiate markup setting flow with preset buttons."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        query.edit_message_text("❌ Not an agent bot.")
        return
    
    # Get current markup
    agent = agents.find_one({'agent_id': agent_id})
    current_markup = agent.get('markup_usdt', '0') if agent else '0'
    
    text = f"""<b>💰 设置差价</b>

当前差价: <b>{current_markup} USDT/件</b>

您可以选择快捷设置，或发送自定义金额:

<b>快捷选项:</b>
• +0.01 USDT
• +0.05 USDT
• +0.10 USDT

<b>自定义设置:</b>
发送任意 ≥ 0 的USDT金额

示例: <code>0.08</code> 或 <code>1.5</code>"""
    
    keyboard = [
        [
            InlineKeyboardButton("+0.01", callback_data="agent_markup_preset_0.01"),
            InlineKeyboardButton("+0.05", callback_data="agent_markup_preset_0.05"),
            InlineKeyboardButton("+0.10", callback_data="agent_markup_preset_0.10")
        ],
        [InlineKeyboardButton("❌ 取消", callback_data="agent_panel")]
    ]
    
    # Set state for custom input
    context.user_data['agent_backend_state'] = 'awaiting_markup'
    
    query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def agent_markup_preset_callback(update: Update, context: CallbackContext):
    """Handle preset markup button press."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        query.edit_message_text("❌ Not an agent bot.")
        return
    
    # Extract value from callback data (e.g., "agent_markup_preset_0.05" -> "0.05")
    value_str = query.data.replace('agent_markup_preset_', '')
    
    try:
        markup = Decimal(value_str)
        
        # Update agent markup with 8 decimal precision
        agents.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    'markup_usdt': str(markup.quantize(Decimal('0.00000001'))),
                    'updated_at': datetime.now()
                }
            }
        )
        
        # Clear state
        context.user_data.pop('agent_backend_state', None)
        
        query.edit_message_text(
            f"✅ 差价设置成功！\n\n"
            f"新差价: <b>{markup} USDT/件</b>\n\n"
            f"此后您的机器人销售商品时，每件将加价 {markup} USDT，利润自动累积到您的账户。",
            parse_mode='HTML'
        )
        
    except Exception as e:
        logging.error(f"Error setting preset markup: {e}")
        query.edit_message_text(f"❌ 设置失败: {e}")


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
    """DEPRECATED: Initiate link setting flow (support/channel/announcement)."""
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


def agent_cfg_cs_callback(update: Update, context: CallbackContext):
    """Initiate customer service setting flow."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        query.edit_message_text("❌ Not an agent bot.")
        return
    
    # Set state
    context.user_data['agent_backend_state'] = 'awaiting_cs_input'
    
    text = """<b>📞 设置客服</b>

请发送客服联系方式

支持的格式：
• 单个客服: <code>@customer_service</code>
• 多个客服: <code>@cs1 @cs2 @cs3</code> (用空格分隔)
• 客服链接: <code>https://t.me/customer_service</code>

发送 <code>清除</code> 可以清除当前设置"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="agent_panel")]]
    
    query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def agent_cfg_official_callback(update: Update, context: CallbackContext):
    """Initiate official channel setting flow."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        query.edit_message_text("❌ Not an agent bot.")
        return
    
    # Set state
    context.user_data['agent_backend_state'] = 'awaiting_official_input'
    
    text = """<b>📢 设置官方频道</b>

请发送官方频道链接

支持的格式：
• 频道用户名: <code>@yourchannel</code>
• 频道链接: <code>https://t.me/yourchannel</code>

发送 <code>清除</code> 可以清除当前设置"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="agent_panel")]]
    
    query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def agent_cfg_restock_callback(update: Update, context: CallbackContext):
    """Initiate restock group setting flow."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        query.edit_message_text("❌ Not an agent bot.")
        return
    
    # Set state
    context.user_data['agent_backend_state'] = 'awaiting_restock_input'
    
    text = """<b>📣 设置补货通知群</b>

请发送补货通知群链接

支持的格式：
• 群组用户名: <code>@yourgroup</code>
• 群组链接: <code>https://t.me/yourgroup</code>
• 群组邀请链接: <code>https://t.me/+xxxxx</code>

发送 <code>清除</code> 可以清除当前设置"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="agent_panel")]]
    
    query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def agent_cfg_tutorial_callback(update: Update, context: CallbackContext):
    """Initiate tutorial link setting flow."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        query.edit_message_text("❌ Not an agent bot.")
        return
    
    # Set state
    context.user_data['agent_backend_state'] = 'awaiting_tutorial_input'
    
    text = """<b>📖 设置教程链接</b>

请发送教程页面链接

<b>要求:</b>
• 必须是有效的 URL (http:// 或 https://)
• 可以是任何网页链接

示例:
• <code>https://example.com/tutorial</code>
• <code>https://docs.google.com/document/xxx</code>

发送 <code>清除</code> 可以清除当前设置"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="agent_panel")]]
    
    query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def agent_cfg_notify_callback(update: Update, context: CallbackContext):
    """Initiate notify channel ID setting flow."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        query.edit_message_text("❌ Not an agent bot.")
        return
    
    # Set state
    context.user_data['agent_backend_state'] = 'awaiting_notify_input'
    
    text = """<b>🔔 设置通知频道ID</b>

请发送通知频道的数字ID

<b>如何获取频道ID:</b>
1. 将机器人添加到您的频道
2. 在频道发送一条消息
3. 使用 @username_to_id_bot 等工具获取频道ID

<b>格式要求:</b>
• 必须是数字 (通常以 -100 开头)
• 示例: <code>-100123456789</code>

发送 <code>清除</code> 可以清除当前设置"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="agent_panel")]]
    
    query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def agent_links_btns_callback(update: Update, context: CallbackContext):
    """Show custom link buttons management panel."""
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
    
    # Get custom buttons from settings.extra_links
    settings = agent.get('settings', {})
    extra_links = settings.get('extra_links', [])
    
    text = "<b>🔘 管理链接按钮</b>\n\n"
    
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


def agent_manage_buttons_callback(update: Update, context: CallbackContext):
    """DEPRECATED: Show custom button management panel."""
    # Redirect to new function
    agent_links_btns_callback(update, context)


def agent_manage_buttons_callback_old(update: Update, context: CallbackContext):
    """DEPRECATED OLD VERSION: Show custom button management panel."""
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
        elif state == 'awaiting_cs_input':
            handle_setting_input(update, context, agent_id, 'customer_service', text, '客服')
        elif state == 'awaiting_official_input':
            handle_setting_input(update, context, agent_id, 'official_channel', text, '官方频道')
        elif state == 'awaiting_restock_input':
            handle_setting_input(update, context, agent_id, 'restock_group', text, '补货通知群')
        elif state == 'awaiting_tutorial_input':
            handle_tutorial_input(update, context, agent_id, text)
        elif state == 'awaiting_notify_input':
            handle_notify_channel_input(update, context, agent_id, text)
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
        
        # Update agent markup with 8 decimal precision
        agents.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    'markup_usdt': str(markup.quantize(Decimal('0.00000001'))),
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
                    'profit_available_usdt': str(new_available.quantize(Decimal('0.00000001'))),
                    'profit_frozen_usdt': str(new_frozen.quantize(Decimal('0.00000001'))),
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


def handle_setting_input(update: Update, context: CallbackContext, agent_id: str, field: str, text: str, name: str):
    """Handle general setting input for customer_service/official_channel/restock_group."""
    if text == '清除':
        # Clear the setting
        agents.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    f'settings.{field}': None,
                    'updated_at': datetime.now()
                },
                '$unset': {f'settings.{field}': ""}
            }
        )
        
        context.user_data.pop('agent_backend_state', None)
        update.message.reply_text(f"✅ {name}已清除")
        return
    
    # Simple validation - allow @username or URLs
    if not (text.startswith('@') or text.startswith('http://') or text.startswith('https://')):
        update.message.reply_text(
            "❌ 格式错误\n\n"
            "请发送以下格式之一:\n"
            "• @username (可以用空格分隔多个)\n"
            "• https://t.me/username\n"
            "• https://example.com"
        )
        return
    
    # Update setting
    agents.update_one(
        {'agent_id': agent_id},
        {
            '$set': {
                f'settings.{field}': text,
                'updated_at': datetime.now()
            }
        }
    )
    
    context.user_data.pop('agent_backend_state', None)
    update.message.reply_text(f"✅ {name}设置成功！\n\n<b>新设置:</b> {text}", parse_mode='HTML')


def handle_tutorial_input(update: Update, context: CallbackContext, agent_id: str, text: str):
    """Handle tutorial link input with URL validation."""
    if text == '清除':
        agents.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    'settings.tutorial_link': None,
                    'updated_at': datetime.now()
                },
                '$unset': {'settings.tutorial_link': ""}
            }
        )
        
        context.user_data.pop('agent_backend_state', None)
        update.message.reply_text("✅ 教程链接已清除")
        return
    
    # Validate URL
    if not (text.startswith('http://') or text.startswith('https://')):
        update.message.reply_text(
            "❌ 教程链接必须是有效的URL\n\n"
            "请发送以 http:// 或 https:// 开头的链接\n\n"
            "示例: <code>https://example.com/tutorial</code>",
            parse_mode='HTML'
        )
        return
    
    # Update setting
    agents.update_one(
        {'agent_id': agent_id},
        {
            '$set': {
                'settings.tutorial_link': text,
                'updated_at': datetime.now()
            }
        }
    )
    
    context.user_data.pop('agent_backend_state', None)
    update.message.reply_text(f"✅ 教程链接设置成功！\n\n<b>新链接:</b> {text}", parse_mode='HTML')


def handle_notify_channel_input(update: Update, context: CallbackContext, agent_id: str, text: str):
    """Handle notify channel ID input with numeric validation."""
    if text == '清除':
        agents.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    'settings.notify_channel_id': None,
                    'updated_at': datetime.now()
                },
                '$unset': {'settings.notify_channel_id': ""}
            }
        )
        
        context.user_data.pop('agent_backend_state', None)
        update.message.reply_text("✅ 通知频道ID已清除")
        return
    
    # Validate numeric ID (should start with - for channels)
    text = text.strip()
    if not text.lstrip('-').isdigit():
        update.message.reply_text(
            "❌ 通知频道ID必须是数字\n\n"
            "请发送有效的频道ID\n\n"
            "示例: <code>-100123456789</code>",
            parse_mode='HTML'
        )
        return
    
    # Update setting
    agents.update_one(
        {'agent_id': agent_id},
        {
            '$set': {
                'settings.notify_channel_id': text,
                'updated_at': datetime.now()
            }
        }
    )
    
    context.user_data.pop('agent_backend_state', None)
    update.message.reply_text(f"✅ 通知频道ID设置成功！\n\n<b>新ID:</b> <code>{text}</code>", parse_mode='HTML')


def handle_link_input(update: Update, context: CallbackContext, agent_id: str, field: str, text: str, name: str):
    """DEPRECATED: Handle link input for support/channel/announcement."""
    # This function is kept for backward compatibility but should not be called
    # Use handle_setting_input, handle_tutorial_input, or handle_notify_channel_input instead
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
    settings = agent.get('settings', {})
    extra_links = settings.get('extra_links', [])
    
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
                'settings.extra_links': extra_links,
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
        settings = agent.get('settings', {})
        extra_links = settings.get('extra_links', [])
        
        if index < 0 or index >= len(extra_links):
            update.message.reply_text(f"❌ 无效的按钮编号，请输入 1-{len(extra_links)} 之间的数字")
            return
        
        # Remove button
        deleted = extra_links.pop(index)
        
        agents.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    'settings.extra_links': extra_links,
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
    settings = agent.get('settings', {})
    extra_links = settings.get('extra_links', [])
    
    if not extra_links:
        query.edit_message_text("❌ 没有可删除的按钮")
        return
    
    text = "🗑 <b>删除自定义按钮</b>\n\n当前按钮:\n"
    for idx, link in enumerate(extra_links, 1):
        text += f"{idx}. {link.get('title', 'Untitled')}\n"
    text += "\n请发送要删除的按钮编号（1-" + str(len(extra_links)) + "）"
    
    context.user_data['agent_backend_state'] = 'awaiting_button_delete_index'
    
    query.edit_message_text(text=text, parse_mode='HTML')
