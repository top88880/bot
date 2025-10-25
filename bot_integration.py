"""Integration module for multi-tenant agent architecture.

This module provides initialization and integration points for the agent
system. Import and call these functions from bot.py to enable agent features.
"""

import os
import json
import logging
import threading
import time
from datetime import datetime
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import CallbackQueryHandler
from telegram.error import TelegramError, RetryAfter

# Import database
from mongo import agents, user


# Storage for running agent updaters
RUNNING_AGENTS = {}  # {agent_id: updater_instance}
AGENTS_FILE = os.path.join(os.path.dirname(__file__), 'agents.json')


def load_agents_from_file():
    """Load agents from JSON file as fallback."""
    try:
        if os.path.exists(AGENTS_FILE):
            with open(AGENTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Error loading agents from file: {e}")
    return []


def save_agents_to_file(agents_list):
    """Save agents to JSON file as fallback."""
    try:
        with open(AGENTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(agents_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Error saving agents to file: {e}")


def get_all_agents():
    """Get all agents from MongoDB or JSON fallback."""
    try:
        # Try MongoDB first
        agents_list = list(agents.find({}))
        if agents_list:
            return agents_list
    except Exception as e:
        logging.warning(f"MongoDB agents query failed: {e}, using JSON fallback")
    
    # Fallback to JSON file
    return load_agents_from_file()


def normalize_chat_id(chat_id_str):
    """Normalize chat_id to integer format.
    
    Args:
        chat_id_str: Chat ID as string (may be @username, -100..., or numeric)
    
    Returns:
        int or str: Normalized chat_id (int if numeric, str if @username)
    """
    if not chat_id_str:
        return None
    
    chat_id_str = str(chat_id_str).strip()
    
    # If it starts with @, return as is (username)
    if chat_id_str.startswith('@'):
        return chat_id_str
    
    # Try to convert to int
    try:
        return int(chat_id_str)
    except ValueError:
        logging.warning(f"Invalid chat_id format: {chat_id_str}")
        return None


def broadcast_restock_to_agents(text, parse_mode=None):
    """Broadcast restock notification to all agent notify channels.
    
    Iterates through all agents and sends the restock notification to each
    agent's configured notify_channel_id using their bot token.
    
    Args:
        text: Message text to broadcast
        parse_mode: Optional parse mode (e.g., 'HTML', 'Markdown')
    
    Returns:
        dict: Summary with keys:
            - total: Total agents processed
            - success: Number of successful sends
            - skipped: Number of agents without notify_channel_id
            - failed: Number of failed sends
            - results: List of per-agent results
    """
    logging.info(f"Starting restock broadcast to agents: {text[:50]}...")
    
    agents_list = get_all_agents()
    
    summary = {
        'total': len(agents_list),
        'success': 0,
        'skipped': 0,
        'failed': 0,
        'results': []
    }
    
    if not agents_list:
        logging.info("No agents found, skipping broadcast")
        return summary
    
    for agent in agents_list:
        agent_id = agent.get('agent_id', 'unknown')
        agent_name = agent.get('name', 'Unnamed')
        token = agent.get('token')
        settings = agent.get('settings', {})
        notify_channel_id = settings.get('notify_channel_id')
        
        result = {
            'agent_id': agent_id,
            'agent_name': agent_name,
            'status': 'unknown'
        }
        
        # Skip if no notify_channel_id configured
        if not notify_channel_id:
            result['status'] = 'skipped'
            result['reason'] = 'No notify_channel_id configured'
            summary['skipped'] += 1
            summary['results'].append(result)
            logging.debug(f"Skipping agent {agent_id} ({agent_name}): no notify_channel_id")
            continue
        
        # Skip if no token
        if not token:
            result['status'] = 'skipped'
            result['reason'] = 'No token available'
            summary['skipped'] += 1
            summary['results'].append(result)
            logging.warning(f"Skipping agent {agent_id} ({agent_name}): no token")
            continue
        
        # Normalize chat_id
        chat_id = normalize_chat_id(notify_channel_id)
        if chat_id is None:
            result['status'] = 'failed'
            result['reason'] = f'Invalid chat_id format: {notify_channel_id}'
            summary['failed'] += 1
            summary['results'].append(result)
            logging.error(f"Agent {agent_id} ({agent_name}): invalid chat_id {notify_channel_id}")
            continue
        
        try:
            # Try to use running agent's bot if available
            if agent_id in RUNNING_AGENTS:
                bot = RUNNING_AGENTS[agent_id].bot
                logging.debug(f"Using running agent bot for {agent_id}")
            else:
                # Create temporary bot instance
                bot = Bot(token=token)
                logging.debug(f"Created temporary bot for {agent_id}")
            
            # Send the message
            bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode
            )
            
            result['status'] = 'success'
            result['chat_id'] = chat_id
            summary['success'] += 1
            logging.info(f"✅ Sent restock notification to agent {agent_id} ({agent_name}) channel {chat_id}")
            
        except RetryAfter as e:
            # Rate limit hit
            result['status'] = 'failed'
            result['reason'] = f'Rate limited: retry after {e.retry_after}s'
            summary['failed'] += 1
            logging.warning(f"⚠️ Rate limit for agent {agent_id} ({agent_name}): retry after {e.retry_after}s")
            
        except TelegramError as e:
            result['status'] = 'failed'
            result['reason'] = f'Telegram error: {str(e)}'
            summary['failed'] += 1
            logging.error(f"❌ Failed to send to agent {agent_id} ({agent_name}): {e}")
            
        except Exception as e:
            result['status'] = 'failed'
            result['reason'] = f'Unexpected error: {str(e)}'
            summary['failed'] += 1
            logging.error(f"❌ Unexpected error for agent {agent_id} ({agent_name}): {e}")
        
        summary['results'].append(result)
        
        # Throttle between sends to avoid hitting rate limits
        time.sleep(0.5)
    
    logging.info(
        f"Restock broadcast complete: {summary['success']} success, "
        f"{summary['skipped']} skipped, {summary['failed']} failed"
    )
    
    return summary


def save_agent(token, name, owner_user_id=None):
    """
    Save a new agent to storage.
    
    Args:
        token: Bot token
        name: Agent display name
        owner_user_id: Telegram user ID of the agent owner (optional, for backwards compatibility)
    
    Returns:
        agent_id: Unique identifier for the agent
    """
    agent_id = f"agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Use owners array instead of single owner_user_id
    owners = [owner_user_id] if owner_user_id else []
    
    agent_data = {
        'agent_id': agent_id,
        'token': token,
        'name': name,
        'status': 'stopped',
        'owners': owners,  # New field: array of owner user IDs
        'markup_usdt': '0.00000000',  # 8 decimal precision
        'profit_available_usdt': '0.00000000',  # 8 decimal precision
        'profit_frozen_usdt': '0.00000000',  # 8 decimal precision
        'total_paid_usdt': '0.00000000',  # 8 decimal precision
        'settings': {
            'customer_service': None,
            'official_channel': None,
            'restock_group': None,
            'tutorial_link': None,
            'notify_channel_id': None,
            'extra_links': []
        },
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    }
    
    try:
        # Try MongoDB first
        agents.insert_one(agent_data)
        logging.info(f"Agent {agent_id} saved to MongoDB with owners={owners}")
    except Exception as e:
        logging.warning(f"MongoDB save failed: {e}, using JSON fallback")
        # Fallback to JSON
        agents_list = load_agents_from_file()
        # Convert datetime to string for JSON
        agent_data['created_at'] = agent_data['created_at'].isoformat()
        agent_data['updated_at'] = agent_data['updated_at'].isoformat()
        agents_list.append(agent_data)
        save_agents_to_file(agents_list)
    
    return agent_id


def update_agent_status(agent_id, status):
    """Update agent status in storage."""
    try:
        # Try MongoDB first
        agents.update_one(
            {'agent_id': agent_id},
            {'$set': {'status': status, 'updated_at': datetime.now()}}
        )
    except Exception as e:
        logging.warning(f"MongoDB update failed: {e}, using JSON fallback")
        # Fallback to JSON
        agents_list = load_agents_from_file()
        for agent in agents_list:
            if agent.get('agent_id') == agent_id:
                agent['status'] = status
                agent['updated_at'] = datetime.now().isoformat()
                break
        save_agents_to_file(agents_list)


def delete_agent(agent_id):
    """Delete an agent from storage."""
    try:
        # Try MongoDB first
        agents.delete_one({'agent_id': agent_id})
    except Exception as e:
        logging.warning(f"MongoDB delete failed: {e}, using JSON fallback")
        # Fallback to JSON
        agents_list = load_agents_from_file()
        agents_list = [a for a in agents_list if a.get('agent_id') != agent_id]
        save_agents_to_file(agents_list)


def start_agent_bot(agent_id, token):
    """
    Start an agent bot instance.
    
    Args:
        agent_id: Unique agent identifier
        token: Bot token
    
    Returns:
        bool: True if started successfully
    """
    try:
        if agent_id in RUNNING_AGENTS:
            logging.warning(f"Agent {agent_id} is already running")
            return True
        
        logging.info(f"Starting agent bot {agent_id}...")
        
        # Import here to avoid circular dependency
        from bot import start_bot_with_token
        
        # Start bot in a separate thread
        def run_agent():
            try:
                # Pass agent_context with just agent_id
                agent_context = {
                    'agent_id': agent_id
                }
                updater = start_bot_with_token(
                    token, 
                    enable_agent_system=False,
                    agent_context=agent_context
                )
                RUNNING_AGENTS[agent_id] = updater
                update_agent_status(agent_id, 'running')
                logging.info(f"Agent {agent_id} started successfully")
            except Exception as e:
                logging.error(f"Error running agent {agent_id}: {e}")
                update_agent_status(agent_id, 'error')
                RUNNING_AGENTS.pop(agent_id, None)
        
        thread = threading.Thread(target=run_agent, daemon=True, name=f"Agent-{agent_id}")
        thread.start()
        
        return True
    except Exception as e:
        logging.error(f"Failed to start agent {agent_id}: {e}")
        return False


def stop_agent_bot(agent_id):
    """Stop a running agent bot."""
    try:
        if agent_id in RUNNING_AGENTS:
            updater = RUNNING_AGENTS[agent_id]
            updater.stop()
            RUNNING_AGENTS.pop(agent_id)
            update_agent_status(agent_id, 'stopped')
            logging.info(f"Agent {agent_id} stopped")
            return True
        else:
            logging.warning(f"Agent {agent_id} is not running")
            return False
    except Exception as e:
        logging.error(f"Error stopping agent {agent_id}: {e}")
        return False


def agent_manage(update, context):
    """Show agent management panel with full button support."""
    query = update.callback_query
    query.answer()
    
    # Debug logging
    logging.info(f"[Agent] agent_manage clicked by user {query.from_user.id}")
    
    # Check admin permission
    from bot import get_admin_ids
    if query.from_user.id not in get_admin_ids():
        query.edit_message_text("❌ 权限不足，仅管理员可用")
        return
    
    try:
        agents_list = get_all_agents()
        running_count = len([a for a in agents_list if a.get('agent_id') in RUNNING_AGENTS])
        
        text = "🤖 <b>代理管理</b>\n\n"
        
        if not agents_list:
            text += "📭 暂无代理\n\n"
            text += "点击下方 <b>新增代理</b> 按钮开始创建第一个代理Bot。\n\n"
            text += "<i>代理Bot可以分享你的商品库存并自动处理订单。</i>"
        else:
            text += f"📊 代理总数: <b>{len(agents_list)}</b>\n"
            text += f"🟢 运行中: <b>{running_count}</b>\n"
            text += f"🔴 已停止: <b>{len(agents_list) - running_count}</b>\n\n"
            
            text += "━━━━━━━━━━━━━━━\n\n"
            
            for idx, agent in enumerate(agents_list, 1):
                agent_id = agent.get('agent_id', 'unknown')
                name = agent.get('name', 'Unnamed')
                status = agent.get('status', 'unknown')
                
                # Check if actually running
                if agent_id in RUNNING_AGENTS:
                    status_emoji = "🟢"
                    status_text = "运行中"
                elif status == 'running':
                    status_emoji = "🟡"
                    status_text = "启动中"
                else:
                    status_emoji = "🔴"
                    status_text = "已停止"
                
                text += f"{idx}. {status_emoji} <b>{name}</b>\n"
                text += f"   📋 ID: <code>{agent_id}</code>\n"
                text += f"   📍 状态: {status_text}\n\n"
        
        buttons = [
            [
                InlineKeyboardButton("➕ 新增代理", callback_data="agent_new"),
                InlineKeyboardButton("🔄 刷新列表", callback_data="agent_refresh")
            ]
        ]
        
        # Add manage/toggle/delete/owners buttons for each agent (using short callback_data)
        for agent in agents_list:
            agent_id = agent.get('agent_id')
            name = agent.get('name', 'Unnamed')
            
            # Truncate name if too long to keep callback_data under 64 bytes
            display_name = name[:8] + "..." if len(name) > 8 else name
            
            row = []
            # Add settings button
            row.append(InlineKeyboardButton(
                f"⚙️ {display_name}", 
                callback_data=f"agent_detail {agent_id}"
            ))
            
            # Add toggle button
            if agent_id in RUNNING_AGENTS:
                row.append(InlineKeyboardButton(
                    "⏸", 
                    callback_data=f"agent_tgl {agent_id}"
                ))
            else:
                row.append(InlineKeyboardButton(
                    "▶️", 
                    callback_data=f"agent_tgl {agent_id}"
                ))
            
            # Add owners button
            row.append(InlineKeyboardButton(
                "👑",
                callback_data=f"agent_own {agent_id}"
            ))
            
            # Add delete button
            row.append(InlineKeyboardButton(
                "🗑", 
                callback_data=f"agent_del {agent_id}"
            ))
            buttons.append(row)
        
        # Add withdrawal review button
        pending_count = 0
        try:
            from mongo import agent_withdrawals
            pending_count = agent_withdrawals.count_documents({'status': 'pending'})
        except:
            pass
        
        if pending_count > 0:
            buttons.append([
                InlineKeyboardButton(
                    f"💰 审核提现 ({pending_count})", 
                    callback_data="agent_wd_list"
                )
            ])
        
        buttons.append([InlineKeyboardButton("🔙 返回控制台", callback_data="backstart")])
        
        query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logging.error(f"Error in agent_manage: {e}")
        query.edit_message_text(
            f"❌ 加载代理管理面板时出错\n\n错误信息: {str(e)}\n\n"
            f"请联系管理员检查日志。"
        )


def agent_refresh(update, context):
    """Refresh the agent management panel (same as agent_manage)."""
    # Simply call agent_manage to refresh
    agent_manage(update, context)


def agent_new(update, context):
    """Start the process of adding a new agent."""
    query = update.callback_query
    query.answer()
    
    # Check admin permission
    from bot import get_admin_ids
    if query.from_user.id not in get_admin_ids():
        query.edit_message_text("❌ 权限不足，仅管理员可用")
        return
    
    user_id = query.from_user.id
    
    # Set sign to trigger token input
    user.update_one({'user_id': user_id}, {"$set": {'sign': 'agent_add_token'}})
    
    text = (
        "🤖 <b>创建新代理 - 步骤 1/2</b>\n\n"
        "📝 请发送代理Bot的Token\n\n"
        "<b>如何获取Token：</b>\n"
        "1. 打开 @BotFather\n"
        "2. 发送 /newbot 创建新Bot\n"
        "3. 按提示设置Bot名称和用户名\n"
        "4. 复制收到的Token并发送到这里\n\n"
        "<i>Token格式示例：1234567890:ABCdefGHIjklMNOpqrsTUVwxyz</i>"
    )
    
    keyboard = [[InlineKeyboardButton("🚫 取消", callback_data="agent_manage")]]
    
    query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# Keep agent_add as an alias for backward compatibility
def agent_add(update, context):
    """Alias for agent_new for backward compatibility."""
    agent_new(update, context)


def agent_tgl(update, context):
    """Toggle agent on/off (short callback version)."""
    query = update.callback_query
    agent_id = query.data.replace('agent_tgl ', '')
    
    # Check admin permission
    from bot import get_admin_ids
    if query.from_user.id not in get_admin_ids():
        query.answer("❌ 权限不足", show_alert=True)
        return
    
    try:
        # Find agent
        agents_list = get_all_agents()
        agent = next((a for a in agents_list if a.get('agent_id') == agent_id), None)
        
        if not agent:
            query.answer("❌ 代理不存在", show_alert=True)
            return
        
        if agent_id in RUNNING_AGENTS:
            # Stop the agent
            success = stop_agent_bot(agent_id)
            if success:
                query.answer("✅ 代理已停止", show_alert=True)
            else:
                query.answer("⚠️ 停止失败", show_alert=True)
        else:
            # Start the agent
            token = agent.get('token')
            if not token:
                query.answer("❌ 代理Token缺失", show_alert=True)
                return
            
            success = start_agent_bot(agent_id, token)
            if success:
                query.answer("✅ 代理启动中...", show_alert=True)
            else:
                query.answer("❌ 启动失败，请检查Token", show_alert=True)
        
        # Refresh the panel
        agent_manage(update, context)
        
    except Exception as e:
        logging.error(f"Error in agent_tgl: {e}")
        query.answer(f"❌ 操作失败: {str(e)}", show_alert=True)


def agent_toggle(update, context):
    """Toggle agent on/off (legacy long callback version)."""
    query = update.callback_query
    agent_id = query.data.replace('agent_toggle ', '')
    
    # Check admin permission
    from bot import get_admin_ids
    if query.from_user.id not in get_admin_ids():
        query.answer("❌ 权限不足", show_alert=True)
        return
    
    # Find agent
    agents_list = get_all_agents()
    agent = next((a for a in agents_list if a.get('agent_id') == agent_id), None)
    
    if not agent:
        query.answer("❌ 代理不存在", show_alert=True)
        return
    
    if agent_id in RUNNING_AGENTS:
        # Stop the agent
        success = stop_agent_bot(agent_id)
        if success:
            query.answer("✅ 代理已停止", show_alert=True)
        else:
            query.answer("⚠️ 停止失败", show_alert=True)
    else:
        # Start the agent
        token = agent.get('token')
        success = start_agent_bot(agent_id, token)
        if success:
            query.answer("✅ 代理启动中...", show_alert=True)
        else:
            query.answer("❌ 启动失败，请检查Token", show_alert=True)
    
    # Refresh the panel
    agent_manage(update, context)


def agent_del(update, context):
    """Delete an agent (short callback version)."""
    query = update.callback_query
    agent_id = query.data.replace('agent_del ', '')
    
    # Check admin permission
    from bot import get_admin_ids
    if query.from_user.id not in get_admin_ids():
        query.answer("❌ 权限不足", show_alert=True)
        return
    
    try:
        # Find agent for confirmation message
        agents_list = get_all_agents()
        agent = next((a for a in agents_list if a.get('agent_id') == agent_id), None)
        
        if not agent:
            query.answer("❌ 代理不存在", show_alert=True)
            return
        
        agent_name = agent.get('name', 'Unnamed')
        
        # Stop if running
        if agent_id in RUNNING_AGENTS:
            stop_agent_bot(agent_id)
        
        # Delete from storage
        delete_agent(agent_id)
        
        query.answer(f"✅ 代理 '{agent_name}' 已删除", show_alert=True)
        
        # Refresh the panel
        agent_manage(update, context)
        
    except Exception as e:
        logging.error(f"Error in agent_del: {e}")
        query.answer(f"❌ 删除失败: {str(e)}", show_alert=True)


def agent_delete(update, context):
    """Delete an agent (legacy long callback version)."""
    query = update.callback_query
    agent_id = query.data.replace('agent_delete ', '')
    
    # Check admin permission
    from bot import get_admin_ids
    if query.from_user.id not in get_admin_ids():
        query.answer("❌ 权限不足", show_alert=True)
        return
    
    # Stop if running
    if agent_id in RUNNING_AGENTS:
        stop_agent_bot(agent_id)
    
    # Delete from storage
    delete_agent(agent_id)
    
    query.answer("✅ 代理已删除", show_alert=True)
    
    # Refresh the panel
    agent_manage(update, context)


def discover_and_start_agents():
    """Discover agents from storage and start them."""
    try:
        agents_list = get_all_agents()
        logging.info(f"Found {len(agents_list)} agents in storage")
        
        for agent in agents_list:
            agent_id = agent.get('agent_id')
            token = agent.get('token')
            status = agent.get('status')
            
            # Only auto-start agents that were running before
            if status == 'running' and agent_id not in RUNNING_AGENTS:
                logging.info(f"Auto-starting agent {agent_id}")
                start_agent_bot(agent_id, token)
    except Exception as e:
        logging.error(f"Error discovering agents: {e}")


def agent_own(update, context):
    """Show owner management panel for an agent."""
    query = update.callback_query
    query.answer()
    agent_id = query.data.replace('agent_own ', '')
    
    # Check admin permission
    from bot import get_admin_ids
    if query.from_user.id not in get_admin_ids():
        query.answer("❌ 权限不足", show_alert=True)
        return
    
    try:
        agent = agents.find_one({'agent_id': agent_id})
        if not agent:
            query.answer("❌ 代理不存在", show_alert=True)
            return
        
        name = agent.get('name', 'Unnamed')
        
        # Get owners with migration
        owners = agent.get('owners')
        if owners is None:
            # Check for legacy owner_user_id
            owner_user_id = agent.get('owner_user_id')
            if owner_user_id is not None:
                owners = [owner_user_id]
                # Migrate to owners array
                agents.update_one(
                    {'agent_id': agent_id},
                    {'$set': {'owners': owners}, '$unset': {'owner_user_id': ''}}
                )
            else:
                owners = []
        
        text = f"<b>👑 拥有者管理 - {name}</b>\n\n"
        
        if not owners:
            text += "📭 当前没有拥有者\n\n"
        else:
            text += "<b>当前拥有者:</b>\n"
            for owner_id in owners:
                text += f"• <code>{owner_id}</code>\n"
            text += "\n"
        
        text += "<i>拥有者可以在代理机器人中使用 /agent 命令管理代理设置。</i>"
        
        keyboard = [
            [
                InlineKeyboardButton("➕ 添加拥有者", callback_data=f"agent_own_add {agent_id}"),
            ]
        ]
        
        # Add remove button for each owner
        for owner_id in owners:
            keyboard.append([
                InlineKeyboardButton(
                    f"➖ 移除 {owner_id}", 
                    callback_data=f"agent_own_rm {agent_id} {owner_id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 返回", callback_data="agent_manage")])
        
        query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in agent_own: {e}")
        query.answer(f"❌ 错误: {str(e)}", show_alert=True)


def agent_own_add(update, context):
    """Initiate adding owner(s) to an agent."""
    query = update.callback_query
    query.answer()
    agent_id = query.data.replace('agent_own_add ', '')
    
    # Check admin permission
    from bot import get_admin_ids
    if query.from_user.id not in get_admin_ids():
        query.answer("❌ 权限不足", show_alert=True)
        return
    
    user_id = query.from_user.id
    
    # Set sign to trigger owner input
    user.update_one({'user_id': user_id}, {"$set": {'sign': f'agent_add_owner:{agent_id}'}})
    
    text = (
        "<b>➕ 添加拥有者</b>\n\n"
        "请发送要添加为拥有者的用户ID或@用户名。\n\n"
        "<b>格式:</b>\n"
        "• 单个: <code>123456789</code> 或 <code>@username</code>\n"
        "• 多个: <code>123456789 @username 987654321</code> (空格分隔)\n\n"
        "<i>用户ID可以通过让用户发送消息给机器人后在日志中查看。</i>"
    )
    
    keyboard = [[InlineKeyboardButton("🚫 取消", callback_data=f"agent_own {agent_id}")]]
    
    query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def agent_own_rm(update, context):
    """Remove an owner from an agent."""
    query = update.callback_query
    query.answer()
    
    # Parse: "agent_own_rm {agent_id} {owner_id}"
    parts = query.data.split(' ')
    if len(parts) < 3:
        query.answer("❌ 格式错误", show_alert=True)
        return
    
    agent_id = parts[1]
    owner_id = int(parts[2])
    
    # Check admin permission
    from bot import get_admin_ids
    if query.from_user.id not in get_admin_ids():
        query.answer("❌ 权限不足", show_alert=True)
        return
    
    try:
        agent = agents.find_one({'agent_id': agent_id})
        if not agent:
            query.answer("❌ 代理不存在", show_alert=True)
            return
        
        owners = agent.get('owners', [])
        if owner_id not in owners:
            query.answer("❌ 该用户不是拥有者", show_alert=True)
            return
        
        # Remove owner
        owners.remove(owner_id)
        agents.update_one(
            {'agent_id': agent_id},
            {'$set': {'owners': owners, 'updated_at': datetime.now()}}
        )
        
        logging.info(f"Removed owner {owner_id} from agent {agent_id}")
        query.answer("✅ 拥有者已移除", show_alert=True)
        
        # Refresh owner panel
        context.match = type('obj', (object,), {'data': f"agent_own {agent_id}"})()
        update.callback_query.data = f"agent_own {agent_id}"
        agent_own(update, context)
        
    except Exception as e:
        logging.error(f"Error in agent_own_rm: {e}")
        query.answer(f"❌ 错误: {str(e)}", show_alert=True)


def integrate_agent_system(dispatcher, job_queue):
    """
    Integrate agent management system into the bot.
    
    Args:
        dispatcher: PTB dispatcher
        job_queue: PTB job queue
    """
    try:
        logging.info("="*60)
        logging.info("Initializing Button-Based Agent Management System")
        logging.info("="*60)
        
        # Register agent management callbacks (short versions for button flow)
        dispatcher.add_handler(CallbackQueryHandler(agent_manage, pattern='^agent_manage$'), group=-1)
        dispatcher.add_handler(CallbackQueryHandler(agent_refresh, pattern='^agent_refresh$'), group=-1)
        dispatcher.add_handler(CallbackQueryHandler(agent_new, pattern='^agent_new$'), group=-1)
        dispatcher.add_handler(CallbackQueryHandler(agent_tgl, pattern='^agent_tgl '), group=-1)
        dispatcher.add_handler(CallbackQueryHandler(agent_del, pattern='^agent_del '), group=-1)
        dispatcher.add_handler(CallbackQueryHandler(agent_own, pattern='^agent_own '), group=-1)
        dispatcher.add_handler(CallbackQueryHandler(agent_own_add, pattern='^agent_own_add '), group=-1)
        dispatcher.add_handler(CallbackQueryHandler(agent_own_rm, pattern='^agent_own_rm '), group=-1)
        
        # Register legacy long callback versions for backward compatibility
        dispatcher.add_handler(CallbackQueryHandler(agent_add, pattern='^agent_add$'), group=-1)
        dispatcher.add_handler(CallbackQueryHandler(agent_toggle, pattern='^agent_toggle '), group=-1)
        dispatcher.add_handler(CallbackQueryHandler(agent_delete, pattern='^agent_delete '), group=-1)
        
        logging.info("✅ Agent management callbacks registered:")
        logging.info("   - agent_manage (main panel)")
        logging.info("   - agent_refresh (refresh list)")
        logging.info("   - agent_new (add new agent)")
        logging.info("   - agent_tgl (toggle agent)")
        logging.info("   - agent_del (delete agent)")
        logging.info("   - agent_own (owner management)")
        logging.info("   - agent_own_add (add owner)")
        logging.info("   - agent_own_rm (remove owner)")
        logging.info("   - Legacy handlers (agent_add, agent_toggle, agent_delete)")
        
        # Discover and start existing agents
        discover_and_start_agents()
        
        logging.info("="*60)
        logging.info("✅ Agent Management System Initialized")
        logging.info("="*60)
        
    except Exception as e:
        logging.error(f"❌ Failed to initialize agent system: {e}")
        import traceback
        logging.error(traceback.format_exc())

