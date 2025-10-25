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

from mongo import agents, agent_withdrawals, user
from bot import get_admin_ids
from services.message_utils import safe_edit_message_text


# ===== i18n Support =====
I18N = {
    'zh': {
        'agent_panel_title': '🤖 代理后台',
        'financial_overview': '📊 财务概况',
        'markup_setting': '差价设置',
        'available_balance': '可提现余额',
        'frozen_balance': '冻结中',
        'total_paid': '已提现总额',
        'contact_info': '🔗 联系方式',
        'customer_service': '客服',
        'official_channel': '官方频道',
        'restock_group': '补货通知群',
        'tutorial_link': '教程链接',
        'notify_channel_id': '通知频道ID',
        'notify_group_id': '通知群组ID',
        'not_set': '未设置',
        'panel_tip': '提示: 这些设置仅影响您的代理机器人，不会影响主机器人。',
        'set_markup': '💰 设置差价',
        'initiate_withdrawal': '💸 发起提现',
        'set_customer_service': '📞 设置客服',
        'set_official_channel': '📢 设置官方频道',
        'set_restock_group': '📣 设置补货通知群',
        'set_tutorial_link': '📖 设置教程链接',
        'set_notify_channel': '🔔 设置通知频道ID',
        'set_notify_group': '👥 设置通知群ID',
        'test_group_notification': '📤 发送测试群通知',
        'manage_link_buttons': '🔘 管理链接按钮',
        'send_test_notification': '📡 发送测试通知',
        'business_report': '📊 经营报告',
        'close': '❌ 关闭',
        'not_agent_bot': '❌ 此命令仅在代理机器人中可用。',
        'agent_not_found': '❌ 未找到代理信息。',
        'not_owner': '❌ 此命令仅限代理拥有者使用。',
        'error_loading_panel': '❌ 加载代理后台时出错',
        'bind_as_owner': '🔐 绑定为拥有者',
        'cancel': '❌ 取消',
        'unbound_title': '🤖 代理后台 - 未绑定',
        'unbound_message': '此代理机器人尚未绑定拥有者。\n\n作为代理运营者，您需要先绑定为拥有者才能访问代理后台。\n\n点击下方按钮绑定您的账号为此代理的拥有者。',
        'rebind_title': '🤖 代理后台 - 需要重新绑定',
        'rebind_message': '此代理机器人当前绑定的是管理员账号。\n\n作为实际的代理运营者，您可以一次性地将拥有者身份转移到您的账号。\n\n⚠️ <b>注意：</b>此操作只能执行一次，请确认您是该代理的实际运营者。',
        'test_notif_success': '✅ 测试通知发送成功！\n\n通知已发送到您配置的频道。',
        'test_notif_no_channel': '❌ 未设置通知频道\n\n请先设置通知频道ID。',
        'test_notif_error': '❌ 发送失败\n\n错误信息: {error}\n\n请检查:\n1. 频道ID格式是否正确 (例如: -1001234567890)\n2. 机器人是否已被添加到频道\n3. 机器人是否有发送消息的权限',
        'test_group_notif_success': '✅ 测试群通知发送成功！\n\n通知已发送到您配置的群组。',
        'test_group_notif_no_group': '❌ 未设置通知群\n\n请先设置通知群ID。',
        'test_group_notif_error': '❌ 发送失败\n\n错误信息: {error}\n\n请检查:\n1. 群组ID格式是否正确 (例如: -100xxxxxxxxxx)\n2. 机器人是否已被添加到群组\n3. 机器人是否有发送消息的权限',
    },
    'en': {
        'agent_panel_title': '🤖 Agent Backend',
        'financial_overview': '📊 Financial Overview',
        'markup_setting': 'Markup Setting',
        'available_balance': 'Available Balance',
        'frozen_balance': 'Frozen',
        'total_paid': 'Total Withdrawn',
        'contact_info': '🔗 Contact Information',
        'customer_service': 'Customer Service',
        'official_channel': 'Official Channel',
        'restock_group': 'Restock Group',
        'tutorial_link': 'Tutorial Link',
        'notify_channel_id': 'Notify Channel ID',
        'notify_group_id': 'Notify Group ID',
        'not_set': 'Not Set',
        'panel_tip': 'Tip: These settings only affect your agent bot, not the main bot.',
        'set_markup': '💰 Set Markup',
        'initiate_withdrawal': '💸 Withdraw',
        'set_customer_service': '📞 Set Customer Service',
        'set_official_channel': '📢 Set Official Channel',
        'set_restock_group': '📣 Set Restock Group',
        'set_tutorial_link': '📖 Set Tutorial Link',
        'set_notify_channel': '🔔 Set Notify Channel ID',
        'set_notify_group': '👥 Set Notify Group ID',
        'test_group_notification': '📤 Send Test Group Notification',
        'manage_link_buttons': '🔘 Manage Link Buttons',
        'send_test_notification': '📡 Send Test Notification',
        'business_report': '📊 Business Report',
        'close': '❌ Close',
        'not_agent_bot': '❌ This command is only available in agent bots.',
        'agent_not_found': '❌ Agent information not found.',
        'not_owner': '❌ This command is only available to the agent owner.',
        'error_loading_panel': '❌ Error loading agent panel',
        'bind_as_owner': '🔐 Bind as Owner',
        'cancel': '❌ Cancel',
        'unbound_title': '🤖 Agent Backend - Unbound',
        'unbound_message': 'This agent bot has no owner bound yet.\n\nAs the agent operator, you need to bind yourself as the owner to access the agent backend.\n\nClick the button below to bind your account as the owner.',
        'rebind_title': '🤖 Agent Backend - Rebind Required',
        'rebind_message': 'This agent bot is currently bound to an admin account.\n\nAs the actual agent operator, you can transfer ownership to your account once.\n\n⚠️ <b>Note:</b> This operation can only be done once. Please confirm you are the actual operator.',
        'test_notif_success': '✅ Test notification sent successfully!\n\nThe notification was sent to your configured channel.',
        'test_notif_no_channel': '❌ Notify channel not set\n\nPlease set the notify channel ID first.',
        'test_notif_error': '❌ Send failed\n\nError: {error}\n\nPlease check:\n1. Channel ID format is correct (e.g., -1001234567890)\n2. Bot has been added to the channel\n3. Bot has permission to send messages',
        'test_group_notif_success': '✅ Test group notification sent successfully!\n\nThe notification was sent to your configured group.',
        'test_group_notif_no_group': '❌ Notify group not set\n\nPlease set the notify group ID first.',
        'test_group_notif_error': '❌ Send failed\n\nError: {error}\n\nPlease check:\n1. Group ID format is correct (e.g., -100xxxxxxxxxx)\n2. Bot has been added to the group\n3. Bot has permission to send messages',
    }
}


