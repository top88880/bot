# Agent Links Implementation

## Overview

This document describes the implementation of per-agent contact links in the multi-tenant bot architecture. Child agents can now configure their own contact information independently from the main bot.

## Changes Made

### 1. New Helper Module: `bot_links.py`

Created a centralized module with helper functions to retrieve and format contact links:

- **`get_links_for_child_agent(context)`**: Gets all contact links for a child agent from database settings
- **`format_contacts_block_for_child(context, lang)`**: Formats contact information as HTML text
- **`build_contact_buttons_for_child(context, lang)`**: Builds inline keyboard buttons for contact links
- **`get_notify_channel_id_for_child(context)`**: Gets the notification channel ID for sending stock updates
- **`get_customer_service_for_child(context)`**: Gets customer service link
- **`get_tutorial_link_for_child(context)`**: Gets tutorial/help link

**Key Behavior:**
- For child agents (when `context.bot_data` has `agent_id`): Returns per-agent settings from database
- For main bot: Returns environment variable values
- Child agents **never** fall back to main bot env variables - unset fields show as "Not Set" or are hidden

### 2. Updated `bot.py`

Modified all user-facing contact displays to use the new helper functions:

#### Contact Support Handler (`📞联系客服`)
- **Before**: Mixed agent links with hardcoded `os.getenv('RESTOCK_GROUP')`
- **After**: Uses `format_contacts_block_for_child()` to show only configured agent links

#### Tutorial Handler (`🔶使用教程`)
- **Before**: Hardcoded `os.getenv('TUTORIAL_LINK')`
- **After**: Uses `get_tutorial_link_for_child()` and shows "not configured" if unset in agent

#### Payment/Recharge Handlers
- **Before**: Hardcoded `os.getenv('CUSTOMER_SERVICE')` in multiple places
- **After**: Uses `get_customer_service_link(context)` (existing function, but now consistently used)

#### Product Notice Callbacks
- **Before**: Hardcoded `os.getenv('CUSTOMER_SERVICE')`
- **After**: Uses `get_customer_service_link(context)`

### 3. Notification System

#### Test Notification (Agent Backend)
The agent backend already had a `send_agent_notification()` function that correctly uses the agent's `notify_channel_id` setting. The test notification button in the agent console uses this function and provides clear error messages if:
- Channel ID is not configured
- Bot is not added to the channel
- Bot lacks permission to send messages

#### Stock Notifications
**Current Implementation:** The main `StockNotificationManager` in `mongo.py` continues to use the main bot's `NOTIFY_CHANNEL_ID` from environment variables. This is because:
1. Stock uploads are typically done through the main bot admin interface
2. The notification manager is a singleton without access to CallbackContext
3. Refactoring it to be context-aware would require significant changes throughout the codebase

**Future Enhancement:** If per-agent stock notifications are needed, the `shangchuanhaobao()` function and notification scheduler would need to be refactored to accept and pass through a context parameter or agent_id.

## Agent Settings Structure

Agent contact settings are stored in the `agents` collection:

```json
{
  "agent_id": "agent_20240101_123456",
  "settings": {
    "customer_service": "@myagent_support",
    "official_channel": "@myagent_channel",
    "restock_group": "https://t.me/myagent_restock",
    "tutorial_link": "https://t.me/myagent_tutorial",
    "notify_channel_id": -1001234567890,
    "extra_links": [
      {
        "title": "FAQ",
        "url": "https://example.com/faq"
      }
    ]
  }
}
```

## Testing Recommendations

1. **As agent owner**: Set all contact fields in agent console
2. **Verify**: Check that all user-facing screens show agent's own links
3. **Test changes**: Modify a setting and verify immediate effect (no restart needed)
4. **Test unset fields**: Leave some fields empty and verify they show as "Not Set" or are hidden
5. **Test notifications**: Use the "Send Test Notification" button in agent console to verify channel configuration

## Backward Compatibility

- **Main bot**: No changes in behavior - continues to use environment variables
- **Existing agent bots**: If settings are not configured, fields show as unset (no fallback to main bot)
- **Existing helper functions**: Functions like `get_customer_service_link()` and `get_channel_link()` in bot.py already implement agent-aware logic and continue to work. The new `bot_links.py` module provides additional formatting and unified access patterns.

## Out of Scope

- Global DB defaults (mentioned in requirements but not implemented in current schema)
- Per-agent stock notification sending (requires significant refactoring)
- Changes to agent settings UI (already implemented in agent console)
- New DB schema migrations (using existing `agents.settings` structure)
