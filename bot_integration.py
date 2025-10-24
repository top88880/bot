"""Integration module for multi-tenant agent architecture.

This module provides initialization and integration points for the agent
system. Import and call these functions from bot.py to enable agent features.
"""

import os
import json
import logging
import threading
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import CallbackQueryHandler

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


def save_agent(token, name):
    """
    Save a new agent to storage.
    
    Args:
        token: Bot token
        name: Agent display name
    
    Returns:
        agent_id: Unique identifier for the agent
    """
    agent_id = f"agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    agent_data = {
        'agent_id': agent_id,
        'token': token,
        'name': name,
        'status': 'stopped',
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    }
    
    try:
        # Try MongoDB first
        agents.insert_one(agent_data)
        logging.info(f"Agent {agent_id} saved to MongoDB")
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
                updater = start_bot_with_token(token, enable_agent_system=False)
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
    """Show agent management panel."""
    query = update.callback_query
    query.answer()
    
    # Check admin permission
    from bot import get_admin_ids
    if query.from_user.id not in get_admin_ids():
        query.edit_message_text("❌ 权限不足，仅管理员可用")
        return
    
    agents_list = get_all_agents()
    
    text = "🤖 <b>代理管理</b>\n\n"
    
    if not agents_list:
        text += "📭 暂无代理\n\n点击下方按钮添加新代理。"
    else:
        text += f"📊 代理总数: {len(agents_list)}\n\n"
        
        for agent in agents_list:
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
            
            text += f"{status_emoji} <b>{name}</b>\n"
            text += f"   ID: <code>{agent_id}</code>\n"
            text += f"   状态: {status_text}\n\n"
    
    buttons = [
        [
            InlineKeyboardButton("➕ 新增代理", callback_data="agent_add"),
            InlineKeyboardButton("🔄 刷新列表", callback_data="agent_manage")
        ]
    ]
    
    # Add toggle/delete buttons for each agent
    for agent in agents_list:
        agent_id = agent.get('agent_id')
        name = agent.get('name', 'Unnamed')
        
        row = []
        if agent_id in RUNNING_AGENTS:
            row.append(InlineKeyboardButton(f"⏸ 停止 {name}", callback_data=f"agent_toggle {agent_id}"))
        else:
            row.append(InlineKeyboardButton(f"▶️ 启动 {name}", callback_data=f"agent_toggle {agent_id}"))
        
        row.append(InlineKeyboardButton(f"🗑 删除", callback_data=f"agent_delete {agent_id}"))
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton("🔙 返回控制台", callback_data="backstart")])
    
    query.edit_message_text(
        text=text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(buttons)
    )


def agent_add(update, context):
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
    
    query.edit_message_text(
        text='🤖 <b>添加新代理</b>\n\n'
             '请发送代理Bot的Token:\n'
             '(从 @BotFather 获取)',
        parse_mode='HTML'
    )


def agent_toggle(update, context):
    """Toggle agent on/off."""
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


def agent_delete(update, context):
    """Delete an agent."""
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
        
        # Register agent management callbacks
        dispatcher.add_handler(CallbackQueryHandler(agent_manage, pattern='^agent_manage$'))
        dispatcher.add_handler(CallbackQueryHandler(agent_add, pattern='^agent_add$'))
        dispatcher.add_handler(CallbackQueryHandler(agent_toggle, pattern='^agent_toggle '))
        dispatcher.add_handler(CallbackQueryHandler(agent_delete, pattern='^agent_delete '))
        
        logging.info("✅ Agent management callbacks registered")
        
        # Discover and start existing agents
        discover_and_start_agents()
        
        logging.info("="*60)
        logging.info("✅ Agent Management System Initialized")
        logging.info("="*60)
        
    except Exception as e:
        logging.error(f"❌ Failed to initialize agent system: {e}")