def get_user_language(update: Update, context: CallbackContext) -> str:
    """Get user's preferred language (zh or en).
    
    Priority:
    1. user.lang field from database
    2. Telegram language_code
    3. Default to 'zh'
    """
    user_id = update.effective_user.id
    
    # Check database first
    try:
        user_doc = user.find_one({'user_id': user_id})
        if user_doc and user_doc.get('lang'):
            lang = user_doc['lang']
            if lang in ['zh', 'en']:
                return lang
    except Exception as e:
        logging.debug(f"Could not fetch user language from DB: {e}")
    
    # Check Telegram language
    if update.effective_user.language_code:
        lang_code = update.effective_user.language_code.lower()
        if lang_code.startswith('zh'):
            return 'zh'
        elif lang_code.startswith('en'):
            return 'en'
    
    # Default to Chinese
    return 'zh'


def t(lang: str, key: str, **kwargs) -> str:
    """Translate a key to the specified language.
    
    Args:
        lang: Language code ('zh' or 'en')
        key: Translation key
        **kwargs: Format parameters for the translation string
    
    Returns:
        Translated string
    """
    if lang not in I18N:
        lang = 'zh'
    
    translation = I18N[lang].get(key, I18N['zh'].get(key, key))
    
    if kwargs:
        try:
            return translation.format(**kwargs)
        except Exception as e:
            logging.error(f"Translation format error for key '{key}': {e}")
            return translation
    
    return translation


def send_agent_notification(context: CallbackContext, text: str, parse_mode: str = None) -> dict:
    """Send a notification to the agent's configured notify channel.
    
    Args:
        context: CallbackContext with agent_id in bot_data
        text: Message text to send
        parse_mode: Optional parse mode ('HTML', 'Markdown', etc.)
    
    Returns:
        Dict with 'success': bool and 'error': str (if failed)
    """
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        return {'success': False, 'error': 'Not an agent bot'}
    
    try:
        agent = agents.find_one({'agent_id': agent_id})
        if not agent:
            return {'success': False, 'error': 'Agent not found'}
        
        settings = agent.get('settings', {})
        notify_channel_id = settings.get('notify_channel_id')
        
        if not notify_channel_id:
            return {'success': False, 'error': 'Notify channel ID not configured'}
        
        # Try to send the message
        try:
            context.bot.send_message(
                chat_id=notify_channel_id,
                text=text,
                parse_mode=parse_mode
            )
            return {'success': True}
        except Exception as send_error:
            error_msg = str(send_error)
            logging.error(f"Failed to send agent notification: {error_msg}")
            return {'success': False, 'error': error_msg}
            
    except Exception as e:
        logging.error(f"Error in send_agent_notification: {e}")
        return {'success': False, 'error': str(e)}


