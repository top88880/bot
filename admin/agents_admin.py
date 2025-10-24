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
        
        query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in agent_panel_callback: {e}")
        query.edit_message_text(f"❌ Error loading agent panel: {e}")


def agent_list_view_callback(update: Update, context: CallbackContext):
    """Show detailed agent list with action buttons."""
    query = update.callback_query
    query.answer()
    
    try:
        agents_collection = bot_db['agents']
        agents = list_agents(agents_collection)
        running_agent_ids = set(get_running_agents())
        
        if not agents:
            query.edit_message_text(
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
        
        query.edit_message_text(
            text=text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
    except Exception as e:
        logging.error(f"Error in agent_list_view_callback: {e}")
        query.edit_message_text(f"❌ Error loading agent list: {e}")
