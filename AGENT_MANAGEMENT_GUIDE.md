# Agent Management Implementation Guide

## Overview
This implementation adds button-based agent management to the Telegram bot, allowing admins to create, manage, and monitor multiple agent bots from the main bot's admin panel.

## Key Changes

### 1. Handler Refactoring (bot.py)

#### `register_common_handlers(dispatcher, job_queue)`
- **Location**: Line 10331
- **Purpose**: Extracts all handler registrations into a reusable function
- **Benefits**: Allows both master and agent bots to share the same handlers
- **Includes**: All CommandHandlers, CallbackQueryHandlers, MessageHandlers, InlineQueryHandlers, and job queue tasks

#### `start_bot_with_token(token, enable_agent_system=False)`
- **Location**: Line 10496
- **Purpose**: Creates a bot instance with the given token
- **Parameters**:
  - `token`: Bot token string from @BotFather
  - `enable_agent_system`: Boolean flag (True only for master bot)
- **Returns**: Updater instance
- **Use Case**: Spawning agent bots with identical functionality

### 2. Main Function Improvements (bot.py)

#### Fixed Duplicate Flask Server
- **Before**: Flask server was started twice (lines 10251 and 10254)
- **After**: Server starts only once with daemon thread (line 10540)
- **Impact**: Prevents port binding conflicts

#### Simplified Main Flow
- **Location**: Line 10536
- **New Structure**:
  ```python
  def main():
      # Start Flask server once
      flask_thread = threading.Thread(target=start_flask_server, daemon=True)
      flask_thread.start()
      
      # Start master bot with agent system
      updater = start_bot_with_token(BOT_TOKEN, enable_agent_system=True)
      updater.idle()
  ```

### 3. Admin Panel Updates (bot.py)

#### "代理管理" Button
- **Added to**: 
  - `show_admin_panel()` function (line 1271)
  - `backstart()` function (line 4580)
- **Callback**: `agent_manage`
- **Access**: Admin-only (checked in callback)

### 4. Agent Sign Flows (bot.py)

#### Token Input Flow
- **Sign**: `agent_add_token`
- **Location**: Line 7298
- **Flow**:
  1. User clicks "新增代理" button
  2. Bot sets sign to `agent_add_token`
  3. User sends bot token
  4. Bot validates and stores token in `context.user_data`
  5. Sign changes to `agent_add_name`

#### Name Input Flow
- **Sign**: `agent_add_name`
- **Location**: Line 7318
- **Flow**:
  1. User sends agent name/nickname
  2. Bot validates name length (1-50 chars)
  3. Bot calls `save_agent()` and `start_agent_bot()`
  4. Agent is persisted and launched
  5. Sign resets to 0

### 5. Agent Management System (bot_integration.py)

#### Storage Architecture
- **Primary**: MongoDB `agents` collection
- **Fallback**: `agents.json` file
- **Runtime**: `RUNNING_AGENTS` dictionary (agent_id → updater)

#### Core Functions

##### `save_agent(token, name)`
- Generates unique agent_id with timestamp
- Stores in MongoDB with fallback to JSON
- Returns agent_id for tracking

##### `start_agent_bot(agent_id, token)`
- Spawns agent in separate daemon thread
- Calls `start_bot_with_token(token, enable_agent_system=False)`
- Updates status to 'running'
- Handles errors gracefully

##### `stop_agent_bot(agent_id)`
- Stops the updater instance
- Removes from RUNNING_AGENTS
- Updates status to 'stopped'

##### `delete_agent(agent_id)`
- Stops agent if running
- Removes from MongoDB/JSON storage

#### UI Callbacks

##### `agent_manage(update, context)`
- Displays agent list with status indicators
- Shows buttons: 新增代理, 刷新列表
- Lists each agent with 启动/停止 and 删除 buttons
- Admin permission check

##### `agent_add(update, context)`
- Sets user sign to `agent_add_token`
- Prompts for token input
- Admin permission check

##### `agent_toggle(update, context)`
- Toggles agent on/off
- Refreshes panel after action
- Admin permission check