def agent_command(update: Update, context: CallbackContext):
    """Handle /agent command - show agent backend panel.
    
    Only works in child agent bots and only for users in the owners array.
    Allows first-time binding if owners is empty or all owners are admins.
    """
    user_id = update.effective_user.id
    lang = get_user_language(update, context)
    
    # Check if this is an agent bot
    agent_id = context.bot_data.get('agent_id')
    if not agent_id:
        update.message.reply_text(t(lang, 'not_agent_bot'))
        return
    
    # Get agent info
    try:
        agent = agents.find_one({'agent_id': agent_id})
        if not agent:
            update.message.reply_text(t(lang, 'agent_not_found'))
            return
        
        # Lazy migration: convert old owner_user_id to owners array
        owners = agent.get('owners')
        if owners is None:
            # Check for legacy owner_user_id field
            owner_user_id = agent.get('owner_user_id')
            if owner_user_id is not None:
                # Migrate to owners array
                owners = [owner_user_id]
                agents.update_one(
                    {'agent_id': agent_id},
                    {'$set': {'owners': owners}, '$unset': {'owner_user_id': ''}}
                )
                logging.info(f"Migrated agent {agent_id} from owner_user_id to owners array")
            else:
                owners = []
        
        admin_ids = get_admin_ids()
        
        # Check if user can claim ownership (owners empty or all are admins)
        if not owners or all(owner_id in admin_ids for owner_id in owners):
            # Show bind button
            show_bind_panel(update, context, agent, owners, is_callback=False, lang=lang)
            return
        
        # Check if user is an owner
        if user_id not in owners:
            update.message.reply_text(t(lang, 'not_owner'))
            return
        
        # Show agent panel
        show_agent_panel(update, context, agent, is_callback=False, lang=lang)
        
    except Exception as e:
        logging.error(f"Error in agent_command: {e}")
        update.message.reply_text(f"{t(lang, 'error_loading_panel')}: {e}")


def show_bind_panel(update: Update, context: CallbackContext, agent: dict, current_owners: list, is_callback: bool = False, lang: str = 'zh'):
    """Show panel with bind button for claiming ownership."""
    admin_ids = get_admin_ids()
    
    if not current_owners:
        text = f"<b>{t(lang, 'unbound_title')}</b>\n\n{t(lang, 'unbound_message')}"
    elif all(owner_id in admin_ids for owner_id in current_owners):
        text = f"<b>{t(lang, 'rebind_title')}</b>\n\n{t(lang, 'rebind_message')}"
    else:
        text = "❌ 权限错误" if lang == 'zh' else "❌ Permission error"
    
    keyboard = [
        [InlineKeyboardButton(t(lang, 'bind_as_owner'), callback_data="agent_claim_owner")],
        [InlineKeyboardButton(t(lang, 'cancel'), callback_data=f"close {update.effective_user.id}")]
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
    lang = get_user_language(update, context)
    
    if not agent_id:
        query.edit_message_text("❌ Agent context not found." if lang == 'en' else "❌ 未找到代理上下文。")
        return
    
    try:
        agent = agents.find_one({'agent_id': agent_id})
        if not agent:
            query.edit_message_text(t(lang, 'agent_not_found'))
            return
        
        # Get current owners (with migration)
        owners = agent.get('owners')
        if owners is None:
            # Check for legacy owner_user_id
            owner_user_id = agent.get('owner_user_id')
            if owner_user_id is not None:
                owners = [owner_user_id]
            else:
                owners = []
        
        admin_ids = get_admin_ids()
        
        # Verify this is allowed (empty or all admins)
        if owners and not all(owner_id in admin_ids for owner_id in owners):
            query.edit_message_text("❌ This agent already has non-admin owners." if lang == 'en' else "❌ 此代理已有非管理员拥有者。")
            return
        
        # Add user to owners array (replacing any admin owners)
        agents.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    'owners': [user_id],
                    'updated_at': datetime.now()
                },
                '$unset': {'owner_user_id': ''}  # Remove legacy field if exists
            }
        )
        
        logging.info(f"Agent {agent_id} owner claimed by user {user_id}")
        
        # Show success
        success_msg = (
            "✅ <b>Bind Successful!</b>\n\n"
            "You have successfully bound yourself as the owner of this agent.\n\n"
            "Please use /agent command again to open the agent backend."
        ) if lang == 'en' else (
            "✅ <b>绑定成功！</b>\n\n"
            "您已成功绑定为此代理的拥有者。\n\n"
            "请再次使用 /agent 命令打开代理后台。"
        )
        
        query.edit_message_text(success_msg, parse_mode='HTML')
        
    except Exception as e:
        logging.error(f"Error in agent_claim_owner_callback: {e}")
        query.edit_message_text(f"❌ 绑定失败: {e}")


