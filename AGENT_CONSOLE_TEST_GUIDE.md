# Agent Console Enhancement Testing Guide

This guide provides step-by-step instructions for testing the new agent console features.

## Prerequisites

- Admin access to the main bot
- At least one agent bot configured
- Test user accounts for owner management testing

## Feature 1: Multi-Owner Management

### Admin Panel - Owner Management

1. **Access Owner Management**
   - Open main bot
   - Send `/start` command
   - Click "Agent Manage" button
   - You should see a "👑 拥有者" button for each agent

2. **View Current Owners**
   - Click "👑 拥有者" for any agent
   - Should display:
     - Agent name
     - List of current owners (if any)
     - "➕ 添加拥有者" button
     - "➖ 移除" button for each owner

3. **Add Owners**
   - Click "➕ 添加拥有者"
   - Send a user ID (e.g., `123456789`)
   - Or send multiple IDs space-separated: `123456789 987654321`
   - Should show success message with count
   - Verify owners appear in the list

4. **Remove Owners**
   - In the owner management panel
   - Click "➖ 移除 {user_id}" for an owner
   - Should show "✅ 拥有者已移除" alert
   - Verify owner is removed from list

### Child Agent - Owner Claim Flow

5. **Test Claim When No Owners**
   - Ensure agent has empty owners array
   - Open the child agent bot
   - Send `/agent` command
   - Should show "🤖 代理后台 - 未绑定" message
   - Click "🔐 绑定为拥有者"
   - Should show success message
   - Send `/agent` again - should now show full panel

6. **Test Owner Permissions**
   - Add user as owner via admin panel
   - As that user, open child agent bot
   - Send `/agent` command
   - Should show full agent panel
   - As non-owner user, send `/agent`
   - Should show "❌ This command is only available to the agent owner."

## Feature 2: i18n (Language Support)

### Chinese Language (zh)

7. **Test Chinese Interface**
   - Set Telegram language to Chinese OR
   - Ensure user record has `lang: 'zh'`
   - Send `/agent` in child bot
   - Verify all text is in Chinese:
     - "🤖 代理后台"
     - "📊 财务概况"
     - "🔗 联系方式"
     - Button text in Chinese

### English Language (en)

8. **Test English Interface**
   - Set Telegram language to English OR
   - Update user record to `lang: 'en'`
   - Send `/agent` in child bot
   - Verify all text is in English:
     - "🤖 Agent Backend"
     - "📊 Financial Overview"
     - "🔗 Contact Information"
     - Button text in English

### Language Detection

9. **Test Auto-Detection**
   - Clear user `lang` field in database
   - Set Telegram language to Chinese
   - Send `/agent` - should be in Chinese
   - Change Telegram language to English
   - Clear session and send `/agent` - should be in English

## Feature 3: Restock Notifications

### Configure Notification Channel

10. **Set Notify Channel ID**
    - In child agent bot, send `/agent`
    - Click "🔔 设置通知频道ID" (or English equivalent)
    - Send channel ID in format: `-1001234567890`
    - Verify it's saved and displayed in panel

### Test Notification Sending

11. **Send Test Notification**
    - In agent panel, click "📡 发送测试通知"
    - If configured correctly:
      - Should show "✅ 测试通知发送成功！" alert
      - Check the notification channel for test message
    - If not configured:
      - Should show "❌ 未设置通知频道" alert
    - If bot not in channel:
      - Should show detailed error message with troubleshooting steps

12. **Test Notification Errors**
    - Set invalid channel ID (e.g., `123` without `-100` prefix)
    - Click test notification button
    - Should show clear error message
    - Verify error includes:
      - Error description
      - Format example
      - Troubleshooting checklist

## Feature 4: Agent Panel UI

### Panel Display

13. **Verify Panel Layout**
    - Send `/agent` in child bot
    - Verify sections are displayed:
      - Agent name in title
      - Financial overview with markup, balances
      - Contact information with all settings
      - Tip message at bottom
    - Verify all buttons are present:
      - 💰 Set Markup / 💸 Withdraw
      - 📞 Set Customer Service / 📢 Set Channel
      - 📣 Set Restock Group / 📖 Set Tutorial
      - 🔔 Set Notify Channel / 🔘 Manage Buttons
      - 📡 Send Test Notification
      - ❌ Close

### Settings Configuration

14. **Test Each Setting**
    - Test setting customer service (@username)
    - Test setting official channel (link or @channel)
    - Test setting restock group (link or @group)
    - Test setting tutorial link (URL)
    - Verify all are saved and displayed correctly

## Feature 5: Backward Compatibility

### Migration Testing

15. **Test Owner Migration**
    - Create agent with old `owner_user_id` field
    - As that user, send `/agent` in child bot
    - Verify access works
    - Check database - `owner_user_id` should be moved to `owners` array
    - Verify old field is removed

16. **Test Withdrawal Compatibility**
    - Create old withdrawal with `owner_user_id`
    - Approve/reject via admin
    - Verify notification is sent to correct user
    - Create new withdrawal
    - Verify it uses `requester_user_id`
    - Check both types can be processed

## Integration Tests

### End-to-End Flow

17. **Complete Agent Setup**
    - Admin: Create new agent
    - Admin: Add owners to agent
    - Owner: Claim ownership via `/agent`
    - Owner: Set all contact settings
    - Owner: Set notify channel and test
    - Owner: Set markup
    - Customer: View product in child bot
    - Verify: Price = base + markup
    - Customer: Place order
    - Verify: Profit accumulates
    - Owner: Request withdrawal
    - Admin: Review and approve
    - Verify: Notification sent correctly

18. **Multi-Language Flow**
    - Configure agent with Chinese owner
    - Verify Chinese UI in agent panel
    - Add English-speaking co-owner
    - Verify English UI shows for English user
    - Both owners should see appropriate language

## Expected Results Summary

### ✅ Pass Criteria

- Multi-owner add/remove works correctly
- Only owners can access `/agent` in child bots
- Owner claim flow works when owners empty
- Language auto-detection works correctly
- All UI text translates properly (zh/en)
- Test notification sends successfully when configured
- Clear error messages when notification fails
- All settings save and display correctly
- Backward compatibility maintained
- No syntax errors or crashes
- Security scan passes
- Code review passes

### ❌ Failure Indicators

- Non-owners can access `/agent`
- Owner management buttons don't work
- Language doesn't auto-detect
- UI shows mixed languages
- Test notification fails silently
- Settings don't save
- Migration doesn't convert owner_user_id
- Withdrawals fail for old records
- Console crashes or shows errors

## Troubleshooting

### Common Issues

**Issue: `/agent` command has no response**
- Check: Is user in owners array?
- Check: Is agent_id set in bot_data?
- Check: Are handlers registered with group=-1?

**Issue: Language doesn't change**
- Check: User lang field in database
- Check: Telegram language_code
- Clear bot session and retry

**Issue: Test notification fails**
- Check: notify_channel_id format (-1001234567890)
- Check: Bot is member of channel
- Check: Bot has send message permissions

**Issue: Owners button doesn't appear**
- Check: User is admin
- Check: Handler registered for agent_own
- Check: Button callback matches pattern

## Logging and Debugging

Enable debug logging to track:
```
Agent {agent_id} owner bound to user {user_id}
Migrated agent {agent_id} from owner_user_id to owners array
Failed to send agent notification: {error}
Removed owner {owner_id} from agent {agent_id}
```

Check logs at: `logs/bot.log` or `logs/init.log`
