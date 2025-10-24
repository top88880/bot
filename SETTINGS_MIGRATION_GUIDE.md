# Agent Backend Settings Migration Guide

## Overview

This guide explains the migration from the old `links` structure to the new `settings` structure in the agent backend system. The new structure provides more flexibility and better organization of agent-specific configuration.

## What Changed

### Old Structure (Deprecated)
```python
agent = {
    'agent_id': 'agent_xxx',
    'owner_user_id': 123456,
    'markup_usdt': '0.05',  # 2 decimal places
    'profit_available_usdt': '10.50',  # 2 decimal places
    'links': {
        'support_link': '@customer_service',
        'channel_link': '@official_channel',
        'announcement_link': 'https://t.me/+xxx',
        'extra_links': [
            {'title': 'FAQ', 'url': 'https://example.com/faq'}
        ]
    }
}
```

### New Structure (Current)
```python
agent = {
    'agent_id': 'agent_xxx',
    'owner_user_id': 123456,
    'markup_usdt': '0.05000000',  # 8 decimal places
    'profit_available_usdt': '10.50000000',  # 8 decimal places
    'settings': {
        'customer_service': '@cs1 @cs2',  # Can have multiple @handles
        'official_channel': '@official_channel',
        'restock_group': 'https://t.me/+xxx',
        'tutorial_link': 'https://docs.example.com/guide',  # NEW
        'notify_channel_id': '-100123456789',  # NEW
        'extra_links': [
            {'title': 'FAQ', 'url': 'https://example.com/faq'}
        ]
    }
}
```

## Key Differences

### 1. Field Mapping
| Old Field | New Field | Notes |
|-----------|-----------|-------|
| `links.support_link` | `settings.customer_service` | Can now contain multiple @handles separated by spaces |
| `links.channel_link` | `settings.official_channel` | Renamed for clarity |
| `links.announcement_link` | `settings.restock_group` | Renamed for clarity |
| N/A | `settings.tutorial_link` | **NEW** - Must be a valid http(s):// URL |
| N/A | `settings.notify_channel_id` | **NEW** - Numeric channel ID for notifications |
| `links.extra_links` | `settings.extra_links` | Moved but format unchanged |

### 2. Precision Improvements
- **Markup and profit fields**: Now use 8 decimal places (0.00000001) instead of 2
- More accurate for fractional cent calculations
- Stored as strings to avoid floating-point errors

### 3. New Fields

#### Tutorial Link
- **Purpose**: Link to usage tutorial/documentation
- **Validation**: Must start with `http://` or `https://`
- **Example**: `https://docs.example.com/tutorial`

#### Notify Channel ID  
- **Purpose**: Numeric ID of Telegram channel for notifications
- **Validation**: Must be numeric (typically starts with -100)
- **Example**: `-100123456789`
- **How to get**: Add bot to channel, send a message, use @username_to_id_bot

## Backward Compatibility

The system maintains full backward compatibility:

### Helper Functions
All helper functions check for the new `settings` structure first, then fall back to `links`:

```python
def get_customer_service_link(context):
    agent_links = get_agent_links(context)
    # Returns customer_service if from settings, or support_link if from links
    customer_service = agent_links.get('customer_service')
    return customer_service if customer_service else default
```

### Old Agents
- Agents created before this update continue to work
- They can be migrated at any time (see Migration section)
- No immediate action required

## Migration

### Automatic Migration
Run the migration script to convert all agents:

```bash
# Dry run first (recommended)
python3 migrate_settings.py --dry-run

# Perform actual migration
python3 migrate_settings.py
```

### Manual Migration
You can also migrate individual agents via MongoDB:

```javascript
// Find agents with old structure
db.agents.find({ settings: { $exists: false } })

// Migrate single agent
db.agents.updateOne(
  { agent_id: 'agent_xxx' },
  {
    $set: {
      settings: {
        customer_service: '<old support_link value>',
        official_channel: '<old channel_link value>',
        restock_group: '<old announcement_link value>',
        tutorial_link: null,
        notify_channel_id: null,
        extra_links: [/* old extra_links */]
      },
      markup_usdt: '0.05000000',
      profit_available_usdt: '0.00000000',
      profit_frozen_usdt: '0.00000000',
      total_paid_usdt: '0.00000000',
      updated_at: new Date()
    }
  }
)
```

## Owner Claim Feature

### New Functionality
Agents can now have their owner claimed/bound by the actual agent operator:

#### When Owner is None
```
🤖 代理后台 - 未绑定

此代理机器人尚未绑定拥有者。

作为代理运营者，您需要先绑定为拥有者才能访问代理后台。

[🔐 绑定为拥有者] [❌ 取消]
```

#### When Owner is Admin
```
🤖 代理后台 - 需要重新绑定

此代理机器人当前绑定的是管理员账号。

作为实际的代理运营者，您可以一次性地将拥有者身份转移到您的账号。

⚠️ 注意：此操作只能执行一次，请确认您是该代理的实际运营者。

[🔐 绑定为拥有者] [❌ 取消]
```

