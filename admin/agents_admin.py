"""Admin handlers for agent management.

This module provides admin commands and callbacks for creating, pausing,
resuming agents, and managing their pricing.
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext

from services.agent_service import (
    create_agent, list_agents, update_agent_status, 
    update_agent_pricing, get_agent_by_id
)
from services.tenant import get_tenant_string
from services.message_utils import safe_edit_message_text
from models.constants import (
    AGENT_STATUS_ACTIVE, AGENT_STATUS_PAUSED, AGENT_STATUS_SUSPENDED,
    MARKUP_TYPE_FIXED, MARKUP_TYPE_PERCENT
)
from mongo import bot_db
from agents_runner import start_agent_bot, stop_agent_bot, get_running_agents


def agent_create_command(update: Update, context: CallbackContext):
    """Handle /agent_create command to create a new agent.
    
    Usage: /agent_create <agent_id> <bot_token> <name>
    """
    user_id = update.effective_user.id
    
    # Check if user is admin (this check should be done by the caller)
    # Assuming is_admin(user_id) check is done before calling
    
    try:
        args = context.args
        if len(args) < 3:
            update.message.reply_text(
                "❌ Usage: /agent_create <agent_id> <bot_token> <name>\n\n"
                "Example: /agent_create agent001 1234567890:ABCdef... MyAgentBot"
            )
            return
        
        agent_id = args[0]
        bot_token = args[1]
        name = ' '.join(args[2:])
        
        # Create the agent
        agents_collection = bot_db['agents']
        agent_doc = create_agent(
            agents_collection,
            agent_id=agent_id,
            bot_token=bot_token,
            name=name,
            created_by_admin_id=user_id
        )
        
        if not agent_doc:
            update.message.reply_text(
                f"❌ Failed to create agent. Agent ID '{agent_id}' may already exist."
            )
            return
        
        # Start the agent bot
        success = start_agent_bot(agent_id, agent_doc)
        
        if success:
            tenant = get_tenant_string(agent_id)
            update.message.reply_text(
                f"✅ Agent created and started successfully!\n\n"
                f"<b>Agent ID:</b> <code>{agent_id}</code>\n"
                f"<b>Name:</b> {name}\n"
                f"<b>Tenant:</b> <code>{tenant}</code>\n"
                f"<b>Status:</b> {AGENT_STATUS_ACTIVE}\n"
                f"<b>Markup:</b> 0% (default)\n\n"
                f"Use /agent_pricing {agent_id} to set pricing.",
                parse_mode='HTML'
            )
        else:
            update.message.reply_text(
                f"⚠️ Agent created but failed to start.\n\n"
                f"<b>Agent ID:</b> <code>{agent_id}</code>\n"
                f"<b>Name:</b> {name}\n\n"
                f"Check logs for details.",
                parse_mode='HTML'
            )
        
    except Exception as e:
        logging.error(f"Error in agent_create_command: {e}")
        update.message.reply_text(f"❌ Error creating agent: {e}")


def agent_list_command(update: Update, context: CallbackContext):
    """Handle /agent_list command to list all agents."""
    try:
        agents_collection = bot_db['agents']
        agents = list_agents(agents_collection)
        
        if not agents:
            update.message.reply_text("No agents found.")
            return
        
        running_agent_ids = set(get_running_agents())
        
        text = "<b>📋 Agent List</b>\n\n"
        
        for agent in agents:
            agent_id = agent['agent_id']
            name = agent['name']
            status = agent['status']
            pricing = agent.get('pricing', {})
            markup_type = pricing.get('markup_type', 'percent')
            markup_value = pricing.get('markup_value', 0)
            
            is_running = "🟢" if agent_id in running_agent_ids else "🔴"
            
            text += (
                f"{is_running} <b>{name}</b>\n"
                f"  • ID: <code>{agent_id}</code>\n"
                f"  • Status: {status}\n"
                f"  • Markup: {markup_value}"
                f"{'%' if markup_type == MARKUP_TYPE_PERCENT else ' USDT'}\n"
                f"  • Created: {agent.get('created_at', 'N/A')}\n\n"
            )
        
        update.message.reply_text(text, parse_mode='HTML')
        
    except Exception as e:
        logging.error(f"Error in agent_list_command: {e}")
        update.message.reply_text(f"❌ Error listing agents: {e}")


def agent_pause_command(update: Update, context: CallbackContext):
    """Handle /agent_pause command to pause an agent.
    
    Usage: /agent_pause <agent_id>
    """
    try:
        args = context.args
        if len(args) < 1:
            update.message.reply_text("❌ Usage: /agent_pause <agent_id>")
            return
        
        agent_id = args[0]
        
        # Update status to paused
        agents_collection = bot_db['agents']
        success = update_agent_status(agents_collection, agent_id, AGENT_STATUS_PAUSED)
        
        if not success:
            update.message.reply_text(f"❌ Failed to pause agent '{agent_id}'")
            return
        
        # Stop the bot
        stop_agent_bot(agent_id)
        
        update.message.reply_text(
            f"✅ Agent '{agent_id}' has been paused and stopped."
        )
        
    except Exception as e:
        logging.error(f"Error in agent_pause_command: {e}")
        update.message.reply_text(f"❌ Error pausing agent: {e}")


def agent_resume_command(update: Update, context: CallbackContext):
    """Handle /agent_resume command to resume a paused agent.
    
    Usage: /agent_resume <agent_id>
    """
    try:
        args = context.args
        if len(args) < 1:
            update.message.reply_text("❌ Usage: /agent_resume <agent_id>")
            return
        
        agent_id = args[0]
        
        # Update status to active
        agents_collection = bot_db['agents']
        success = update_agent_status(agents_collection, agent_id, AGENT_STATUS_ACTIVE)
        
        if not success:
            update.message.reply_text(f"❌ Failed to resume agent '{agent_id}'")
            return
        
        # Get agent doc and start the bot
        agent_doc = get_agent_by_id(agents_collection, agent_id)
        if not agent_doc:
            update.message.reply_text(f"❌ Agent '{agent_id}' not found")
            return
        
        start_agent_bot(agent_id, agent_doc)
        
        update.message.reply_text(
            f"✅ Agent '{agent_id}' has been resumed and started."
        )
        
    except Exception as e:
        logging.error(f"Error in agent_resume_command: {e}")
        update.message.reply_text(f"❌ Error resuming agent: {e}")


def agent_pricing_command(update: Update, context: CallbackContext):
    """Handle /agent_pricing command to set agent pricing.
    
    Usage: /agent_pricing <agent_id> <percent|fixed> <value>
    Examples:
      /agent_pricing agent001 percent 10    (10% markup)
      /agent_pricing agent001 fixed 5       (5 USDT markup per item)
    """
    try:
        args = context.args
        if len(args) < 3:
            update.message.reply_text(
                "❌ Usage: /agent_pricing <agent_id> <percent|fixed> <value>\n\n"
                "Examples:\n"
                "  /agent_pricing agent001 percent 10\n"
                "  /agent_pricing agent001 fixed 5"
            )
            return
        
        agent_id = args[0]
        markup_type = args[1].lower()
        
        if markup_type not in ['percent', 'fixed']:
            update.message.reply_text("❌ Markup type must be 'percent' or 'fixed'")
            return
        
        try:
            markup_value = float(args[2])
        except ValueError:
            update.message.reply_text("❌ Markup value must be a number")
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
            update.message.reply_text(f"❌ Failed to update pricing for agent '{agent_id}'")
            return
        
        update.message.reply_text(
            f"✅ Pricing updated for agent '{agent_id}':\n"
            f"  • Type: {markup_type}\n"
            f"  • Value: {markup_value}{'%' if markup_type == MARKUP_TYPE_PERCENT else ' USDT'}"
        )
        
    except Exception as e:
        logging.error(f"Error in agent_pricing_command: {e}")
        update.message.reply_text(f"❌ Error updating pricing: {e}")


def agent_panel_callback(update: Update, context: CallbackContext):
    """Show agent management panel."""
    query = update.callback_query
    query.answer()
    
    try:
        agents_collection = bot_db['agents']
        agents = list_agents(agents_collection)
        running_agent_ids = set(get_running_agents())
        
        text = "<b>🤖 Agent Management Panel</b>\n\n"
        text += f"Total agents: {len(agents)}\n"
        text += f"Running: {len(running_agent_ids)}\n\n"
        text += "Use commands:\n"
        text += "  /agent_create - Create new agent\n"
        text += "  /agent_list - List all agents\n"
        text += "  /agent_pause - Pause an agent\n"
        text += "  /agent_resume - Resume an agent\n"
        text += "  /agent_pricing - Set agent pricing\n"
        
        keyboard = [
            [InlineKeyboardButton("📋 List Agents", callback_data="agent_list_view")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="backstart")],
            [InlineKeyboardButton("❌ Close", callback_data=f"close {query.from_user.id}")]
        ]
        
        safe_edit_message_text(
            query,
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in agent_panel_callback: {e}")
        safe_edit_message_text(query, f"❌ Error loading agent panel: {e}")


def agent_list_view_callback(update: Update, context: CallbackContext):
    """Show detailed agent list with action buttons."""
    query = update.callback_query
    query.answer()
    
    try:
        agents_collection = bot_db['agents']
        agents = list_agents(agents_collection)
        running_agent_ids = set(get_running_agents())
        
        if not agents:
            safe_edit_message_text(
                query,
                "No agents found.\n\nUse /agent_create to create a new agent."
            )
            return
        
        text = "<b>📋 Agent List</b>\n\n"
        keyboard = []
        
        for agent in agents:
            agent_id = agent['agent_id']
            name = agent['name']
            status = agent['status']
            is_running = agent_id in running_agent_ids
            
            status_icon = "🟢" if is_running else "🔴"
            text += f"{status_icon} <b>{name}</b> ({agent_id}) - {status}\n"
            
            # Add action button for each agent
            keyboard.append([
                InlineKeyboardButton(
                    f"⚙️ {name}",
                    callback_data=f"agent_detail {agent_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="agent_panel")])
        keyboard.append([InlineKeyboardButton("❌ Close", callback_data=f"close {query.from_user.id}")])
        
        safe_edit_message_text(
            query,
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in agent_list_view_callback: {e}")
        safe_edit_message_text(query, f"❌ Error loading agent list: {e}")


def agent_detail_callback(update: Update, context: CallbackContext):
    """Show detailed view of a specific agent with management options."""
    query = update.callback_query
    query.answer()
    
    try:
        # Extract agent_id from callback_data "agent_detail <agent_id>"
        agent_id = query.data.split(' ', 1)[1]
        
        agents_collection = bot_db['agents']
        agent = get_agent_by_id(agents_collection, agent_id)
        
        if not agent:
            safe_edit_message_text(query, f"❌ Agent '{agent_id}' not found")
            return
        
        name = agent.get('name', 'Unnamed')
        status = agent.get('status', 'unknown')
        running_agent_ids = set(get_running_agents())
        is_running = agent_id in running_agent_ids
        
        text = f"""<b>🤖 Agent Details: {name}</b>

