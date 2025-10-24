# 🤖 Multi-Tenant Telegram Bot - Agent Clone System

A comprehensive Telegram bot platform with multi-tenant agent clone architecture, allowing creation of unlimited agent bots that share inventory while maintaining independent pricing and profit tracking.

## ✨ Features

### Core Platform
- 🏪 Product inventory management
- 💳 Multiple payment methods (USDT TRC20, Alipay, WeChat)
- 👥 User management with multi-language support
- 📊 Real-time stock notifications
- 🔐 Secure payment processing

### Agent Clone System (NEW!)
- 🤖 Unlimited agent bots sharing the same inventory
- 💰 Independent pricing markup per agent (percent or fixed)
- 📈 Automated profit tracking and maturity (48h)
- 💸 Complete withdrawal request workflow
- 🔒 AES-GCM encrypted agent bot tokens
- ⚡ Atomic stock operations (no overselling)
- 🎛️ Admin panel for agent management
- 📱 Agent self-service panels

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- MongoDB 4.0+
- Telegram Bot Token

### Installation

```bash
# Clone repository
git clone <your-repo-url>
cd bot

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Generate agent encryption key
python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
# Add the output as AGENT_TOKEN_AES_KEY in .env

# Run data migration (first time only)
python migrate_data.py

# Start the bot
python bot.py
```

## 📖 Documentation

- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Command cheat sheet and quick reference
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Complete technical overview
- **[AGENT_IMPLEMENTATION.md](AGENT_IMPLEMENTATION.md)** - Architecture deep-dive
- **[INTEGRATION_INSTRUCTIONS.txt](INTEGRATION_INSTRUCTIONS.txt)** - Step-by-step deployment
- **[教程.txt](教程.txt)** - Chinese setup tutorial

## 🎮 Admin Commands

### Agent Management
```bash
/agent_create <agent_id> <bot_token> <name>  # Create new agent
/agent_list                                   # List all agents
/agent_pricing <agent_id> percent 10          # Set 10% markup
/agent_pricing <agent_id> fixed 5             # Set 5 USDT markup
/agent_pause <agent_id>                       # Pause agent
/agent_resume <agent_id>                      # Resume agent
```

### Withdrawal Management
```bash
/withdraw_list [status]                # List withdrawal requests
/withdraw_approve <withdrawal_id>      # Approve withdrawal
/withdraw_pay <withdrawal_id> <txid>  # Mark as paid
/withdraw_reject <withdrawal_id>       # Reject withdrawal
```

### Standard Commands
```bash
/start                    # Start bot
/admin                    # Admin panel
/gg <message>            # Broadcast message
/add <user_id> +amount   # Add balance
/cha <user_id>           # Check user info
```

## 🏗️ Architecture

### Multi-Tenant Model
```
Master Bot (tenant: "master")
├── Agent Bot 1 (tenant: "agent:agent001")
├── Agent Bot 2 (tenant: "agent:agent002")
└── Agent Bot N (tenant: "agent:agentN")

Shared: Inventory, Payment Channels
Isolated: Users, Orders, Profits per Tenant
```

### Profit Flow
```
Order → Pending (48h) → Matured → Withdrawal Request 
     → Admin Approve → Admin Pay (TXID) → Withdrawn
```

### Database Collections
- **agents**: Agent bot configuration
- **agent_ledger**: Profit tracking with maturity
- **agent_withdrawals**: Withdrawal request lifecycle
- **user**: User accounts (tenant-aware)
- **gmjlu**: Order records (tenant-aware)
- **topup**: Recharge records (tenant-aware)
- **hb**: Product inventory (shared)

## 🔐 Security

- ✅ AES-GCM 256-bit encryption for agent tokens
- ✅ Atomic database operations prevent race conditions
- ✅ Admin-only command restrictions
- ✅ Input validation on all endpoints
- ✅ Safe HTML rendering with fallback
- ✅ No plaintext token logging

## 📊 Performance

- **Concurrent Agents**: Up to 50 recommended
- **Maturity Job**: Every 10 minutes
- **Agent Monitoring**: Every 60 seconds
- **Database**: Auto-indexed for optimal queries
- **Stock Operations**: Atomic (prevents overselling)

## 🛠️ Configuration

### Environment Variables (.env)
```bash
# Bot Configuration
BOT_TOKEN=your_bot_token
ADMIN_IDS=123456789,987654321

# MongoDB
MONGO_URI=mongodb://127.0.0.1:27017/
MONGO_DB_BOT=xc1111bot

# Payment
EASYPAY_PID=your_pid
EASYPAY_KEY=your_key
EASYPAY_GATEWAY=https://your_gateway/submit.php
ENABLE_ALIPAY_WECHAT=true

# Agent System (Required)
AGENT_TOKEN_AES_KEY=base64_encoded_32_byte_key
```

## 🔄 Migration

First-time deployment requires data migration:

```bash
python migrate_data.py
```

This will:
- Add `tenant` field to existing users
- Add `tenant` and `sold_by` to existing orders
- Normalize inventory states to integers
- Convert timer strings to datetime objects

## 📈 Example Workflow

1. **Admin creates agent**
   ```bash
   /agent_create agent001 1234567890:ABC TestAgent
   ```

2. **Admin sets pricing**
   ```bash
   /agent_pricing agent001 percent 10  # 10% markup
   ```

3. **Customer buys via agent bot**
   - Base price: 100 USDT
   - Agent shows: 110 USDT (with 10% markup)
   - Agent earns: 10 USDT profit

4. **Profit matures after 48 hours**
   - Status changes from "pending" to "matured"
   - Available for withdrawal

5. **Agent requests withdrawal**
   - Via agent wallet panel
   - Minimum 10 USDT

6. **Admin processes withdrawal**
   ```bash
   /withdraw_approve <id>
   /withdraw_pay <id> <txid>
   ```

7. **System updates ledger**
   - Status: "withdrawn"
   - Records TXID

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Agent won't start | Verify bot token and AGENT_TOKEN_AES_KEY |
| No profits showing | Check order completed, wait 48h maturity |
| Can't withdraw | Verify balance > min_withdrawal (10 USDT) |
| Indexes missing | Restart bot, auto-created on startup |
| Migration fails | Check MongoDB connection, backup first |

## 🔙 Rollback

If issues occur, comment out agent integration in bot.py:

```python
# if AGENT_SYSTEM_AVAILABLE:
#     try:
#         integrate_agent_system(dispatcher, updater.job_queue)
#     ...
```

Restart bot. System continues without agent features.

## 📝 License

[Your License Here]

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

## 📞 Support

- Check logs: `logs/bot.log`
- Review documentation in `/docs`
- Open an issue for bugs
- Contact maintainers for questions

## 🎯 Roadmap

- [x] Multi-tenant architecture
- [x] Agent bot management
- [x] Profit tracking system
- [x] Withdrawal workflow
- [ ] Web dashboard (future)
- [ ] Analytics & reporting (future)
- [ ] Multi-currency support (future)

---

**Status**: ✅ Production Ready
**Version**: 1.0.0
**Last Updated**: 2025-10-24

Made with ❤️ using GitHub Copilot