def show_agent_panel(update: Update, context: CallbackContext, agent: dict = None, is_callback: bool = False, lang: str = 'zh'):
    """Show agent backend panel with stats and configuration options."""
    agent_id = context.bot_data.get('agent_id')
    
    if not agent:
        agent = agents.find_one({'agent_id': agent_id})
    
    if not agent:
        text = t(lang, 'agent_not_found')
        if is_callback:
            update.callback_query.edit_message_text(text)
        else:
            update.message.reply_text(text)
        return
    
    # Build panel text
    name = agent.get('name', 'Unnamed Agent')
    # Format financial values to 2 decimal places
    markup_usdt = float(Decimal(str(agent.get('markup_usdt', '0'))).quantize(Decimal('0.01')))
    profit_available = float(Decimal(str(agent.get('profit_available_usdt', '0'))).quantize(Decimal('0.01')))
    profit_frozen = float(Decimal(str(agent.get('profit_frozen_usdt', '0'))).quantize(Decimal('0.01')))
    total_paid = float(Decimal(str(agent.get('total_paid_usdt', '0'))).quantize(Decimal('0.01')))
    
    # Get settings (new structure) - READ ONLY in child agents
    settings = agent.get('settings', {})
    customer_service = settings.get('customer_service') or t(lang, 'not_set')
    official_channel = settings.get('official_channel') or t(lang, 'not_set')
    restock_group = settings.get('restock_group') or t(lang, 'not_set')
    tutorial_link = settings.get('tutorial_link') or t(lang, 'not_set')
    notify_channel_id = settings.get('notify_channel_id') or t(lang, 'not_set')
    notify_group_id = settings.get('notify_group_id') or t(lang, 'not_set')
    
    # Add read-only note for child agents
    readonly_note = "\n\n<i>💡 " + (
        "联系方式由主机器人管理员统一设置，代理机器人只读。" if lang == 'zh' 
        else "Contact settings are managed by main bot admins and are read-only in agent bots."
    ) + "</i>"
    
    text = f"""<b>{t(lang, 'agent_panel_title')} - {name}</b>

<b>{t(lang, 'financial_overview')}</b>
• {t(lang, 'markup_setting')}: {markup_usdt:.2f} USDT/件
• {t(lang, 'available_balance')}: {profit_available:.2f} USDT
• {t(lang, 'frozen_balance')}: {profit_frozen:.2f} USDT
• {t(lang, 'total_paid')}: {total_paid:.2f} USDT

<b>{t(lang, 'contact_info')}</b>
• {t(lang, 'customer_service')}: {customer_service}
• {t(lang, 'official_channel')}: {official_channel}
• {t(lang, 'restock_group')}: {restock_group}
• {t(lang, 'tutorial_link')}: {tutorial_link}
• {t(lang, 'notify_channel_id')}: {notify_channel_id}
• {t(lang, 'notify_group_id')}: {notify_group_id}
{readonly_note}"""
    
    # Build keyboard - REMOVED contact editing buttons for child agents
    # Deduplicate buttons by tracking seen callback_data/url
    seen_buttons = set()
    keyboard = []
    
    # Row 1
    row1 = []
    btn1_data = "agent_set_markup"
    if btn1_data not in seen_buttons:
        row1.append(InlineKeyboardButton(t(lang, 'set_markup'), callback_data=btn1_data))
        seen_buttons.add(btn1_data)
    btn2_data = "agent_withdraw_init"
    if btn2_data not in seen_buttons:
        row1.append(InlineKeyboardButton(t(lang, 'initiate_withdrawal'), callback_data=btn2_data))
        seen_buttons.add(btn2_data)
    if row1:
        keyboard.append(row1)
    
    # Row 2
    row2 = []
    btn3_data = "agent_links_btns"
    if btn3_data not in seen_buttons:
        row2.append(InlineKeyboardButton(t(lang, 'manage_link_buttons'), callback_data=btn3_data))
        seen_buttons.add(btn3_data)
    btn4_data = "agent_stats"
    if btn4_data not in seen_buttons:
        row2.append(InlineKeyboardButton(t(lang, 'business_report'), callback_data=btn4_data))
        seen_buttons.add(btn4_data)
    if row2:
        keyboard.append(row2)
    
    # Row 3
    row3 = []
    btn5_data = "agent_test_notif"
    if btn5_data not in seen_buttons:
        row3.append(InlineKeyboardButton(t(lang, 'send_test_notification'), callback_data=btn5_data))
        seen_buttons.add(btn5_data)
    btn6_data = "agent_group_test"
    if btn6_data not in seen_buttons:
        row3.append(InlineKeyboardButton(t(lang, 'test_group_notification'), callback_data=btn6_data))
        seen_buttons.add(btn6_data)
    if row3:
        keyboard.append(row3)
    
    # Close button
    close_data = f"close {update.effective_user.id}"
    if close_data not in seen_buttons:
        keyboard.append([InlineKeyboardButton(t(lang, 'close'), callback_data=close_data)])
        seen_buttons.add(close_data)
    
    if is_callback:
        safe_edit_message_text(
            update.callback_query,
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard),
            context=context,
            view_name='agent_panel'
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
    lang = get_user_language(update, context)
    
    if not agent_id:
        safe_edit_message_text(query, t(lang, 'not_agent_bot'))
        return
    
    agent = agents.find_one({'agent_id': agent_id})
    show_agent_panel(update, context, agent, is_callback=True, lang=lang)