### Implementation
- When `/agent` is called, check `owner_user_id`
- If `None` or in `ADMIN_IDS`, show bind button
- On bind, update `owner_user_id` to current user
- Can only be done once per agent

## UI Changes

### Agent Backend Panel

#### Old UI
```
设置客服 | 设置频道
设置公告 | 管理按钮
```

#### New UI
```
设置客服      | 设置官方频道
设置补货通知群 | 设置教程链接  
设置通知频道ID | 管理链接按钮
```

### Markup Setting

#### Old UI
```
💰 设置差价

请发送您想要设置的每件商品差价（单位：USDT）
示例: 0.05

[❌ 取消]
```

#### New UI
```
💰 设置差价

当前差价: 0.05 USDT/件

快捷选项:
• +0.01 USDT
• +0.05 USDT
• +0.10 USDT

自定义设置: 发送任意 ≥ 0 的USDT金额
示例: 0.08 或 1.5

[+0.01] [+0.05] [+0.10]
[❌ 取消]
```

## Validation Rules

### Customer Service
- Format: `@username` or URL
- Can contain multiple @handles separated by spaces
- Example: `@cs1 @cs2 @cs3`

### Official Channel
- Format: `@channel` or URL
- Example: `@myagent_channel` or `https://t.me/myagent_channel`

### Restock Group
- Format: `@group` or URL or invite link
- Example: `https://t.me/+xxxxx`

### Tutorial Link
- **Required format**: `http://` or `https://`
- **Validation**: URL must start with http(s)://
- Example: `https://docs.google.com/document/xxx`

### Notify Channel ID
- **Required format**: Numeric
- Usually starts with `-100` for channels
- **Validation**: Must contain only digits and minus sign
- Example: `-100123456789`

## Testing

### Test Owner Claim
1. Create agent with owner_user_id=None
2. Open child bot
3. Send `/agent`
4. Verify bind button appears
5. Click bind button
6. Verify owner_user_id is set

### Test Settings
1. Open agent backend with `/agent`
2. Test each setting button:
   - 设置客服: Try multiple @handles
   - 设置官方频道: Try @channel and URL
   - 设置补货通知群: Try invite link
   - 设置教程链接: Try without http:// (should fail)
   - 设置通知频道ID: Try non-numeric (should fail)

### Test Preset Markup
1. Click "💰 设置差价"
2. Verify preset buttons appear
3. Click +0.01 button
4. Verify markup set to 0.01
5. Check database: `markup_usdt` should be "0.01000000" (8 decimals)

## Troubleshooting

### Issue: Agent still showing old links structure
**Solution**: Run migration script or wait for agent to save settings via UI

### Issue: Tutorial link validation failing
**Solution**: Ensure URL starts with `http://` or `https://`

### Issue: Notify channel ID validation failing
**Solution**: Ensure ID is numeric only (e.g., `-100123456789`, no letters)

### Issue: Owner claim button not showing
**Solution**: 
1. Check if `owner_user_id` is set to a non-admin user
2. Verify user is not already the owner
3. Check if user ID is in ADMIN_IDS

### Issue: Precision loss in profit amounts
**Solution**: Ensure you're using the new 8-decimal precision format

## API Reference

### get_agent_links(context)
Returns agent settings in unified format:
```python
{
    'customer_service': str or None,
    'official_channel': str or None,
    'restock_group': str or None,
    'tutorial_link': str or None,
    'notify_channel_id': str or None,
    'extra_links': list
}
```

### get_customer_service_link(context)
Returns customer service string, falling back to default if not set.

### get_channel_link(context)
Returns official channel string, falling back to default if not set.

### get_announcement_link(context)
Returns restock group string, falling back to default if not set.

## Database Queries

### Find agents with old structure
```javascript
db.agents.find({ 
    settings: { $exists: false },
    links: { $exists: true }
})
```

### Find agents with new structure
```javascript
db.agents.find({ 
    settings: { $exists: true }
})
```

### Check precision of financial fields
```javascript
// Find fields with old precision (less than 8 decimals)
db.agents.find({
    $or: [
        { markup_usdt: { $regex: /^\d+\.\d{1,7}$/ } },
        { profit_available_usdt: { $regex: /^\d+\.\d{1,7}$/ } },
        { profit_frozen_usdt: { $regex: /^\d+\.\d{1,7}$/ } },
        { total_paid_usdt: { $regex: /^\d+\.\d{1,7}$/ } }
    ]
})
```

### Find unclaimed agents
```javascript
db.agents.find({
    $or: [
        { owner_user_id: null },
        { owner_user_id: { $in: [/* ADMIN_IDS */] } }
    ]
})
```

## Support

For issues or questions:
1. Check this guide
2. Review AGENT_BACKEND_QUICK_REF.md
3. Check logs for error messages
4. Verify MongoDB data structure

---

**Version**: 1.0  
**Last Updated**: 2024-10-24  
**Status**: ✅ Production Ready
