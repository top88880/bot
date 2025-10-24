# Agent Management System - Quick Start Guide

## 🎯 Overview
The Agent Management system allows admins to create and manage agent bots that share the main bot's inventory but can apply their own pricing markup.

## 🚀 Quick Start

### 1. Access Agent Management
1. Open the bot as an admin
2. Click `/admin` or use admin keyboard
3. Click **代理管理** button

### 2. Create Your First Agent

**Step 1: Get a Bot Token**
1. Go to @BotFather on Telegram
2. Send `/newbot`
3. Follow prompts to name your bot
4. Copy the token (format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

**Step 2: Add Agent in Bot**
1. In Agent Management panel, click **➕ 新增代理**
2. Paste the bot token
3. Enter a display name (e.g., "零售代理", "批发代理")
4. Wait for confirmation

**Result:**
```
✅ 代理创建成功！

📋 代理ID: agent_20250124_123456
🤖 名称: 零售代理
🟢 状态: 运行中
```

### 3. Manage Agents

**View All Agents:**
- Click **🔄 刷新列表** to refresh

**Start/Stop Agent:**
- Click **▶️ 启动** to start an agent
- Click **⏸ 停止** to stop an agent

**Delete Agent:**
- Click **🗑 删除** next to the agent
- Confirm deletion

## 📱 Button Reference

| Button | Action | Callback Data |
|--------|--------|---------------|
| 代理管理 | Open agent panel | `agent_manage` |
| 🔄 刷新列表 | Refresh list | `agent_refresh` |
| ➕ 新增代理 | Add new agent | `agent_new` |
| ▶️ 启动 | Start agent | `agent_tgl <id>` |
| ⏸ 停止 | Stop agent | `agent_tgl <id>` |
| 🗑 删除 | Delete agent | `agent_del <id>` |
| 🔙 返回控制台 | Back to admin | `backstart` |

## 🔍 Troubleshooting

### Agent Won't Start

**Symptoms:**
```
⚠️ 代理已保存，但启动失败
```

**Possible Causes:**
1. **Invalid Token**
   - Token expired or revoked
   - Token format incorrect
   - Solution: Check token in @BotFather

2. **Bot Not Accessible**
   - Bot not started with @BotFather
   - Solution: Send `/start` to your new bot

3. **Network Issues**
   - Temporary connection problem
   - Solution: Try starting again

**How to Fix:**
1. Click **🗑 删除** to remove the agent
2. Verify token is correct
3. Create the agent again

### Agent Doesn't Appear

**Check:**
1. Refresh the panel (click **🔄 刷新列表**)
2. Check logs for errors
3. Verify MongoDB/JSON storage is accessible

### Buttons Not Responding

**Solutions:**
1. Refresh the Telegram client
2. Check bot is running (main bot)
3. Check admin permissions
4. Review bot logs

## 📊 Agent Status Icons

| Icon | Status | Meaning |
|------|--------|---------|
| 🟢 | Running | Agent bot is active |
| 🔴 | Stopped | Agent bot is not running |
| 🟡 | Starting | Agent is being started |

## 🔐 Security

### Token Storage
- Bot tokens are **encrypted** with AES-256
- Stored securely in MongoDB or JSON file
- Only accessible by admin users

### Access Control
- All agent management requires admin privileges
- Admin IDs configured in `.env` file
- Verified on every operation

### Best Practices
1. Keep bot tokens confidential
2. Use unique names for each agent
3. Monitor agent activity regularly
4. Delete unused agents promptly

## 🛠️ Advanced Configuration

### Environment Variables
```bash
# Required for agent system
AGENT_TOKEN_AES_KEY=<base64_encoded_32_byte_key>

# Generate with:
python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
```

### MongoDB Storage
Agents are stored in the `agents` collection:
```javascript
{
  agent_id: "agent_20250124_123456",
  name: "零售代理",
  bot_token_encrypted: "...",
  status: "running",
  created_at: "2025-10-24 12:00:00"
}
```

### JSON Fallback
If MongoDB is unavailable, agents are stored in `agents.json`:
```json
[
  {
    "agent_id": "agent_20250124_123456",
    "name": "零售代理",
    "token": "...",
    "status": "running"
  }
]
```

## 📈 Monitoring

### Check Agent Status
```python
# In Python shell
from bot_integration import get_all_agents, RUNNING_AGENTS

agents = get_all_agents()
print(f"Total: {len(agents)}")
print(f"Running: {len(RUNNING_AGENTS)}")
```

### View Logs
```bash
tail -f logs/bot.log | grep -i agent
```

Look for:
- `✅ Agent created`
- `Agent ... started successfully`
- `Agent ... stopped`
- Error messages

## 🔄 Workflow Examples

### Example 1: Create Retail Agent
```
1. Admin clicks: 代理管理
2. Click: ➕ 新增代理
3. Send token: 1234567890:ABCdef...
4. Send name: 零售代理
5. Result: Agent created and running
```

### Example 2: Restart Failed Agent
```
1. Admin clicks: 代理管理
2. See: 🔴 零售代理 (已停止)
3. Click: ▶️ 启动 零售代理
4. Result: 🟢 零售代理 (运行中)
```

### Example 3: Remove Old Agent
```
1. Admin clicks: 代理管理
2. Find old agent
3. Click: 🗑 删除
4. Confirm: Agent deleted
5. Panel refreshes automatically
```

## 🆘 Support

### Common Issues

**Issue: "Token格式不正确"**
- Check token contains `:`
- Length should be > 30 characters
- No spaces or newlines

**Issue: "会话已过期"**
- Start over from clicking **➕ 新增代理**
- Complete both steps quickly

**Issue: "代理不存在"**
- Agent may have been deleted
- Refresh the panel
- Check storage (MongoDB/JSON)

### Getting Help

1. **Check Logs:** `tail -f logs/bot.log`
2. **Run Tests:** `python test_agent_system.py`
3. **Verify Setup:** `python verify_startup.py`
4. **Review Docs:** See `AGENT_FIX_SUMMARY.md`

## 📚 Additional Resources

- **Full Documentation:** `AGENT_FIX_SUMMARY.md`
- **Implementation Guide:** `AGENT_IMPLEMENTATION.md`
- **Test Suite:** `test_agent_system.py`
- **Verification Script:** `verify_startup.py`

## ✅ Checklist

Before going live:
- [ ] `.env` configured with `AGENT_TOKEN_AES_KEY`
- [ ] MongoDB or JSON storage accessible
- [ ] Admin IDs configured
- [ ] Main bot running successfully
- [ ] Test agent creation flow
- [ ] Test agent start/stop
- [ ] Test agent deletion
- [ ] Logs monitoring set up

---

**Version:** 1.0  
**Last Updated:** 2025-10-24  
**Status:** Production Ready