def agent_test_notif_callback(update: Update, context: CallbackContext):
    """Test notification sending to agent's notify channel."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    lang = get_user_language(update, context)
    
    if not agent_id:
        query.edit_message_text(t(lang, 'not_agent_bot'))
        return
    
    try:
        agent = agents.find_one({'agent_id': agent_id})
        if not agent:
            query.edit_message_text(t(lang, 'agent_not_found'))
            return
        
        settings = agent.get('settings', {})
        notify_channel_id = settings.get('notify_channel_id')
        
        if not notify_channel_id:
            query.answer(t(lang, 'test_notif_no_channel'), show_alert=True)
            return
        
        # Send test notification
        test_message = (
            "🔔 <b>Test Notification</b>\n\n"
            "This is a test notification from your agent bot.\n\n"
            "If you can see this message, your notification channel is configured correctly!"
        ) if lang == 'en' else (
            "🔔 <b>测试通知</b>\n\n"
            "这是来自您的代理机器人的测试通知。\n\n"
            "如果您能看到这条消息，说明您的通知频道配置正确！"
        )
        
        result = send_agent_notification(context, test_message, parse_mode='HTML')
        
        if result['success']:
            query.answer(t(lang, 'test_notif_success'), show_alert=True)
        else:
            error_msg = t(lang, 'test_notif_error', error=result.get('error', 'Unknown'))
            query.answer(error_msg, show_alert=True)
            
    except Exception as e:
        logging.error(f"Error in agent_test_notif_callback: {e}")
        query.answer(f"❌ Error: {e}", show_alert=True)
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


# DEPRECATED: Contact setting callbacks are now managed by main bot admins only
# Child agents show read-only contact information
def agent_cfg_cs_callback(update: Update, context: CallbackContext):
    """DEPRECATED: Contact settings now managed by main bot admin only."""
    query = update.callback_query
    query.answer("⚠️ 联系方式由主机器人管理员统一设置", show_alert=True)
    logging.warning("Attempt to use deprecated agent_cfg_cs_callback - settings now admin-only")


def agent_cfg_official_callback(update: Update, context: CallbackContext):
    """DEPRECATED: Contact settings now managed by main bot admin only."""
    query = update.callback_query
    query.answer("⚠️ 联系方式由主机器人管理员统一设置", show_alert=True)
    logging.warning("Attempt to use deprecated agent_cfg_official_callback - settings now admin-only")


def agent_cfg_restock_callback(update: Update, context: CallbackContext):
    """DEPRECATED: Contact settings now managed by main bot admin only."""
    query = update.callback_query
    query.answer("⚠️ 联系方式由主机器人管理员统一设置", show_alert=True)
    logging.warning("Attempt to use deprecated agent_cfg_restock_callback - settings now admin-only")


def agent_cfg_tutorial_callback(update: Update, context: CallbackContext):
    """DEPRECATED: Contact settings now managed by main bot admin only."""
    query = update.callback_query
    query.answer("⚠️ 联系方式由主机器人管理员统一设置", show_alert=True)
    logging.warning("Attempt to use deprecated agent_cfg_tutorial_callback - settings now admin-only")


def agent_cfg_notify_callback(update: Update, context: CallbackContext):
    """DEPRECATED: Contact settings now managed by main bot admin only."""
    query = update.callback_query
    query.answer("⚠️ 通知设置由主机器人管理员统一设置", show_alert=True)
    logging.warning("Attempt to use deprecated agent_cfg_notify_callback - settings now admin-only")


# LEGACY CODE BELOW - Kept for reference but disabled
# def agent_cfg_cs_callback(update: Update, context: CallbackContext):
#     """Initiate customer service setting flow."""
#     query = update.callback_query
#     query.answer()
#     
#     agent_id = context.bot_data.get('agent_id')
#     if not agent_id:
#         query.edit_message_text("❌ Not an agent bot.")
#         return
#     
#     # Set state
#     context.user_data['agent_backend_state'] = 'awaiting_cs_input'
#     
#     text = """<b>📞 设置客服</b>
# 
# 请发送客服联系方式
# 
# 支持的格式：
# • 单个客服: <code>@customer_service</code>
# • 多个客服: <code>@cs1 @cs2 @cs3</code> (用空格分隔)
# • 客服链接: <code>https://t.me/customer_service</code>
# 
# 发送 <code>清除</code> 可以清除当前设置"""
#     
#     keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="agent_panel")]]
#     
#     query.edit_message_text(
#         text=text,
#         parse_mode='HTML',
#         reply_markup=InlineKeyboardMarkup(keyboard)
#     )
# 
# 
# def agent_cfg_official_callback(update: Update, context: CallbackContext):
#     """Initiate official channel setting flow."""
#     query = update.callback_query
#     query.answer()
# 
# 
# The above legacy code has been removed. Contact settings are now managed by main bot admins only.


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
        # Contact settings removed - now managed by main bot admin only
        # elif state == 'awaiting_cs_input':
        #     handle_setting_input(update, context, agent_id, 'customer_service', text, '客服')
        # elif state == 'awaiting_official_input':
        #     handle_setting_input(update, context, agent_id, 'official_channel', text, '官方频道')
        # elif state == 'awaiting_restock_input':
        #     handle_setting_input(update, context, agent_id, 'restock_group', text, '补货通知群')
        # elif state == 'awaiting_tutorial_input':
        #     handle_tutorial_input(update, context, agent_id, text)
        # elif state == 'awaiting_notify_input':
        #     handle_notify_channel_input(update, context, agent_id, text)
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
    user_id = update.effective_user.id
    
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
            'requester_user_id': user_id,  # Changed from owner_user_id to requester_user_id
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


