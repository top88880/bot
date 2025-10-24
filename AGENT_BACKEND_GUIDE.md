# Agent Markup and Backend System - Implementation Guide

## Overview

This implementation adds a comprehensive agent backend system to the bot, allowing each agent bot to:
- Set their own markup/profit margin on products (USDT only)
- Automatically accumulate profits from sales
- Manage agent-specific contact links and branding
- Request and receive withdrawals with admin approval

## Key Features

### 1. Agent Markup System (USDT Only)
- Each agent can set a per-item markup in USDT (e.g., 0.05 USDT per item)
- Markup is added to the base product price automatically
- Profit accumulates in the agent's account with each sale

### 2. Agent Backend (/agent command)
- Only available in child agent bots
- Only accessible by the agent owner (owner_user_id)
- Provides dashboard with:
  - Current markup setting
  - Available, frozen, and total paid balances
  - Link management
  - Withdrawal initiation

### 3. Withdrawal System
- Agents can request withdrawals (minimum 10 USDT)
- 1 USDT fee per withdrawal
- Funds are frozen during review
- Admin approves/rejects requests
- Automatic notifications to agents

### 4. Agent-Specific Links
- Support/customer service link
- Channel link
- Announcement link
- Up to 5 custom button links
- Used instead of main bot links in child agents

## Setup Instructions

### 1. Run Migration Script

First, migrate existing agents to add the new fields:

```bash
python3 migrate_agents.py
```

This will add default values for all required fields to existing agents.

### 2. Agent Creation

When creating a new agent through the bot:
1. Admin uses "代理管理" button
2. Click "新增代理"
3. Send bot token
4. Send agent name
5. Agent is created with owner_user_id set to the admin's user ID

### 3. Agent Owner Access

The agent owner (the admin who created the agent) can now:
1. Open their agent bot
2. Use `/agent` command
3. Access the agent backend dashboard

## Usage Guide

### For Agent Owners

#### Setting Markup
1. Use `/agent` command
2. Click "💰 设置差价"
3. Send markup amount in USDT (e.g., `0.05` or `1`)
4. Markup applies to all future sales

#### Managing Links
1. Use `/agent` command
2. Click "📞 设置客服", "📢 设置频道", or "📣 设置公告"
3. Send link in format:
   - `@username`
   - `https://t.me/username`
   - `https://example.com`
4. Send `清除` to remove a link

#### Managing Custom Buttons
1. Use `/agent` command
2. Click "🔘 管理按钮"
3. Click "➕ 添加按钮"
4. Send button title
5. Send button URL
6. Maximum 5 custom buttons

#### Requesting Withdrawal
1. Use `/agent` command
2. Click "💸 发起提现"
3. Send amount (minimum 10 USDT)
4. Send TRC20 USDT address
5. Wait for admin approval

### For Admins

#### Viewing Withdrawal Requests
```
/withdraw_stats          - View statistics
/withdraw_list           - List pending requests
/withdraw_list approved  - List approved requests
/withdraw_list all       - List all requests
```

#### Approving Withdrawals
```
/withdraw_approve <request_id>
```
Example: `/withdraw_approve aw_20250124_143022_123456`

#### Rejecting Withdrawals
```
/withdraw_reject <request_id> [reason]
```
Example: `/withdraw_reject aw_20250124_143022_123456 Invalid address`

#### Marking as Paid
```
/withdraw_pay <request_id> <txid>
```
Example: `/withdraw_pay aw_20250124_143022_123456 0x1234567890abcdef...`

## Data Model

### Agents Collection

New fields added:
```javascript
{
  agent_id: "agent_20250124_143022",
  token: "encrypted_token",
  name: "My Agent Bot",
  status: "running",
  
  // NEW FIELDS
  owner_user_id: 123456789,  // Telegram user ID of owner
  markup_usdt: "0.05",        // Per-item markup in USDT
  profit_available_usdt: "150.25",  // Available for withdrawal
  profit_frozen_usdt: "50.00",       // Frozen during withdrawal
  total_paid_usdt: "200.00",        // Total ever paid out
  
  links: {
    support_link: "@mysupport",
    channel_link: "https://t.me/mychannel",
    announcement_link: null,
    extra_links: [
      {title: "Website", url: "https://example.com"},
      {title: "FAQ", url: "https://example.com/faq"}
    ]
  },
  
  created_at: ISODate("2025-01-24T14:30:22Z"),
  updated_at: ISODate("2025-01-24T14:30:22Z")
}
```

### Agent Withdrawals Collection