<b>ID:</b> <code>{agent_id}</code>
<b>Status:</b> {status} {'🟢 Running' if is_running else '🔴 Stopped'}
<b>Created:</b> {agent.get('created_at', 'N/A')}

<b>Management Options:</b>"""
        
        keyboard = [
            [InlineKeyboardButton("🛠 代理联系方式设置", callback_data=f"agent_settings {agent_id}")],
            [InlineKeyboardButton("⬅️ Back to List", callback_data="agent_list_view")],
            [InlineKeyboardButton("❌ Close", callback_data=f"close {query.from_user.id}")]
        ]
        
        safe_edit_message_text(
            query,
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in agent_detail_callback: {e}")
        safe_edit_message_text(query, f"❌ Error loading agent details: {e}")


def agent_settings_callback(update: Update, context: CallbackContext):
    """Show agent contact settings management panel."""
    query = update.callback_query
    query.answer()
    
    try:
        # Extract agent_id from callback_data "agent_settings <agent_id>"
        agent_id = query.data.split(' ', 1)[1]
        
        agents_collection = bot_db['agents']
        agent = get_agent_by_id(agents_collection, agent_id)
        
        if not agent:
            safe_edit_message_text(query, f"❌ Agent '{agent_id}' not found")
            return
        
        name = agent.get('name', 'Unnamed')
        settings = agent.get('settings', {})
        
        # Get current settings
        customer_service = settings.get('customer_service') or '未设置'
        official_channel = settings.get('official_channel') or '未设置'
        restock_group = settings.get('restock_group') or '未设置'
        tutorial_link = settings.get('tutorial_link') or '未设置'
        notify_channel_id = settings.get('notify_channel_id') or '未设置'
        notify_group_id = settings.get('notify_group_id') or '未设置'
        
        text = f"""<b>🛠 代理联系方式设置 - {name}</b>

