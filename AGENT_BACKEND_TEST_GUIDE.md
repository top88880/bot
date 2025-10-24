# Agent Backend System - Testing Guide

This guide covers how to test the button-driven agent backend system.

## Prerequisites

1. MongoDB running with collections: `agents`, `agent_withdrawals`
2. Main bot running with token
3. Test agent bot token from @BotFather

## Test Scenarios

### 1. Creating an Agent (Admin Only)

**As Main Bot Admin:**
1. Send `/start` to main bot
2. Click "代理管理" or navigate to agent management
3. Click "➕ 新增代理"
4. Send agent bot token
5. Send agent name
6. Verify agent is created with `owner_user_id` set

**Expected Result:**
- Agent created successfully
- Agent status shows as "运行中" (running)
- `owner_user_id` field populated in MongoDB

### 2. Agent Backend Access (/agent command)

**As Agent Owner in Child Agent Bot:**
1. Start the child agent bot
2. Send `/agent` command
3. Verify panel appears with:
   - 差价设置 (Markup)
   - 可提现余额 (Available balance)
   - 已提现总额 (Total paid)
   - Configuration buttons

**Expected Result:**
- Panel appears ONLY for owner_user_id
- Other users see "❌ This command is only available to the agent owner"
- All financial stats show correct values

### 3. Setting Agent Markup

**As Agent Owner:**
1. In agent bot, send `/agent`
2. Click "💰 设置差价"
3. Send a markup value (e.g., "0.05")
4. Verify confirmation message

**Expected Result:**
- Markup saved in MongoDB (`markup_usdt` field)
- Confirmation shows new markup value

### 4. Verifying Markup in Prices

**As Any User in Child Agent Bot:**
1. Browse products in child agent bot
2. Compare prices with main bot
3. Verify child agent prices = base price + markup

**Test Points:**
- Product list: Prices show with markup
- Product detail (gmsp): Price shows with markup
- Purchase confirmation: Total = (base price + markup) × quantity
- Inline query share: Price shows with markup

**Expected Result:**
- All prices in child agent include the markup
- Main bot prices remain unchanged

### 5. Profit Recording

**As Customer in Child Agent Bot:**
1. Purchase a product
2. Check agent's `profit_available_usdt` in MongoDB

**Expected Result:**
- After successful order: `profit_available_usdt` increases by (markup × quantity)
- Profit quantized to 2 decimal places

### 6. Agent Withdrawal Request

**As Agent Owner:**
1. In agent bot, send `/agent`
2. Click "💸 发起提现"
3. Send amount (minimum 10 USDT)
4. Send TRC20 address (starts with T, 34 characters)
5. Verify confirmation

**Expected Result:**
- Withdrawal request created in `agent_withdrawals` collection
- Status: "pending"
- Amount moved from `profit_available_usdt` to `profit_frozen_usdt`
- Request ID shown: `aw_YYYYMMDD_HHMMSS_xxxxx`

### 7. Admin Withdrawal Review (Button Interface)

**As Admin in Main Bot:**
1. Go to agent management panel
2. Click "💰 审核提现 (N)" button
3. View list of pending withdrawals
4. For a withdrawal:
   - Click "✅ 批准" to approve OR
   - Click "❌ 拒绝" to reject

**Expected for Approval:**
- Status changes to "approved"
- Agent owner receives notification
- Funds remain frozen

**Expected for Rejection:**
- Status changes to "rejected"
- Funds return from frozen to available
- Agent owner receives notification with reason

### 8. Marking Withdrawal as Paid

**As Admin via Command:**
1. After approving a withdrawal and making the payment
2. Send: `/withdraw_pay <request_id> <TXID>`
3. Verify confirmation

**Expected Result:**
- Status changes to "paid"
- Funds deducted from `profit_frozen_usdt`
- Amount added to `total_paid_usdt`
- Agent owner receives notification with TXID

### 9. Configuring Agent-Specific Links

**As Agent Owner:**
1. In agent bot, send `/agent`
2. Click "📞 设置客服" and send a link (e.g., `@myagent_support`)
3. Click "📢 设置频道" and send a link
4. Click "📣 设置公告" and send a link
5. Click "🔘 管理按钮" to add custom buttons

**Expected Result:**
- Links saved in `agents.links` object
- Custom buttons saved in `extra_links` array (max 5)

### 10. Verifying Agent-Specific Links in Menus

**As Customer in Child Agent Bot:**
1. Browse menu and click "📞联系客服" button
2. Verify displayed links are agent-specific (not main bot's)

**Expected Result:**
- Customer service link is agent's (if set)
- Channel link is agent's (if set)
- Announcement link shown (if set)
- Custom buttons appear at bottom
- Falls back to main bot links if agent links not configured

### 11. Handler Priority Test

**Verify that:**
1. `/agent` command works in child agent (not consumed by catch-all)
2. Agent backend callbacks trigger correct handlers
3. Text input during agent flows captured correctly

**Expected Result:**
- No handler conflicts
- Agent flows complete successfully
- General message handlers don't interfere with agent flows

## Test Checklist

### Setup
- [ ] Main bot running
- [ ] MongoDB accessible
- [ ] Test agent created
- [ ] Agent bot running

### Agent Backend
- [ ] `/agent` command accessible to owner only
- [ ] Markup setting works
- [ ] Link configuration works
- [ ] Custom buttons (add/delete) work

### Price & Profit
- [ ] Prices show with markup in child agent
- [ ] Profit recorded after purchase
- [ ] Profit calculation correct (markup × quantity)

### Withdrawals
- [ ] Withdrawal request created (min 10 USDT)
- [ ] Funds moved to frozen
- [ ] Admin can see pending list via button
- [ ] Approval flow works with buttons
- [ ] Rejection flow works with buttons
- [ ] Notifications sent to agent owner

### Links
- [ ] Agent-specific links displayed in menus
- [ ] Custom buttons appear in contact menu
- [ ] Announcement link shown (if configured)
- [ ] Falls back to defaults when not configured

### Edge Cases
- [ ] Non-owner cannot access `/agent`
- [ ] Withdrawal with insufficient balance rejected
- [ ] Invalid TRC20 address rejected
- [ ] Markup applies only in child agent, not main bot
- [ ] Price calculations handle Decimal correctly

## Common Issues

### Issue: `/agent` command not working
**Solution:** Check handler registration order, ensure group=-1

### Issue: Prices not showing markup
**Solution:** Verify `calc_display_price_usdt()` called in all display functions

### Issue: Profit not accumulating
**Solution:** Check `record_agent_profit()` called after order success

### Issue: Withdrawal button not showing
**Solution:** Verify pending withdrawals exist, check MongoDB query

## Database Inspection Commands

```javascript
// Check agent configuration
db.agents.find({agent_id: "agent_XXXXXXXX"})

// Check withdrawal requests
db.agent_withdrawals.find({status: "pending"})

// Verify profit fields
db.agents.find({}, {
  name: 1,
  markup_usdt: 1,
  profit_available_usdt: 1,
  profit_frozen_usdt: 1,
  total_paid_usdt: 1
})
```

## Success Criteria

✅ All prices in child agents show markup correctly
✅ Profit accumulates after successful orders
✅ Agent owners can manage settings via buttons only
✅ Withdrawal flow works end-to-end with button interface
✅ Admin can review/approve/reject via buttons
✅ Agent-specific links used in child agent menus
✅ No regressions in main bot functionality