New collection structure:
```javascript
{
  request_id: "aw_20250124_143022_123456",
  agent_id: "agent_20250124_143022",
  owner_user_id: 123456789,
  amount_usdt: "50.00",
  fee_usdt: "1",
  address: "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
  status: "pending",  // pending | approved | rejected | paid
  created_at: ISODate("2025-01-24T14:30:22Z"),
  reviewed_at: null,
  reviewed_by: null,
  paid_at: null,
  paid_by: null,
  txid: null,
  reject_reason: null
}
```

## Implementation Details

### Bot Context System

Each agent bot instance now has `bot_data` with:
```python
context.bot_data = {
    'agent_id': 'agent_20250124_143022',
    'owner_user_id': 123456789
}
```

This allows any handler to know if it's running in an agent context.

### Helper Functions

Three new helper functions in `bot.py`:

```python
def get_current_agent_id(context) -> str:
    """Returns agent_id or None if master bot."""
    
def get_agent_markup_usdt(context) -> Decimal:
    """Returns agent markup or Decimal('0')."""
    
def calc_display_price_usdt(base_price_usdt: Decimal, context) -> Decimal:
    """Calculates final price = base + markup."""
```

### Profit Accrual

When an order is completed (in `dabaohao` function):
1. Order record is saved via `goumaijilua()`
2. `record_agent_profit(context, order_doc)` is called
3. Profit is calculated: `markup_usdt × quantity`
4. Agent's `profit_available_usdt` is incremented

### Withdrawal Lifecycle

1. **Request**: Agent requests amount ≥ 10 USDT
   - Funds move: available → frozen
   - Status: pending
   - Notification: Agent owner receives confirmation

2. **Approval**: Admin approves request
   - Status: pending → approved
   - Notification: Agent owner notified

3. **Payment**: Admin marks as paid with TXID
   - Funds move: frozen → (removed)
   - total_paid_usdt incremented
   - Status: approved → paid
   - Notification: Agent owner notified

4. **Rejection**: Admin rejects request
   - Funds move: frozen → available
   - Status: pending → rejected
   - Notification: Agent owner notified with reason

## Handler Registration

New handlers are registered with `group=-1` to ensure they run before catch-all handlers:

```python
# Agent backend command
dispatcher.add_handler(CommandHandler('agent', agent_command, run_async=True), group=-1)

# Agent backend callbacks
dispatcher.add_handler(CallbackQueryHandler(agent_panel_callback, pattern='^agent_panel$'), group=-1)
# ... more callbacks ...

# Agent backend text input handler
dispatcher.add_handler(MessageHandler(
    Filters.chat_type.private & Filters.text & ~Filters.command,
    agent_text_input_handler, run_async=True
), group=-1)
```

## Security Considerations

1. **Owner Verification**: `/agent` command checks `owner_user_id` matches caller
2. **Admin Verification**: Withdrawal commands check `is_admin(user_id)`
3. **Address Validation**: Basic TRC20 address format check (T prefix, 34 chars)
4. **Amount Validation**: Minimum withdrawal 10 USDT, maximum = available balance
5. **Context Isolation**: Agent bots cannot access master bot functions

## Testing Checklist

- [ ] Create a new agent and verify owner_user_id is saved
- [ ] Use /agent command in agent bot as owner
- [ ] Set markup and verify it's saved
- [ ] Make a purchase and verify profit is accrued
- [ ] Set agent-specific links
- [ ] Add/delete custom buttons
- [ ] Request withdrawal with valid address
- [ ] Admin: list pending withdrawals
- [ ] Admin: approve withdrawal
- [ ] Admin: mark as paid with TXID
- [ ] Verify agent receives all notifications
- [ ] Test rejection flow
- [ ] Run migration script on test data
- [ ] Verify agent-specific links appear in child bot (TODO)

## Future Enhancements

Potential improvements (not in current scope):
- Variable withdrawal fees based on amount
- Automated on-chain payouts (requires TronPy integration)
- Withdrawal history view in agent backend
- Profit charts and analytics
- Per-product markup overrides
- Tiered markup system (volume-based)

## Troubleshooting

### Agent can't access /agent command
- Check agent was started with agent_context
- Verify owner_user_id is set in database
- Ensure user_id matches owner_user_id

### Profit not accumulating
- Check agent has markup_usdt > 0
- Verify orders are completing successfully
- Check dabaohao calls record_agent_profit

### Withdrawal frozen funds not updating
- Check status transitions in admin commands
- Verify Decimal arithmetic is correct
- Check for MongoDB update errors in logs

### Links not showing in child bot
- This feature is not yet implemented
- Agent-specific links are stored but not yet used
- See "Next Steps" for implementation plan

## Support

For issues or questions:
1. Check logs in `logs/bot.log`
2. Review MongoDB collections: `agents`, `agent_withdrawals`
3. Test with migration script: `python3 migrate_agents.py`
4. Contact development team

---

**Version**: 1.0  
**Date**: 2025-01-24  
**Status**: Core implementation complete, testing pending