<b>当前设置:</b>
• 客服: {customer_service}
• 官方频道: {official_channel}
• 补货通知群: {restock_group}
• 教程链接: {tutorial_link}
• 通知频道ID: {notify_channel_id}
• 通知群组ID: {notify_group_id}

选择要设置的项目:"""
        
        keyboard = [
            [
                InlineKeyboardButton("📞 设置客服", callback_data=f"admin_set_cs {agent_id}"),
                InlineKeyboardButton("📢 设置官方频道", callback_data=f"admin_set_official {agent_id}")
            ],
            [
                InlineKeyboardButton("📣 设置补货通知群", callback_data=f"admin_set_restock {agent_id}"),
                InlineKeyboardButton("📖 设置教程链接", callback_data=f"admin_set_tutorial {agent_id}")
            ],
            [
                InlineKeyboardButton("🔔 设置通知频道ID", callback_data=f"admin_set_notify_channel {agent_id}"),
                InlineKeyboardButton("👥 设置通知群组ID", callback_data=f"admin_set_notify_group {agent_id}")
            ],
            [InlineKeyboardButton("⬅️ 返回", callback_data=f"agent_detail {agent_id}")],
            [InlineKeyboardButton("❌ 关闭", callback_data=f"close {query.from_user.id}")]
        ]
        
        safe_edit_message_text(
            query,
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in agent_settings_callback: {e}")
        safe_edit_message_text(query, f"❌ Error loading agent settings: {e}")


# Admin setting handlers
def admin_set_cs_callback(update: Update, context: CallbackContext):
    """Initiate customer service setting for agent."""
    query = update.callback_query
    query.answer()
    
    agent_id = query.data.split(' ', 1)[1]
    context.user_data['admin_setting_flow'] = {
        'agent_id': agent_id,
        'field': 'customer_service',
        'field_name': '客服',
        'state': 'awaiting_input'
    }
    
    text = """<b>📞 设置代理客服</b>

