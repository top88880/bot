# Agent Management Implementation - Quick Reference

## Key Functions

### bot.py
```python
# Line 10331
register_common_handlers(dispatcher, job_queue)
# Registers all handlers (commands, callbacks, messages, jobs)

# Line 10496
start_bot_with_token(token, enable_agent_system=False)
# Spawns bot with given token, optionally enables agent system

# Line 10536
main()
# Master bot entry point - starts Flask once, enables agent system
```

### bot_integration.py
```python
# Agent Storage
save_agent(token, name) → agent_id
get_all_agents() → list[dict]
update_agent_status(agent_id, status)
delete_agent(agent_id)

# Agent Control
start_agent_bot(agent_id, token) → bool
stop_agent_bot(agent_id) → bool

# UI Callbacks
agent_manage(update, context)     # Main panel
agent_add(update, context)         # Start add flow
agent_toggle(update, context)      # Start/stop agent
agent_delete(update, context)      # Delete agent

# Integration
integrate_agent_system(dispatcher, job_queue)
# Registers callbacks and auto-starts agents
```

## Admin Panel Flow

```
/admin → 管理员控制台
  └─ 代理管理 → agent_manage
       ├─ ➕ 新增代理 → agent_add
       │    └─ [ForceReply] Token → agent_add_token
       │         └─ [ForceReply] Name → agent_add_name
       │              └─ save_agent() + start_agent_bot()
       ├─ 🔄 刷新列表 → agent_manage (refresh)
       ├─ ▶️ 启动 [Agent] → agent_toggle (start)
       ├─ ⏸ 停止 [Agent] → agent_toggle (stop)
       ├─ 🗑 删除 → agent_delete
       └─ 🔙 返回控制台 → backstart
```

## Sign Flow States

| Sign State | Triggered By | Expects | Next State | Action |
|------------|--------------|---------|------------|--------|
| `agent_add_token` | agent_add callback | Bot token | `agent_add_name` | Store token in context |
| `agent_add_name` | Token received | Agent name | `0` (reset) | save_agent() + start_agent_bot() |

## Callback Patterns

```python
# In register_common_handlers() - integrated by integrate_agent_system()
dispatcher.add_handler(CallbackQueryHandler(agent_manage, pattern='^agent_manage$'))
dispatcher.add_handler(CallbackQueryHandler(agent_add, pattern='^agent_add$'))
dispatcher.add_handler(CallbackQueryHandler(agent_toggle, pattern='^agent_toggle '))
dispatcher.add_handler(CallbackQueryHandler(agent_delete, pattern='^agent_delete '))
```

## Key Changes Summary

| File | Change | Line | Description |
|------|--------|------|-------------|
| bot.py | `register_common_handlers()` | 10331 | Extract all handlers to function |
| bot.py | `start_bot_with_token()` | 10496 | Spawn bot with token |
| bot.py | Fix Flask duplicate | 10540 | Single server start |
| bot.py | Add admin button | 1271, 4580 | "代理管理" in panels |
| bot.py | Agent sign flows | 7298, 7318 | token/name input |
| bot_integration.py | Complete rewrite | All | Button-based management |
| .gitignore | New file | All | Exclude runtime files |

## Testing Commands

```bash
# Syntax check
python3 -m py_compile bot.py
python3 -m py_compile bot_integration.py

# AST validation
python3 -m ast bot.py
python3 -m ast bot_integration.py

# Function verification
grep -n "def register_common_handlers" bot.py
grep -n "def start_bot_with_token" bot.py
grep -n "def agent_manage" bot_integration.py
```

## Deployment Checklist

- [ ] Backup existing bot.py and bot_integration.py
- [ ] Deploy new files
- [ ] Restart bot process
- [ ] Verify admin panel loads
- [ ] Test adding an agent
- [ ] Verify agent appears and starts
- [ ] Test stop/start/delete operations
- [ ] Check logs for errors