def handle_notify_group_input(update: Update, context: CallbackContext, agent_id: str, text: str):
    """Handle notify group ID input with numeric validation."""
    if text == '清除':
        agents.update_one(
            {'agent_id': agent_id},
            {
                '$set': {
                    'settings.notify_group_id': None,
                    'updated_at': datetime.now()
                },
                '$unset': {'settings.notify_group_id': ""}
            }
        )
        
        context.user_data.pop('agent_backend_state', None)
        update.message.reply_text("✅ 通知群ID已清除")
        return
    
    # Validate numeric ID or @username
    text = text.strip()
    
    # Accept @username format or numeric ID
    if text.startswith('@'):
        # Username format is acceptable
        group_id = text
    elif text.lstrip('-').isdigit():
        # Numeric ID format (should start with -100 for supergroups)
        group_id = text
    else:
        update.message.reply_text(
            "❌ 通知群ID格式错误\n\n"
            "请发送有效的群组ID或@用户名\n\n"
            "示例: <code>-100123456789</code> 或 <code>@mygroup</code>",
            parse_mode='HTML'
        )
        return
    
    # Update setting
    agents.update_one(
        {'agent_id': agent_id},
        {
            '$set': {
                'settings.notify_group_id': group_id,
                'updated_at': datetime.now()
            }
        }
    )
    
    context.user_data.pop('agent_backend_state', None)
    update.message.reply_text(f"✅ 通知群ID设置成功！\n\n<b>新ID:</b> <code>{group_id}</code>", parse_mode='HTML')



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


def agent_cfg_group_callback(update: Update, context: CallbackContext):
    """Initiate notify group ID configuration."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    lang = get_user_language(update, context)
    
    if not agent_id:
        query.edit_message_text(t(lang, 'not_agent_bot'))
        return
    
    agent = agents.find_one({'agent_id': agent_id})
    settings = agent.get('settings', {})
    current_group_id = settings.get('notify_group_id', t(lang, 'not_set'))
    
    text = (
        f"<b>👥 {t(lang, 'set_notify_group')}</b>\n\n"
        f"当前设置: <code>{current_group_id}</code>\n\n"
        f"请发送新的通知群ID (数字格式，例如: -100xxxxxxxxxx)\n"
        f"或发送群组@用户名 (例如: @mygroup)\n\n"
        f"<b>提示:</b>\n"
        f"1. 将机器人添加到您的群组\n"
        f"2. 授予机器人发送消息的权限\n"
        f"3. 使用 /getid 命令获取群组ID\n"
        f"或转发群组消息给 @userinfobot 获取ID"
    ) if lang == 'zh' else (
        f"<b>👥 {t(lang, 'set_notify_group')}</b>\n\n"
        f"Current setting: <code>{current_group_id}</code>\n\n"
        f"Please send the new notify group ID (numeric format, e.g., -100xxxxxxxxxx)\n"
        f"or send group @username (e.g., @mygroup)\n\n"
        f"<b>Tips:</b>\n"
        f"1. Add the bot to your group\n"
        f"2. Grant the bot permission to send messages\n"
        f"3. Use /getid command to get the group ID\n"
        f"or forward a group message to @userinfobot to get the ID"
    )
    
    context.user_data['agent_backend_state'] = 'awaiting_notify_group_id'
    
    keyboard = [[InlineKeyboardButton(t(lang, 'cancel'), callback_data="agent_panel")]]
    query.edit_message_text(text=text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))


def agent_group_test_callback(update: Update, context: CallbackContext):
    """Test group notification sending."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    lang = get_user_language(update, context)
    
    if not agent_id:
        query.edit_message_text(t(lang, 'not_agent_bot'))
        return
    
    try:
        from services.agent_group_notifications import (
            get_notify_group_id_for_child,
            format_test_notification,
            send_agent_group_message
        )
        from datetime import datetime
        
        agent = agents.find_one({'agent_id': agent_id})
        if not agent:
            query.edit_message_text(t(lang, 'agent_not_found'))
            return
        
        group_id = get_notify_group_id_for_child(context)
        
        if group_id is None:
            query.answer(t(lang, 'test_group_notif_no_group'), show_alert=True)
            return
        
        # Send test notification
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        test_message = format_test_notification(lang, timestamp)
        
        success = send_agent_group_message(context, test_message)
        
        if success:
            query.answer(t(lang, 'test_group_notif_success'), show_alert=True)
        else:
            error_msg = t(lang, 'test_group_notif_error', error='Check logs for details')
            query.answer(error_msg, show_alert=True)
            
    except Exception as e:
        logging.error(f"Error in agent_group_test_callback: {e}")
        query.answer(f"❌ Error: {e}", show_alert=True)
    
    # Refresh panel
    show_agent_panel(update, context, agent, is_callback=True, lang=lang)


