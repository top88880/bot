# Quick Reference - Agent Clone Bots

## 🚀 Quick Start (5 Steps)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate encryption key
python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"

# 3. Add to .env
echo "AGENT_TOKEN_AES_KEY=<your_generated_key>" >> .env

# 4. Run migration
python migrate_data.py

# 5. Start bot
python bot.py
```

## 📝 Admin Commands

```bash
# Create agent
/agent_create <agent_id> <bot_token> <name>
Example: /agent_create agent001 123:ABC MyAgent

# List all agents
/agent_list

# Set pricing (10% markup)
/agent_pricing agent001 percent 10

# Set pricing (5 USDT per item)
/agent_pricing agent001 fixed 5

# Pause/Resume agent
/agent_pause agent001
/agent_resume agent001

# Withdrawal management
/withdraw_list requested
/withdraw_approve <withdrawal_id>
/withdraw_pay <withdrawal_id> <txid>
/withdraw_reject <withdrawal_id> [reason]
```

## 🎯 Key Concepts

### Tenant Model
- **Master**: `tenant = "master"`
- **Agent**: `tenant = "agent:agent001"`

### Pricing
```
Base Price: 100 USDT
Markup: 10% (or 5 USDT fixed)
Agent Price: 110 USDT (or 105 USDT)
Agent Profit: 10 USDT (or 5 USDT)
```

### Profit Flow
```
Order Placed → Pending (48h) → Matured → Withdrawal Request 
→ Admin Approve → Admin Pay → Withdrawn
```

## 📊 Collections

```javascript
// agents - Agent configuration
{ agent_id, name, bot_token_encrypted, status, pricing, payout }

// agent_ledger - Profit tracking
{ agent_id, order_id, profit, status, mature_at }

// agent_withdrawals - Withdrawal requests
{ agent_id, amount, status, txid }
```

## 🔧 Environment Variables

```bash
# Required for agent system
AGENT_TOKEN_AES_KEY=<base64_32_bytes>

# All other vars same as before
BOT_TOKEN=...
ADMIN_IDS=...
MONGO_URI=...
```

## ⚡ Integration Points

### bot.py Changes (14 lines total)

```python
# After imports (line ~74)
try:
    from bot_integration import integrate_agent_system
    AGENT_SYSTEM_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Agent system not available: {e}")
    AGENT_SYSTEM_AVAILABLE = False

# In main(), after dispatcher setup (line ~10255)
dispatcher = updater.dispatcher

if AGENT_SYSTEM_AVAILABLE:
    try:
        integrate_agent_system(dispatcher, updater.job_queue)
    except Exception as e:
        logging.error(f"Failed to initialize agent system: {e}")
        logging.info("Continuing with master bot only...")
```

## 🔍 Verification

```bash
# Check logs for:
grep "Agent System Initialization Complete" logs/bot.log

# Check database:
mongo
> use xc1111bot
> db.agents.find().pretty()
> db.agent_ledger.find().pretty()
```

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Agent won't start | Check bot token, verify AGENT_TOKEN_AES_KEY |
| No profits showing | Check order completed, wait 48h for maturity |
| Can't withdraw | Verify available > min_withdrawal (10 USDT) |
| Indexes missing | Restart bot, indexes auto-create |
| Migration fails | Check MongoDB connection, backup first |

## 📈 Performance

- Max agents: ~50 recommended
- Index creation: Automatic on startup
- Maturity job: Every 10 minutes
- Agent monitoring: Every 60 seconds

## 🛡️ Security Checklist

- [ ] AGENT_TOKEN_AES_KEY is 32 bytes (base64)
- [ ] Encryption key not in git
- [ ] Admin IDs configured correctly
- [ ] MongoDB has authentication
- [ ] Logs don't show plaintext tokens
- [ ] Backup database before deployment

## 📚 Documentation

- `IMPLEMENTATION_SUMMARY.md` - Complete overview
- `AGENT_IMPLEMENTATION.md` - Technical deep-dive
- `INTEGRATION_INSTRUCTIONS.txt` - Deployment steps
- `教程.txt` - Chinese tutorial
- `.env.example` - Environment template

## 🎓 Example Workflow

```bash
# 1. Admin creates agent
/agent_create agent001 1234567890:ABC TestAgent

# 2. Admin sets 10% markup
/agent_pricing agent001 percent 10

# 3. Agent bot starts automatically
# (Check /agent_list to verify)

# 4. Customer buys via agent bot
# Base: 100 USDT → Agent shows: 110 USDT

# 5. Profit recorded in ledger (pending)

# 6. After 48 hours, becomes matured

# 7. Agent requests withdrawal via wallet panel

# 8. Admin approves
/withdraw_approve <id>

# 9. Admin pays externally and marks paid
/withdraw_pay <id> TXIDhash123

# 10. System updates ledger to withdrawn
```

## 🚨 Emergency Rollback

```python
# In bot.py, comment these lines:
# if AGENT_SYSTEM_AVAILABLE:
#     try:
#         integrate_agent_system(dispatcher, updater.job_queue)
#     ...

# Restart bot
python bot.py
# Master bot continues, agents disabled
```

## 📞 Support

- Check `logs/bot.log` first
- Review error messages
- Verify environment variables
- Test with master bot first
- Create test agent before production

---

**Quick Ref v1.0 | Agent Clone Bots | 2025-10-24**
