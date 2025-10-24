# Agent Backend System Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         MAIN BOT                                 │
│  (Master Instance with Agent Management)                        │
│                                                                  │
│  Admin Functions:                                               │
│  • 代理管理 - Create/manage agents                               │
│  • /withdraw_list - View withdrawal requests                    │
│  • /withdraw_approve <id> - Approve withdrawal                  │
│  • /withdraw_reject <id> [reason] - Reject withdrawal           │
│  • /withdraw_pay <id> <txid> - Mark as paid                    │
│  • /withdraw_stats - View statistics                            │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ creates/manages
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AGENT BOT #1                                │
│  (Child Instance with agent_id in bot_data)                     │
│                                                                  │
│  Agent Owner Functions:                                         │
│  • /agent - Open dashboard                                      │
│    ├─ 💰 设置差价 - Set markup (e.g., 0.05 USDT)                │
│    ├─ 💸 发起提现 - Request withdrawal (≥10 USDT)              │
│    ├─ 📞 设置客服 - Set support link                            │
│    ├─ 📢 设置频道 - Set channel link                            │
│    ├─ 📣 设置公告 - Set announcement link                        │
│    └─ 🔘 管理按钮 - Manage custom buttons (max 5)              │
│                                                                  │
│  Customer Functions:                                            │
│  • Browse products (base price + agent markup)                  │
│  • Make purchases                                               │
│  • Profit automatically accrued to agent                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                      AGENT BOT #2                                │
│  (Another child instance with different agent_id)               │
│  ... (same structure as Agent Bot #1)                           │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Order Processing Flow
```
Customer in Agent Bot
       │
       ▼
Select product (base_price = 10 USDT)
       │
       ▼
Display price with markup (10 + 0.05 = 10.05 USDT)
       │
       ▼
Customer pays 10.05 USDT
       │
       ▼
Order fulfilled (dabaohao function)
       │
       ├─ Save order (goumaijilua)
       └─ Record profit (record_agent_profit)
              │
              ▼
       Increment agent.profit_available_usdt
       profit += markup × quantity
       (0.05 × 1 = 0.05 USDT added)
```

### 2. Withdrawal Flow
```
Agent Owner in Agent Bot
       │
       ▼
/agent → 💸 发起提现
       │
       ▼
Enter amount (e.g., 50 USDT)
       │
       ▼
Enter TRC20 address (T9yD14...)
       │
       ▼
Create withdrawal request
       │
       ├─ Freeze funds: available → frozen
       ├─ Set status: pending
       └─ Notify agent: "Request submitted"
       │
       ▼
Admin in Main Bot
       │
       ├─ /withdraw_list (sees pending request)
       │
       ├─ /withdraw_approve <id>
       │   └─ Set status: approved
       │   └─ Notify agent: "Approved, awaiting payment"
       │
       ├─ [Admin processes payment manually]
       │
       └─ /withdraw_pay <id> <txid>
           ├─ Move funds: frozen → (removed)
           ├─ Increment total_paid_usdt
           ├─ Set status: paid
           └─ Notify agent: "Paid! TXID: ..."
```

### 3. Markup Configuration Flow
```
Agent Owner in Agent Bot
       │
       ▼
/agent → 💰 设置差价
       │
       ▼
Bot: "Please enter markup in USDT"
       │
       ▼
Agent: "0.05"
       │
       ▼
Validate (≥ 0)
       │
       ▼
Update agent.markup_usdt = "0.05"
       │
       ▼
Notify: "Markup set to 0.05 USDT per item"
       │
       ▼
Future orders will include this markup
```

## Database Schema

### agents Collection
```javascript
{
  _id: ObjectId("..."),
  agent_id: "agent_20250124_143022",
  token: "encrypted_token_string",
  name: "My Agent Bot",
  status: "running",
  
  // NEW FIELDS (this PR)
  owner_user_id: 123456789,        // Telegram user ID
  markup_usdt: "0.05",              // Per-item markup
  profit_available_usdt: "150.25",  // Available for withdrawal
  profit_frozen_usdt: "50.00",      // Frozen during review
  total_paid_usdt: "200.00",        // Total paid out
  
  links: {
    support_link: "@mysupport",
    channel_link: "https://t.me/mychannel",
    announcement_link: "https://t.me/announcements",
    extra_links: [
      {title: "Website", url: "https://example.com"},
      {title: "FAQ", url: "https://example.com/faq"}
    ]
  },
  
  created_at: ISODate("2025-01-24T14:30:22Z"),
  updated_at: ISODate("2025-01-24T15:45:30Z")
}
```

### agent_withdrawals Collection (NEW)
```javascript
{
  _id: ObjectId("..."),
  request_id: "aw_20250124_143022_abc123",
  agent_id: "agent_20250124_143022",
  owner_user_id: 123456789,
  amount_usdt: "50.00",
  fee_usdt: "1",
  address: "T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb",
  status: "pending",  // → approved → paid
                      // or → rejected
  
  created_at: ISODate("2025-01-24T14:30:22Z"),
  reviewed_at: ISODate("2025-01-24T14:35:00Z"),
  reviewed_by: 987654321,  // Admin user ID
  paid_at: ISODate("2025-01-24T14:40:00Z"),
  paid_by: 987654321,
  txid: "0x1234567890abcdef...",
  reject_reason: null
}
```

## Code Structure

```
bot/
├── bot.py
│   ├── Helper Functions (NEW)
│   │   ├── get_current_agent_id(context) → agent_id | None
│   │   ├── get_agent_markup_usdt(context) → Decimal
│   │   ├── calc_display_price_usdt(base, context) → Decimal
│   │   └── record_agent_profit(context, order_doc)
│   │
│   ├── Modified Functions
│   │   ├── start_bot_with_token(token, enable_agent_system, agent_context)
│   │   ├── register_common_handlers(dispatcher, job_queue)
│   │   └── dabaohao(context, user_id, ...) - calls record_agent_profit
│   │
│   └── Handler Registration
│       ├── Agent backend handlers (group=-1)
│       ├── Admin withdrawal commands
│       └── Text input handler (group=-1)
│
├── bot_integration.py
│   ├── Modified Functions
│   │   ├── save_agent(token, name, owner_user_id) - NEW parameter
│   │   └── start_agent_bot(agent_id, token) - passes agent_context
│   │
│   └── Agent Management
│       ├── agent_manage(update, context)
│       ├── agent_new(update, context)
│       └── agent_tgl(update, context)
│
├── mongo.py
│   └── Modified Functions
│       └── goumaijilua(...) - now returns order_doc
│
├── handlers/
│   └── agent_backend.py (NEW - 600+ lines)
│       ├── agent_command(update, context)
│       ├── show_agent_panel(...)
│       ├── agent_set_markup_callback(...)
│       ├── agent_withdraw_init_callback(...)
│       ├── agent_set_link_callback(...)
│       ├── agent_manage_buttons_callback(...)
│       ├── agent_text_input_handler(...)
│       └── handle_* functions (markup, withdraw, links, buttons)
│
├── admin/
│   └── withdraw_commands.py (NEW - 400+ lines)
│       ├── withdraw_list_command(...)
│       ├── withdraw_approve_command(...)
│       ├── withdraw_reject_command(...)
│       ├── withdraw_pay_command(...)
│       └── withdraw_stats_command(...)
│
├── migrate_agents.py (NEW)
│   └── Backfills existing agents with new fields
│
├── test_agent_backend.py (NEW)
│   └── Test suite for validation
│
└── Documentation (NEW)
    ├── AGENT_BACKEND_GUIDE.md (9KB)
    ├── AGENT_BACKEND_QUICK_REF.md (5KB)
    └── IMPLEMENTATION_SUMMARY.md (3KB)
```

## State Management

### Agent Backend Text Input States
```
agent_backend_state values:
├── awaiting_markup
├── awaiting_withdraw_amount
├── awaiting_withdraw_address
├── awaiting_support_link
├── awaiting_channel_link
├── awaiting_announcement_link
├── awaiting_button_title
├── awaiting_button_url
└── awaiting_button_delete_index
```

### Withdrawal Status Lifecycle
```
pending ──────┬───→ approved ───→ paid
              │
              └───→ rejected

Transitions:
• pending → approved: Admin uses /withdraw_approve
• pending → rejected: Admin uses /withdraw_reject
• approved → paid: Admin uses /withdraw_pay
```

### Fund Movement
```
Available Balance
       │
       │ (withdrawal request)
       ▼
Frozen Balance ──┬──→ (if approved & paid) → Total Paid
                 │
                 └──→ (if rejected) → Available Balance
```

## Security Layers

```
┌─────────────────────────────────────┐
│    User Requests /agent             │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Check: Is this an agent bot?       │
│  (context.bot_data.get('agent_id')) │
└──────────────┬──────────────────────┘
               │ YES
               ▼
┌─────────────────────────────────────┐
│  Get agent from database            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Check: user_id == owner_user_id?   │
└──────────────┬──────────────────────┘
               │ YES
               ▼
┌─────────────────────────────────────┐
│  Show agent dashboard               │
└─────────────────────────────────────┘
```

## Handler Priority (Groups)

```
Group -1 (Highest Priority)
├── Agent backend command (/agent)
├── Agent backend callbacks (agent_*)
└── Agent backend text handler

Group 0 (Default)
├── Other bot commands
├── Other callbacks
└── Regular handlers

Group 1+ (Lower Priority)
└── Catch-all handlers
```

This ensures agent backend handlers execute before any catch-all handlers.

---

**Key Takeaways:**
1. ✅ Complete agent backend with self-service UI
2. ✅ Automatic profit accrual on every sale
3. ✅ Full withdrawal lifecycle with admin approval
4. ✅ Secure (owner verification, admin verification)
5. ✅ Migration-safe (defaults for existing agents)
6. ✅ Well-documented (14KB of guides)
7. ✅ Production-ready code

For implementation details, see **AGENT_BACKEND_GUIDE.md**