def agent_stats_callback(update: Update, context: CallbackContext):
    """Show agent business statistics/analytics dashboard."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    lang = get_user_language(update, context)
    
    if not agent_id:
        query.edit_message_text(t(lang, 'not_agent_bot'))
        return
    
    try:
        # Default to 'all' time range
        time_range = context.user_data.get('agent_stats_range', 'all')
        show_agent_stats_dashboard(update, context, agent_id, time_range, lang, is_callback=True)
        
    except Exception as e:
        logging.error(f"Error in agent_stats_callback: {e}")
        query.edit_message_text(f"❌ {t(lang, 'error_loading_panel')}: {e}")


def show_agent_stats_dashboard(
    update: Update,
    context: CallbackContext,
    agent_id: str,
    time_range: str = 'all',
    lang: str = 'zh',
    is_callback: bool = False
):
    """Display agent statistics dashboard with time range filters.
    
    Args:
        update: Update object
        context: CallbackContext
        agent_id: Agent identifier
        time_range: Time range filter ('24h', '7d', 'all')
        lang: Language code
        is_callback: Whether this is from a callback
    """
    from datetime import datetime, timedelta
    from mongo import agents, user, gmjlu, topup
    
    try:
        agent = agents.find_one({'agent_id': agent_id})
        if not agent:
            text = t(lang, 'agent_not_found')
            if is_callback:
                update.callback_query.edit_message_text(text)
            else:
                update.message.reply_text(text)
            return
        
        # Get agent info
        agent_name = agent.get('name', 'N/A')
        bot_username = context.bot_data.get('bot_username', 'N/A')
        # Format markup to 2 decimal places
        markup_usdt = Decimal(str(agent.get('markup_usdt', '0'))).quantize(Decimal('0.01'))
        
        # Calculate time filter
        now = datetime.now()
        time_filter = {}
        
        if time_range == '24h':
            time_filter = {'$gte': now - timedelta(hours=24)}
            range_label = '近24小时' if lang == 'zh' else 'Last 24 Hours'
        elif time_range == '7d':
            time_filter = {'$gte': now - timedelta(days=7)}
            range_label = '近7天' if lang == 'zh' else 'Last 7 Days'
        else:  # 'all'
            range_label = '全部' if lang == 'zh' else 'All Time'
        
        # Query statistics
        # Total users for this agent
        total_users = user.count_documents({'agent_id': agent_id}) if user.find_one({'agent_id': {'$exists': True}}) else 0
        
        # New users in time range (if time field exists)
        new_users_24h = 0
        new_users_7d = 0
        if time_filter:
            # Try to get new users - this depends on having a registration timestamp
            # Since the schema might not have this, we'll set to 0 for now
            new_users_24h = 0
            new_users_7d = 0
        
        # Orders (gmjlu collection likely has agent_id and time fields)
        order_query = {'agent_id': agent_id} if gmjlu.find_one({'agent_id': {'$exists': True}}) else {}
        if time_filter and order_query:
            # Assuming gmjlu has a 'time' field
            try:
                order_query['time'] = time_filter
                total_orders = gmjlu.count_documents(order_query)
            except:
                total_orders = gmjlu.count_documents({'agent_id': agent_id}) if order_query else 0
        else:
            total_orders = gmjlu.count_documents(order_query) if order_query else 0
        
        # Recharges (topup collection)
        recharge_query = {
            'agent_id': agent_id,
            'status': 'completed'
        } if topup.find_one({'agent_id': {'$exists': True}}) else {'status': 'completed'}
        
        if time_filter and 'agent_id' in recharge_query:
            try:
                recharge_query['credited_at'] = time_filter
                recharge_count = topup.count_documents(recharge_query)
                # Sum of recharge amounts
                recharge_pipeline = [
                    {'$match': recharge_query},
                    {'$group': {'_id': None, 'total': {'$sum': '$usdt'}}}
                ]
                recharge_result = list(topup.aggregate(recharge_pipeline))
                recharge_total = recharge_result[0]['total'] if recharge_result else 0
            except:
                recharge_count = 0
                recharge_total = 0
        else:
            recharge_count = 0
            recharge_total = 0
        
        # Calculate profit (from agent document or order aggregation)
        # For simplicity, use agent's recorded profit
        profit_available = float(agent.get('profit_available_usdt', 0))
        profit_frozen = float(agent.get('profit_frozen_usdt', 0))
        total_paid = float(agent.get('total_paid_usdt', 0))
        total_profit = profit_available + profit_frozen + total_paid
        
        # Build message
        if lang == 'zh':
            text = f"""<b>📊 经营报告</b>

