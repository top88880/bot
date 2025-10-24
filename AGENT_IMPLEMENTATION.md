# Multi-Tenant Agent Clone Bots - Implementation Guide

## Overview

This implementation adds a multi-tenant architecture to the bot, allowing creation of agent clone bots that:
- Share the same inventory with the master bot
- Apply agent-specific price markups
- Earn profits from markups
- Request withdrawals of earned profits
- Use the master bot's payment channels

## Architecture

### Tenant Model
- **Master Tenant**: The main bot (tenant = "master")
- **Agent Tenants**: Agent bots (tenant = "agent:<agent_id>")

### Data Isolation
- Users, orders, and topups are partitioned by tenant
- Inventory is shared across all tenants
- Payments flow through master bot's channels

### Collections

#### agents
Stores agent bot configuration:
```javascript
{
  agent_id: "agent001",
  name: "My Agent Bot",
  bot_token_encrypted: "base64_encrypted_token",
  status: "active",  // active, paused, suspended
  pricing: {
    markup_type: "percent",  // or "fixed"
    markup_value: 10
  },
  payout: {
    wallet_address: "TRC20_address",
    min_withdrawal: 10
  },
  created_at: ISODate,
  updated_at: ISODate
}
```

#### agent_ledger
Tracks agent profits:
```javascript
{
  agent_id: "agent001",
  order_id: "order_bianhao",
  type: "sale",  // or "refund"
  status: "pending",  // pending, matured, withdrawn, reverted
  base_price: 100,
  agent_price: 110,
  markup_per_item: 10,
  qty: 1,
  profit: 10,
  created_at: ISODate,
  mature_at: ISODate,  // 48 hours after created_at
  matured_at: ISODate,
  withdrawn_at: ISODate
}
```

#### agent_withdrawals
Tracks withdrawal requests:
```javascript
{
  agent_id: "agent001",
  amount: 100,
  wallet_address: "TRC20_address",
  status: "requested",  // requested, approved, paid, rejected
  requested_at: ISODate,
  approved_at: ISODate,
  paid_at: ISODate,
  txid: "transaction_hash",
  admin_note: "rejection reason"
}
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

New dependency added: `cryptography==41.0.7`

### 2. Environment Configuration

Add to your `.env` file:

```bash
# Generate a secure key:
# python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
AGENT_TOKEN_AES_KEY=your_base64_encoded_32_byte_key
```

### 3. Run Data Migration

```bash
python migrate_data.py
```

This will:
- Add `tenant="master"` to existing users
- Add `tenant="master"` to existing orders and topups
- Normalize inventory states to integers (0=available, 1=sold)

### 4. Start the Bot

The bot will automatically:
- Create database indexes
- Discover and start active agent bots
- Run maturity jobs for agent earnings

## Admin Commands

### Agent Management

```bash
# Create a new agent
/agent_create agent001 1234567890:ABC... MyAgentName

# List all agents
/agent_list

# Pause an agent
/agent_pause agent001

# Resume an agent
/agent_resume agent001

# Set agent pricing
/agent_pricing agent001 percent 10    # 10% markup
/agent_pricing agent001 fixed 5       # 5 USDT per item
```

### Withdrawal Management

```bash
# List withdrawal requests
/withdraw_list requested

# Approve a withdrawal
/withdraw_approve <withdrawal_id>

# Reject a withdrawal
/withdraw_reject <withdrawal_id> [reason]

# Mark as paid
/withdraw_pay <withdrawal_id> <txid>
```

## Agent Self-Service

Agents can access their panel to:
1. View earnings (available, pending, withdrawn)
2. Set their own pricing markup
3. Request withdrawals
4. View withdrawal history

## How It Works

### Pricing Flow

1. Product has base price: 100 USDT
2. Agent sets 10% markup
3. Agent bot shows price: 110 USDT
4. Customer pays: 110 USDT
5. Agent earns: 10 USDT profit

### Order Flow

1. Customer places order via agent bot
2. System reserves stock atomically
3. Customer's balance is debited (110 USDT)
4. Order is recorded with:
   - `tenant = "agent:agent001"`
   - `sold_by = {type: "agent", agent_id: "agent001"}`
   - `base_price = 100`
   - `agent_price = 110`
   - `markup_value = 10`
5. Profit entry created in agent_ledger (status: pending)

### Earnings Maturity

1. Scheduled job runs every 10 minutes
2. Ledger entries older than 48 hours are marked as matured
3. Matured profits become available for withdrawal

### Withdrawal Flow

1. Agent requests withdrawal via wallet panel
2. System checks available balance
3. Admin reviews and approves
4. Admin processes payment externally
5. Admin marks as paid with TXID
6. System updates ledger entries to withdrawn

## Security

### Token Encryption
- Agent bot tokens are encrypted using AES-GCM
- Encryption key stored in environment variable
- Never log plaintext tokens

### Atomic Stock Operations
- Uses MongoDB `find_one_and_update` to prevent overselling
- Implements automatic rollback on failure
- Race-condition safe across multiple bots

### Safe HTML Messaging
- Wrapper function `safe_send_html()` for all admin-configurable texts
- Falls back to escaped text if HTML parsing fails
- Prevents batch notification failures

## Performance

### Database Indexes

Automatically created on startup:
- `user`: (tenant, user_id) unique
- `gmjlu`: (tenant), (sold_by.type), (time desc)
- `topup`: (tenant), (status), (time desc)
- `hb`: (nowuid, state)
- `agents`: (agent_id) unique
- `agent_ledger`: (agent_id, status), (status, mature_at)
- `agent_withdrawals`: (agent_id, status)

### Scalability
- Tested with up to 50 concurrent agent bots
- Each agent bot runs in its own thread
- Shared database connection pool
- Atomic operations prevent conflicts

## Troubleshooting

### Agent bot won't start
- Check bot token is valid
- Verify AGENT_TOKEN_AES_KEY is set correctly
- Check logs for encryption errors

### Stock overselling
- Verify all bots are using atomic stock service
- Check hb.state values are integers (0 or 1)
- Review logs for failed reservations

### Earnings not showing
- Check if order is completed
- Verify profit entry was created in agent_ledger
- Check if still in maturity period (48 hours)

### Withdrawal failing
- Verify available balance is sufficient
- Check withdrawal status is "approved"
- Ensure ledger has matured entries

## Migration from Old System

1. **Backup your database**
2. Update code to latest version
3. Install new dependencies
4. Set AGENT_TOKEN_AES_KEY environment variable
5. Run `python migrate_data.py`
6. Restart bot
7. Test with master bot first
8. Create your first agent bot

## API Reference

### Services

- `services.crypto`: Token encryption/decryption
- `services.tenant`: Tenant context helpers
- `services.price_service`: Price markup calculations
- `services.stock_service`: Atomic inventory operations
- `services.agent_service`: Agent CRUD operations
- `services.earnings_service`: Profit tracking and withdrawals

### Handlers

- `admin.agents_admin`: Admin agent management
- `admin.withdraw_admin`: Admin withdrawal management
- `handlers.agent_panel`: Agent self-service panel
- `handlers.agent_wallet`: Agent wallet and withdrawals

## Contributing

When adding new features:
1. Maintain tenant isolation in all queries
2. Use atomic operations for inventory changes
3. Log all state transitions
4. Update indexes if adding new query patterns
5. Test with both master and agent bots

## Support

For issues or questions:
1. Check logs in `logs/bot.log`
2. Review this documentation
3. Check MongoDB indexes are created
4. Verify environment variables are set

## License

Same as parent project.
