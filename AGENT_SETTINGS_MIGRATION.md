# Agent Contact Settings Centralization - Migration Guide

## Overview
This migration centralizes all agent contact/notification endpoint management to the main bot's admin console. Child agents now display contacts in read-only mode and are restricted to non-sensitive data views only.

## What Changed

### 1. Main Bot Admin Panel
- **New Feature**: Admin panel for managing per-agent contact settings
- **Location**: Admin → 代理管理 → [Select Agent] → 🛠 代理联系方式设置
- **Managed Fields**:
  - `customer_service` - Customer service contacts (supports multiple @handles)
  - `official_channel` - Official channel (@channel or https link)
  - `restock_group` - Restock notification group (@group or invite link)
  - `tutorial_link` - Tutorial link (http(s):// URL)
  - `notify_channel_id` - Notification channel ID (-100xxxxxxxxxx or @channel)
  - `notify_group_id` - Notification group ID (-100xxxxxxxxxx or @group)

### 2. Child Agent Changes
- **Read-Only Contacts**: Child agents display all contact settings but cannot edit them
- **Removed Features**: All `agent_cfg_*` contact editing handlers are now deprecated
- **Security Enhancement**: Order and recharge views now redact sensitive customer data
- **Preserved Features**:
  - Markup settings
  - Withdrawal management
  - Analytics (经营报告)
  - Custom link buttons management

### 3. Data Security
- **New Module**: `services/security.py` with `redact_order_payload()` function
- **Redacted Fields**: credentials, files, passwords, secrets, deliverables, sessions, JSON, tokens, keys
- **Preserved Fields**: product_name, quantity, unit_price, subtotal, timestamps

### 4. Notifications
- **No Breaking Changes**: Existing notification flows continue to work unchanged
- **Settings Location**: Notifications use `agents.settings.notify_channel_id` and `notify_group_id`
- **Future Enhancement**: Extension point for `message_thread_id` (topic groups) documented but not implemented

## Database Schema

### Before (agent document)
```javascript
{
  agent_id: "agent001",
  name: "My Agent",
  // ... other fields
}
```

### After (agent document with settings)
```javascript
{
  agent_id: "agent001",
  name: "My Agent",
  settings: {
    customer_service: "@customer1 @customer2",
    official_channel: "@mychannel",
    restock_group: "https://t.me/+invite123",
    tutorial_link: "https://example.com/tutorial",
    notify_channel_id: "-1001234567890",  // or "@mychannel"
    notify_group_id: "-1234567890",       // or "@mygroup"
    extra_links: [/* custom buttons */]
  },
  // ... other fields
}
```

## Migration Steps

### Automatic Migration (No Action Required)
The system automatically migrates existing data when:
1. Admin accesses the new settings panel - settings are created on first save
2. Child agent displays contacts - reads from `settings` object
3. Notifications are sent - uses `settings.notify_channel_id` or `settings.notify_group_id`

### Manual Steps (Optional)
If you have existing contact data in legacy fields, you can:
1. Review existing agent configurations
2. Use the admin panel to set/update contact settings
3. Verify child agents display the correct read-only information

## Testing Checklist

### Main Bot Admin
- [ ] Access Admin → 代理管理 → [Select Agent] → 🛠 代理联系方式设置
- [ ] Set customer service (single or multiple @handles)
- [ ] Set official channel (@channel or https link)
- [ ] Set restock group (@group or invite link)
- [ ] Set tutorial link (must be http(s)://)
- [ ] Set notify channel ID (-100xxxxxxxxxx or @channel)
- [ ] Set notify group ID (-100xxxxxxxxxx or @group)
- [ ] Verify "清除" command clears settings
- [ ] Verify validation errors for invalid inputs

### Child Agent Bot
- [ ] Run `/agent` command
- [ ] Verify all contact fields are displayed as read-only
- [ ] Verify "设置客服" and similar buttons are removed
- [ ] Verify markup and withdrawal buttons still work
- [ ] Verify "管理链接按钮" still works for custom buttons
- [ ] Attempt to click deprecated `agent_cfg_*` buttons (should show warning)

### Notifications
- [ ] Trigger auto-credit recharge for agent
- [ ] Verify notification sent to agent's notify_channel_id or notify_group_id
- [ ] Trigger order fulfillment
- [ ] Verify notification sent correctly
- [ ] Verify main bot notifications unchanged

### Data Security
- [ ] In child agent, view order list
- [ ] Verify no sensitive fields (credentials, files, etc.) are visible
- [ ] Verify only metadata (product, price, qty) is shown
- [ ] Attempt file download (should be blocked with permission message)

## Code Changes Summary

### New Files
- `services/security.py` - Security utilities for data redaction

### Modified Files
- `admin/agents_admin.py` - Added agent settings management handlers
- `handlers/agent_backend.py` - Made child agents read-only for contacts
- `bot.py` - Registered new admin handlers
- `bot_links.py` - Added notify_group_id support

### Key Functions
- `admin_setting_text_input()` - Handles admin text input for setting fields
- `agent_settings_callback()` - Displays agent settings panel
- `redact_order_payload()` - Redacts sensitive data from orders
- `get_notify_group_id_for_child()` - Gets notify group ID for agents

## Backwards Compatibility

### Deprecated (Still Functional)
- `agent_cfg_cs_callback()` - Now shows warning message
- `agent_cfg_official_callback()` - Now shows warning message
- `agent_cfg_restock_callback()` - Now shows warning message
- `agent_cfg_tutorial_callback()` - Now shows warning message
- `agent_cfg_notify_callback()` - Now shows warning message

### Preserved
- All notification mechanisms
- Markup and withdrawal features
- Analytics and reporting
- Custom link buttons

## Future Enhancements
1. **Topic Groups Support**: Add `message_thread_id` parameter for sending notifications to specific topics in groups
2. **Batch Settings**: Allow admins to apply settings to multiple agents at once
3. **Settings Templates**: Create reusable templates for common configurations
4. **Audit Log**: Track who changed what settings and when

## Support
For issues or questions:
1. Check logs for error messages
2. Verify MongoDB connection and agent document structure
3. Ensure bot tokens are valid and bots are added to channels/groups
4. Test with @username_to_id_bot to get correct channel/group IDs

## Rollback Plan
If you need to rollback:
1. Revert to previous commit
2. Child agents will regain contact editing capability
3. Admin panel changes will be removed
4. Existing data in `settings` object remains intact and can be manually migrated back if needed