请发送客服联系方式

支持的格式：
• 单个客服: <code>@customer_service</code>
• 多个客服: <code>@cs1 @cs2 @cs3</code> (用空格分隔)
• 客服链接: <code>https://t.me/customer_service</code>

发送 <code>清除</code> 可以清除当前设置"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data=f"agent_settings {agent_id}")]]
    
    safe_edit_message_text(
        query,
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def admin_set_official_callback(update: Update, context: CallbackContext):
    """Initiate official channel setting for agent."""
    query = update.callback_query
    query.answer()
    
    agent_id = query.data.split(' ', 1)[1]
    context.user_data['admin_setting_flow'] = {
        'agent_id': agent_id,
        'field': 'official_channel',
        'field_name': '官方频道',
        'state': 'awaiting_input'
    }
    
    text = """<b>📢 设置代理官方频道</b>

请发送官方频道链接

支持的格式：
• 频道用户名: <code>@yourchannel</code>
• 频道链接: <code>https://t.me/yourchannel</code>

发送 <code>清除</code> 可以清除当前设置"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data=f"agent_settings {agent_id}")]]
    
    safe_edit_message_text(
        query,
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def admin_set_restock_callback(update: Update, context: CallbackContext):
    """Initiate restock group setting for agent."""
    query = update.callback_query
    query.answer()
    
    agent_id = query.data.split(' ', 1)[1]
    context.user_data['admin_setting_flow'] = {
        'agent_id': agent_id,
        'field': 'restock_group',
        'field_name': '补货通知群',
        'state': 'awaiting_input'
    }
    
    text = """<b>📣 设置代理补货通知群</b>

请发送补货通知群链接

支持的格式：
• 群组用户名: <code>@yourgroup</code>
• 群组链接: <code>https://t.me/yourgroup</code>
• 群组邀请链接: <code>https://t.me/+xxxxx</code>

发送 <code>清除</code> 可以清除当前设置"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data=f"agent_settings {agent_id}")]]
    
    safe_edit_message_text(
        query,
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def admin_set_tutorial_callback(update: Update, context: CallbackContext):
    """Initiate tutorial link setting for agent."""
    query = update.callback_query
    query.answer()
    
    agent_id = query.data.split(' ', 1)[1]
    context.user_data['admin_setting_flow'] = {
        'agent_id': agent_id,
        'field': 'tutorial_link',
        'field_name': '教程链接',
        'state': 'awaiting_tutorial_input'
    }
    
    text = """<b>📖 设置代理教程链接</b>

请发送教程页面链接

<b>要求:</b>
• 必须是有效的 URL (http:// 或 https://)
• 可以是任何网页链接

示例:
• <code>https://example.com/tutorial</code>
• <code>https://docs.google.com/document/xxx</code>

发送 <code>清除</code> 可以清除当前设置"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data=f"agent_settings {agent_id}")]]
    
    safe_edit_message_text(
        query,
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def admin_set_notify_channel_callback(update: Update, context: CallbackContext):
    """Initiate notify channel ID setting for agent."""
    query = update.callback_query
    query.answer()
    
    agent_id = query.data.split(' ', 1)[1]
    context.user_data['admin_setting_flow'] = {
        'agent_id': agent_id,
        'field': 'notify_channel_id',
        'field_name': '通知频道ID',
        'state': 'awaiting_notify_input'
    }
    
    text = """<b>🔔 设置代理通知频道ID</b>

请发送通知频道的数字ID或用户名

<b>如何获取频道ID:</b>
1. 将机器人添加到您的频道
2. 在频道发送一条消息
3. 使用 @username_to_id_bot 等工具获取频道ID

<b>格式要求:</b>
• 数字ID (通常以 -100 开头): <code>-100123456789</code>
• 或频道用户名: <code>@yourchannel</code>

发送 <code>清除</code> 可以清除当前设置"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data=f"agent_settings {agent_id}")]]
    
    safe_edit_message_text(
        query,
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def admin_set_notify_group_callback(update: Update, context: CallbackContext):
    """Initiate notify group ID setting for agent."""
    query = update.callback_query
    query.answer()
    
    agent_id = query.data.split(' ', 1)[1]
    context.user_data['admin_setting_flow'] = {
        'agent_id': agent_id,
        'field': 'notify_group_id',
        'field_name': '通知群组ID',
        'state': 'awaiting_notify_input'
    }
    
    text = """<b>👥 设置代理通知群组ID</b>

请发送通知群组的数字ID或用户名

<b>如何获取群组ID:</b>
1. 将机器人添加到您的群组
2. 在群组发送一条消息
3. 使用 @username_to_id_bot 等工具获取群组ID

<b>格式要求:</b>
• 数字ID (通常以负数开头): <code>-123456789</code>
• 或群组用户名: <code>@yourgroup</code>

发送 <code>清除</code> 可以清除当前设置

<b>注意:</b> 群组主题支持 (message_thread_id) 将在未来版本中添加"""
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data=f"agent_settings {agent_id}")]]
    
    safe_edit_message_text(
        query,
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )



