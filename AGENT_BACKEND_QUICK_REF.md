# Agent Backend System - Quick Reference

## Quick Start

### 1. Migration (for existing installations)
```bash
python3 migrate_agents.py
```

### 2. Test Installation
```bash
python3 test_agent_backend.py
```

### 3. Create Agent
1. Open master bot
2. Admin command → 代理管理
3. Click 新增代理
4. Send bot token
5. Send agent name

### 4. Access Agent Backend
1. Open the agent bot (as the creator)
2. Send `/agent`
3. Use the dashboard

## Commands

### Agent Owner Commands
- `/agent` - Open agent backend dashboard (agent bot only)

### Admin Commands
- `/withdraw_list [status]` - List withdrawal requests
- `/withdraw_approve <request_id>` - Approve withdrawal
- `/withdraw_reject <request_id> [reason]` - Reject withdrawal
- `/withdraw_pay <request_id> <txid>` - Mark as paid
- `/withdraw_stats` - View statistics

## Agent Backend Features

### Set Markup
💰 设置差价 → Send amount in USDT (e.g., `0.05`)

### Request Withdrawal
💸 发起提现 → Send amount (≥10 USDT) → Send TRC20 address

### Manage Links
- 📞 设置客服 → Send @username or URL
- 📢 设置频道 → Send channel link
- 📣 设置公告 → Send announcement link
- Send `清除` to remove a link

### Manage Buttons
🔘 管理按钮 → Add/delete custom link buttons (max 5)

## Workflow

### Order Processing
1. Customer purchases in agent bot
2. Base price + agent markup charged
3. Order fulfilled
4. Profit = markup × quantity
5. Profit added to `profit_available_usdt`

### Withdrawal
1. Agent requests withdrawal (≥10 USDT)
2. Funds: available → frozen
3. Admin reviews with `/withdraw_list`
4. Admin approves with `/withdraw_approve <id>`
5. Admin processes payment manually
6. Admin confirms with `/withdraw_pay <id> <txid>`
7. Funds: frozen → (removed), total_paid updated
8. Agent notified

## File Structure

```
bot/
├── bot.py                      # Main bot with helper functions
├── bot_integration.py          # Agent management
├── mongo.py                    # Database with collections
├── handlers/
│   └── agent_backend.py        # Agent backend handlers
├── admin/
│   └── withdraw_commands.py    # Admin withdrawal commands
├── migrate_agents.py           # Migration script
├── test_agent_backend.py       # Test suite
├── AGENT_BACKEND_GUIDE.md      # Full documentation
└── AGENT_BACKEND_QUICK_REF.md  # This file
```

## Data Fields

### Agent Fields (agents collection)
```
owner_user_id: int              # Telegram user ID of owner
markup_usdt: str                # Per-item markup (e.g., "0.05")
profit_available_usdt: str      # Available for withdrawal
profit_frozen_usdt: str         # Frozen during withdrawal
total_paid_usdt: str            # Total paid out
links: {
  support_link: str,
  channel_link: str,
  announcement_link: str,
  extra_links: [{title, url}]
}
```

### Withdrawal Fields (agent_withdrawals collection)
```
request_id: str                 # "aw_YYYYMMDD_HHMMSS_xxxxx"
agent_id: str
owner_user_id: int
amount_usdt: str
fee_usdt: str (default "1")
address: str (TRC20)
status: str ("pending"|"approved"|"rejected"|"paid")
```

## Common Tasks

### Check Agent Setup
```python
from mongo import agents
agent = agents.find_one({'agent_id': 'agent_xxx'})
print(agent['owner_user_id'])
print(agent['markup_usdt'])
print(agent['profit_available_usdt'])
```

### Check Withdrawals
```python
from mongo import agent_withdrawals
pending = list(agent_withdrawals.find({'status': 'pending'}))
for w in pending:
    print(f"{w['agent_id']}: {w['amount_usdt']} USDT")
```

### Update Agent Markup Manually
```python
from mongo import agents
from datetime import datetime
agents.update_one(
    {'agent_id': 'agent_xxx'},
    {'$set': {
        'markup_usdt': '0.10',
        'updated_at': datetime.now()
    }}
)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `/agent` command not working | Check owner_user_id matches caller |
| No profit accumulating | Check markup_usdt > 0 |
| Withdrawal frozen | Check status in agent_withdrawals |
| Missing fields error | Run migrate_agents.py |
| Handler not found | Check imports in register_common_handlers |

## Status Codes

### Agent Status
- `stopped` - Not running
- `running` - Active
- `error` - Failed to start

### Withdrawal Status
- `pending` - Awaiting admin review
- `approved` - Approved, awaiting payment
- `rejected` - Rejected, funds returned
- `paid` - Completed

## Validation Rules

- Markup: ≥ 0 USDT
- Withdrawal: ≥ 10 USDT, ≤ available balance
- Fee: 1 USDT (fixed)
- TRC20 Address: Starts with 'T', length 34
- Custom buttons: Maximum 5

## Security

- Agent backend: Only owner_user_id can access
- Withdrawal commands: Only admins can execute
- Context isolation: Agent bots can't access master functions
- Token encryption: Bot tokens are encrypted in storage

## Performance Notes

- Helper functions cache agent data in bot_data
- Withdrawal queries indexed on status
- Agent queries indexed on agent_id
- Decimal precision: 2 decimal places (0.01 USDT)

## Next Steps (Not Implemented Yet)

- [ ] Agent-specific links in user-facing UI
- [ ] Price display with markup in product listings
- [ ] Withdrawal history in agent backend
- [ ] Analytics dashboard for agents

---

For full documentation, see: **AGENT_BACKEND_GUIDE.md**
