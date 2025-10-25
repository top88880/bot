# Testing Guide for Restock Notifications and TRC20 Auto-Credit

This guide explains how to test the new features implemented in this PR.

## Part 1: Restock Notification Broadcasting

### Prerequisites
- Main bot and at least one agent bot should be configured
- Agent bot should have `notify_channel_id` set in settings
- Main bot should have `NOTIFY_CHANNEL_ID` environment variable set

### Test 1: Stock Upload and Notification
1. Log in as admin to the main bot
2. Go to admin panel → 商品管理 (Product Management)
3. Select a product category
4. Upload stock using one of the methods:
   - 上传号包 (Upload package)
   - 上传谷歌账户 (Upload Google accounts)
   - 上传txt文件 (Upload txt file)
   - 上传协议号 (Upload protocol numbers)
5. After upload completes, check:
   - ✅ Main bot's notify channel receives notification
   - ✅ All agent bots' notify channels receive the same notification
   - ✅ Check logs for successful broadcasts

### Expected Result
```
✅ Sent restock notification to main channel -1001234567890
✅ Sent restock notification to agent agent_20231225_123456 (AgentName) channel -1009876543210
```

### Test 2: Agent Without Notify Channel
1. Create an agent without setting `notify_channel_id`
2. Upload stock
3. Check logs should show:
   - ✅ "Skipping agent X: no notify_channel_id"

### Test 3: Multiple Agents
1. Configure 3+ agents with different notify channels
2. Upload stock
3. Verify all agents receive notification within a few seconds
4. Check for 0.5s delay between sends (throttling)

## Part 2: TRC20 USDT Auto-Credit

### Prerequisites
- Set environment variables:
  ```bash
  USDT_CONTRACT=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t
  TRON_MIN_CONFIRMATIONS=2
  TRONGRID_API_KEY=your_api_key_here  # Optional but recommended
  ```
- Ensure `jxqk.py` and `zf.py` are running
- Have test USDT on TRON testnet or mainnet

### Test 1: Normal Payment Flow
1. User initiates topup in bot (充值)
2. User receives payment address and amount
3. User sends EXACT amount of USDT to the address
4. Wait for 2 confirmations (about 6 seconds on TRON)
5. Check:
   - ✅ Transaction appears in `qukuai` collection
   - ✅ Order in `topup` collection changes status to 'completed'
   - ✅ User balance increases by the amount
   - ✅ User receives notification of successful payment

### Test 2: Insufficient Confirmations
1. User sends payment
2. Check immediately after 1 confirmation:
   - ✅ Transaction in qukuai but state=0 (not processed)
   - ✅ Logs show "Insufficient confirmations"
3. Wait for 2nd confirmation:
   - ✅ Payment auto-credits

### Test 3: Wrong Amount
1. User sends different amount than order
2. Check:
   - ✅ Transaction stored but not matched to order
   - ✅ Logs show "No matching order found"

### Test 4: Wrong Token (Not USDT)
1. Send TRX or other TRC20 token to payment address
2. Check:
   - ✅ Transaction ignored (not stored in qukuai)
   - ✅ Logs show "Skipping non-USDT transaction"

### Test 5: Duplicate Payment Prevention
1. Successfully complete a payment
2. Try to rescan the same TXID via admin panel
3. Check:
   - ✅ Shows "already credited"
   - ✅ Balance not doubled

## Part 3: Admin Rescan Tools

### Prerequisites
- Be logged in as admin
- Have access to admin panel

### Test 1: Access TRC20 Admin Panel
1. Open bot, use `/start`
2. Access admin panel (if you're an admin)
3. Click "TRC20 支付管理"
4. Verify you see:
   - 按交易ID扫描 (Scan by TXID)
   - 按订单号扫描 (Scan by Order ID)
   - 扫描所有待处理 (Scan all pending)
   - 待处理统计 (Pending statistics)

### Test 2: Rescan by TXID
1. Find a valid TXID of a paid transaction (check TronScan)
2. Click "按交易ID扫描"
3. Send the TXID
4. Check:
   - ✅ If not yet credited: credits successfully
   - ✅ If already credited: shows "already credited"
   - ✅ If invalid: shows error message

### Test 3: Rescan by Order ID
1. Find a pending order number (bianhao) from database
2. Click "按订单号扫描"
3. Send the order number
4. Check:
   - ✅ If matching payment exists: credits successfully
   - ✅ If no match: shows "No matching payment found"

### Test 4: Scan All Pending
1. Create 2-3 pending orders with payments
2. Click "扫描所有待处理"
3. Wait for scan to complete
4. Check:
   - ✅ Shows statistics: total, credited, pending, expired, failed
   - ✅ Valid payments are credited
   - ✅ Expired orders marked as expired

### Test 5: Pending Statistics
1. Click "待处理统计"
2. Verify display shows:
   - ✅ Number of pending orders
   - ✅ Total pending amount in USDT
   - ✅ Number of completed orders in last 24h

## Logging and Debugging

### Key Log Messages to Monitor

**Restock Broadcasts:**
```
Starting restock broadcast to agents: 📦 商品 ...
✅ Sent restock notification to agent agent_123 (AgentName) channel -1001234567890
Restock broadcast complete: 2 success, 1 skipped, 0 failed
```

**TRC20 Processing:**
```
Processing transaction: txid=7c9d8..., to=THPVJv..., amount=10.000000
✅ Credited order CZ20231225123456: user=123456, amount=10.000000 USDT, txid=7c9d8...
⚠️ Insufficient confirmations for 7c9d8...: 1/2
❌ No matching order found for txid=7c9d8..., amount=5.500000
```

### Database Queries for Verification

**Check pending orders:**
```javascript
db.topup.find({status: 'pending', cz_type: 'usdt'})
```

**Check completed orders:**
```javascript
db.topup.find({status: 'completed', txid: {$exists: true}})
```

**Check transactions:**
```javascript
db.qukuai.find({type: 'USDT', state: 0})  // Unprocessed
db.qukuai.find({type: 'USDT', state: 1})  // Processed
```

**Check agent notify channels:**
```javascript
db.agents.find({}, {'name': 1, 'settings.notify_channel_id': 1})
```

## Common Issues and Solutions

### Issue: Agent channels not receiving notifications
**Solution:** 
- Check agent has notify_channel_id set
- Verify agent bot token is valid
- Check agent bot has permission to post in channel

### Issue: Payments not auto-crediting
**Solution:**
- Check jxqk.py is running
- Verify TRON_MIN_CONFIRMATIONS is set correctly
- Check logs for error messages
- Use admin rescan tool to manually process

### Issue: "Rate limited" errors
**Solution:**
- Set TRONGRID_API_KEY for higher rate limits
- Increase delay between broadcast sends (currently 0.5s)

### Issue: Amount mismatch
**Solution:**
- USDT has 6 decimals, ensure exact match
- Check tolerance is 0.000001 USDT
- User must send exact amount shown in order

## Performance Monitoring

### Metrics to Track
1. **Restock Broadcast Speed:** Should complete within seconds for <10 agents
2. **TRC20 Auto-Credit Latency:** Should credit within 6-10 seconds after 2 confirmations
3. **Database Query Performance:** Monitor `topup` and `qukuai` collection sizes

### Optimization Tips
1. Consider adding database indexes on:
   - `topup.status`
   - `topup.txid`
   - `qukuai.type`
   - `qukuai.state`
   - `qukuai.txid`
2. Monitor RabbitMQ queue sizes
3. Set up alerts for failed broadcasts or payment processing errors