def admin_setting_text_input(update: Update, context: CallbackContext):
    """Handle text input for admin setting flows."""
    from datetime import datetime
    from mongo import agents
    
    flow = context.user_data.get("admin_setting_flow")
    
    if not flow or flow.get("state") not in ["awaiting_input", "awaiting_tutorial_input", "awaiting_notify_input"]:
        return  # Not in a flow
    
    agent_id = flow["agent_id"]
    field = flow["field"]
    field_name = flow["field_name"]
    text = update.message.text.strip()
    
    try:
        # Handle clearing
        if text == "清除":
            agents.update_one(
                {"agent_id": agent_id},
                {
                    "$set": {
                        f"settings.{field}": None,
                        "updated_at": datetime.now()
                    },
                    "$unset": {f"settings.{field}": ""}
                }
            )
            
            context.user_data.pop("admin_setting_flow", None)
            update.message.reply_text(f"✅ {field_name}已清除")
            return
        
        # Validate based on field type
        if flow["state"] == "awaiting_tutorial_input":
            # Validate URL
            if not (text.startswith("http://") or text.startswith("https://")):
                update.message.reply_text(
                    "❌ 教程链接必须是有效的URL\n\n"
                    "请发送以 http:// 或 https:// 开头的链接\n\n"
                    "示例: <code>https://example.com/tutorial</code>",
                    parse_mode="HTML"
                )
                return
        elif flow["state"] == "awaiting_notify_input":
            # Validate numeric ID or @username
            if not (text.startswith("@") or text.lstrip("-").isdigit()):
                update.message.reply_text(
                    "❌ 通知ID格式错误\n\n"
                    "请发送有效的频道/群组ID或用户名\n\n"
                    "示例: <code>-100123456789</code> 或 <code>@yourchannel</code>",
                    parse_mode="HTML"
                )
                return
        else:
            # General validation - allow @username or URLs
            if not (text.startswith("@") or text.startswith("http://") or text.startswith("https://")):
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
            {"agent_id": agent_id},
            {
                "$set": {
                    f"settings.{field}": text,
                    "updated_at": datetime.now()
                }
            }
        )
        
        context.user_data.pop("admin_setting_flow", None)
        update.message.reply_text(
            f"✅ {field_name}设置成功！\n\n"
            f"<b>代理ID:</b> <code>{agent_id}</code>\n"
            f"<b>新设置:</b> {text}\n\n"
            f"此设置将立即在代理机器人中生效（只读显示）。",
            parse_mode="HTML"
        )
        
        logging.info(f"Admin set {field} for agent {agent_id}: {text}")
        
    except Exception as e:
        logging.error(f"Error in admin_setting_text_input: {e}")
        update.message.reply_text(f"❌ 设置失败: {e}")
        context.user_data.pop("admin_setting_flow", None)