##### `agent_delete(update, context)`
- Confirms and deletes agent
- Stops if running
- Refreshes panel
- Admin permission check

#### `integrate_agent_system(dispatcher, job_queue)`
- Registers all agent management callbacks
- Discovers and auto-starts agents marked as 'running'
- Called only by master bot in main()

## Agent Data Schema

```python
{
    'agent_id': 'agent_20250124_121345',  # Unique ID with timestamp
    'token': '1234567890:ABCdefGHIjklMNOpqrsTUVwxyz',  # Bot token
    'name': 'Sales Bot',  # Display name
    'status': 'running',  # 'running', 'stopped', or 'error'
    'created_at': datetime(2025, 1, 24, 12, 13, 45),
    'updated_at': datetime(2025, 1, 24, 12, 13, 45)
}
```

## Usage Flow

### Adding a New Agent
1. Admin opens admin panel (`/admin`)
2. Clicks "代理管理" button
3. Clicks "➕ 新增代理" button
4. Sends bot token from @BotFather
5. Sends agent name/nickname
6. Bot validates, saves, and starts agent
7. Success message displayed

### Managing Agents
- **View Status**: Click "代理管理" → see all agents with status
- **Refresh List**: Click "🔄 刷新列表"
- **Start Agent**: Click "▶️ 启动 [Name]"
- **Stop Agent**: Click "⏸ 停止 [Name]"
- **Delete Agent**: Click "🗑 删除" (stops if running)

## Status Indicators
- 🟢 **Running**: Agent is active and polling
- 🟡 **Starting**: Agent is initializing
- 🔴 **Stopped**: Agent is not running

## Security Features
1. **Admin-Only Access**: All agent management requires admin privileges
2. **Token Validation**: Basic validation before accepting tokens
3. **Isolated Agents**: Each agent runs in separate thread with own updater
4. **No Pay Server**: Agent bots don't start the Flask payment server
5. **No Agent System**: Agent bots can't manage other agents

## Benefits

### For Admins
- Manage multiple bots from one interface
- No command-line access needed
- Visual status monitoring
- Easy start/stop/delete operations

### For Users
- All agents have identical UI/menus
- Consistent user experience
- Same payment flows and business logic
- Shared database for unified data

### Technical
- Clean separation of concerns
- Reusable handler registration
- MongoDB with JSON fallback
- Thread-safe agent management
- Automatic agent discovery on restart

## Files Modified
1. **bot.py**: Handler extraction, agent flows, admin panel updates, main() fix
2. **bot_integration.py**: Complete rewrite for button-based management
3. **.gitignore**: Added to exclude runtime files

## Dependencies
- python-telegram-bot==13.15 (v13 API - Updater/Dispatcher)
- pymongo==4.13.0 (MongoDB storage)
- python-dotenv==1.1.0 (Environment config)

## Compatibility
- ✅ Python 3.8+
- ✅ python-telegram-bot v13
- ✅ MongoDB (optional, JSON fallback)
- ✅ Existing bot features preserved
- ✅ No breaking changes to public API

## Testing Checklist
- [ ] Bot starts without errors
- [ ] Admin panel shows "代理管理" button
- [ ] Can add new agent (token + name flow)
- [ ] Agent appears in list with correct status
- [ ] Can start/stop agent
- [ ] Can delete agent
- [ ] Agents persist across bot restarts
- [ ] Multiple agents can run simultaneously
- [ ] Agents share same database and UI
- [ ] No duplicate Flask server errors

## Troubleshooting

### Agent Won't Start
- Verify token is valid
- Check bot has no existing sessions
- Review logs for specific errors
- Ensure token permissions are correct

### Token Not Accepted
- Must be valid bot token format
- Length should be > 20 characters
- Get fresh token from @BotFather

### Status Shows Running but Agent Not Responsive
- Check RUNNING_AGENTS dictionary
- Verify thread is alive
- Review agent logs
- Try stop/start cycle

## Future Enhancements
- Agent performance metrics
- Automatic restart on failure
- Agent-specific configuration
- Bulk agent operations
- Agent activity logs
- Token encryption at rest
