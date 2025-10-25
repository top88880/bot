# Contact Links Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    User Action in Bot                        │
│  (Press "📞联系客服", "🔶使用教程", or initiate payment)      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Handler in bot.py Called                        │
│    (e.g., message handler for text == '📞联系客服')          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│          Call bot_links Helper Function                      │
│  • format_contacts_block_for_child(context, lang)            │
│  • get_tutorial_link_for_child(context)                      │
│  • get_customer_service_link(context)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         Check context.bot_data.get('agent_id')               │
└──────────┬──────────────────────────────────┬───────────────┘
           │                                  │
      agent_id                           No agent_id
      present                                 │
           │                                  │
           ▼                                  ▼
┌──────────────────────┐         ┌────────────────────────┐
│   CHILD AGENT        │         │     MAIN BOT           │
│                      │         │                        │
│ 1. Query MongoDB     │         │ 1. Read env variables  │
│    agents.find_one() │         │    os.getenv()         │
│                      │         │                        │
│ 2. Get settings:     │         │ 2. Use defaults:       │
│    - customer_service│         │    - CUSTOMER_SERVICE  │
│    - official_channel│         │    - OFFICIAL_CHANNEL  │
│    - restock_group   │         │    - RESTOCK_GROUP     │
│    - tutorial_link   │         │    - TUTORIAL_LINK     │
│    - notify_channel  │         │    - NOTIFY_CHANNEL_ID │
│                      │         │                        │
│ 3. If unset:         │         │ 3. Always has values   │
│    Return None or    │         │    from .env           │
│    "Not Set"         │         │                        │
│                      │         │                        │
│ ❌ NO FALLBACK       │         │ ✅ UNCHANGED           │
│    to main env       │         │                        │
└──────────┬───────────┘         └────────────┬───────────┘
           │                                  │
           │                                  │
           └──────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Format and Display to User                      │
│  • HTML text with contact info                               │
│  • Inline keyboard buttons with links                        │
│  • "Not Set" message if agent field unconfigured             │
└─────────────────────────────────────────────────────────────┘
```

## Key Decision Points

### When displaying contacts in child agent:
```python
if context.bot_data.get('agent_id'):
    # Agent path - STRICT
    links = get_links_from_database()
    if not links['customer_service']:
        show_not_set_message()
    else:
        show_agent_link()
else:
    # Main bot path - UNCHANGED
    link = os.getenv('CUSTOMER_SERVICE')
    show_main_bot_link()
```

### Before This Fix:
```
Child Agent User → Handler → os.getenv('CUSTOMER_SERVICE')
                           ❌ Shows main bot contact
```

### After This Fix:
```
Child Agent User → Handler → get_customer_service_for_child(context)
                          → Check agent_id
                          → Query database
                          ✅ Shows agent's own contact or "Not Set"
```

## Examples

### Example 1: Contact Support in Child Agent
```
User presses: 📞联系客服

Old behavior:
  Shows: @lwmmm (main bot's customer service)

New behavior:
  Shows: @myagent_support (agent's configured customer service)
  Or: "未设置联系方式" (if not configured)
```

### Example 2: Tutorial in Child Agent
```
User presses: 🔶使用教程

Old behavior:
  Shows: https://t.me/XCZHCS/106 (main bot's tutorial)

New behavior:
  Shows: https://t.me/myagent_tutorial (agent's tutorial)
  Or: "教程链接未设置" (if not configured)
```

### Example 3: Payment Flow
```
User initiates recharge

Old behavior:
  Text includes: "如有问题请联系客服 @lwmmm"

New behavior:
  Text includes: "如有问题请联系客服 @myagent_support"
```

## Database Structure

```json
{
  "_id": ObjectId("..."),
  "agent_id": "agent_20240101_123456",
  "name": "My Agent Bot",
  "settings": {
    "customer_service": "@myagent_support",
    "official_channel": "@myagent_channel",
    "restock_group": "https://t.me/+AbCdEfGhIjK",
    "tutorial_link": "https://t.me/myagent_tutorial",
    "notify_channel_id": -1001234567890,
    "extra_links": [
      {
        "title": "FAQ",
        "url": "https://example.com/faq"
      }
    ]
  },
  "status": "active",
  "created_at": "2024-01-01 12:34:56"
}
```

## Code Paths Updated

1. `bot.py:8988` - Contact support message handler
2. `bot.py:9031` - Tutorial message handler  
3. `bot.py:9270` - Payment method selection (callback)
4. `bot.py:9807` - Payment method selection (query)
5. `bot.py:10203` - Notice callback alert

All now use helpers from `bot_links.py` instead of direct `os.getenv()` calls.