<b>号铺名：</b>{agent_name} (@{bot_username})
<b>分销利润率（差价）：</b>+{markup_usdt}U/件
<b>时间范围：</b>{range_label}

<b>👥 用户数据</b>
• 用户总数: {total_users}
• 近24小时新增: {new_users_24h}
• 近7天新增: {new_users_7d}

<b>🛒 订单数据</b>
• 购买总数: {total_orders}

<b>💰 充值数据</b>
• 充值笔数: {recharge_count}
• 充值总额: {recharge_total:.2f} USDT

<b>💎 利润数据</b>
• 累计利润: {total_profit:.2f} USDT
  ├─ 可提现: {profit_available:.2f} USDT
  ├─ 冻结中: {profit_frozen:.2f} USDT
  └─ 已提现: {total_paid:.2f} USDT"""
        else:
            text = f"""<b>📊 Business Report</b>

<b>Shop Name:</b>{agent_name} (@{bot_username})
<b>Markup Rate:</b>+{markup_usdt}U/item
<b>Time Range:</b>{range_label}

<b>👥 User Data</b>
• Total Users: {total_users}
• New (24h): {new_users_24h}
• New (7d): {new_users_7d}

<b>🛒 Order Data</b>
• Total Orders: {total_orders}

<b>💰 Recharge Data</b>
• Recharge Count: {recharge_count}
• Total Amount: {recharge_total:.2f} USDT

<b>💎 Profit Data</b>
• Total Profit: {total_profit:.2f} USDT
  ├─ Available: {profit_available:.2f} USDT
  ├─ Frozen: {profit_frozen:.2f} USDT
  └─ Withdrawn: {total_paid:.2f} USDT"""
        
        # Build keyboard with time range filters
        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ 近24小时" if time_range == '24h' else "近24小时" if lang == 'zh' else "✅ 24h" if time_range == '24h' else "24h",
                    callback_data="agent_stats_range_24h"
                ),
                InlineKeyboardButton(
                    "✅ 近7天" if time_range == '7d' else "近7天" if lang == 'zh' else "✅ 7d" if time_range == '7d' else "7d",
                    callback_data="agent_stats_range_7d"
                ),
                InlineKeyboardButton(
                    "✅ 全部" if time_range == 'all' else "全部" if lang == 'zh' else "✅ All" if time_range == 'all' else "All",
                    callback_data="agent_stats_range_all"
                )
            ],
            [InlineKeyboardButton(
                "🔙 返回" if lang == 'zh' else "🔙 Back",
                callback_data="agent_panel"
            )]
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
        
    except Exception as e:
        logging.error(f"Error in show_agent_stats_dashboard: {e}")
        error_text = f"❌ {t(lang, 'error_loading_panel')}: {e}"
        if is_callback:
            update.callback_query.edit_message_text(error_text)
        else:
            update.message.reply_text(error_text)


def agent_stats_range_callback(update: Update, context: CallbackContext):
    """Handle time range selection for agent stats."""
    query = update.callback_query
    query.answer()
    
    agent_id = context.bot_data.get('agent_id')
    lang = get_user_language(update, context)
    
    # Extract time range from callback data
    callback_data = query.data
    if 'range_24h' in callback_data:
        time_range = '24h'
    elif 'range_7d' in callback_data:
        time_range = '7d'
    else:  # range_all
        time_range = 'all'
    
    # Store in user_data
    context.user_data['agent_stats_range'] = time_range
    
    # Show stats with new range
    show_agent_stats_dashboard(update, context, agent_id, time_range, lang, is_callback=True)

