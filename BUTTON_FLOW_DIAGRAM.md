# Agent Management - Button Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ADMIN PANEL                                  │
│                                                                     │
│  [用户列表] [用户私发] [设置充值地址] [商品管理]                      │
│  [修改欢迎语] [设置菜单按钮] [收益说明] [收入统计]                    │
│  [导出用户列表] [导出下单记录] [管理员管理] [代理管理] ◄──┐         │
│  [销售统计] [库存预警] [数据导出] [多语言管理]              │         │
│  [关闭面板]                                                   │         │
└────────────────────────────────────────────────────────────┼─────────┘
                                                             │
                                                             │ Click
                                                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   AGENT MANAGEMENT PANEL                            │
│                                                                     │
│  🤖 代理管理                                                         │
│                                                                     │
│  📊 代理总数: 3                                                      │
│  🟢 运行中: 2                                                        │
│  🔴 已停止: 1                                                        │
│                                                                     │
│  ━━━━━━━━━━━━━━━                                                    │
│                                                                     │
│  1. 🟢 零售代理                                                      │
│     📋 ID: agent001                                                 │
│     📍 状态: 运行中                                                  │
│                                                                     │
│  2. 🟢 批发代理                                                      │
│     📋 ID: agent002                                                 │
│     📍 状态: 运行中                                                  │
│                                                                     │
│  3. 🔴 区域代理                                                      │
│     📋 ID: agent003                                                 │
│     📍 状态: 已停止                                                  │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐                       │
│  │ ➕ 新增代理        │  │ 🔄 刷新列表        │                       │
│  │ agent_new        │  │ agent_refresh    │                       │
│  └────────┬─────────┘  └────────┬─────────┘                       │
│           │                      │                                 │
│           │                      └─────────────┐                   │
│           │                                    │ Refresh           │
│  ┌────────┴────────┐  ┌──────────────────┐   │ (reloads          │
│  │ ⏸ 停止 零售      │  │ 🗑 删除            │   │  panel)           │
│  │ agent_tgl ag001 │  │ agent_del ag001  │   │                   │
│  └────────┬────────┘  └────────┬─────────┘   │                   │
│           │                     │              │                   │
│  ┌────────┴────────┐  ┌────────┴─────────┐   │                   │
│  │ ⏸ 停止 批发      │  │ 🗑 删除            │   │                   │
│  │ agent_tgl ag002 │  │ agent_del ag002  │   │                   │
│  └────────┬────────┘  └────────┬─────────┘   │                   │
│           │                     │              │                   │
│  ┌────────┴────────┐  ┌────────┴─────────┐   │                   │
│  │ ▶️ 启动 区域      │  │ 🗑 删除            │   │                   │
│  │ agent_tgl ag003 │  │ agent_del ag003  │   │                   │
│  └────────┬────────┘  └────────┬─────────┘   │                   │
│           │                     │              │                   │
│  ┌────────┴─────────────────────┘             │                   │
│  │                                             │                   │
│  │  Toggle/Delete Actions:                    │                   │
│  │  • Show alert with result                  │                   │
│  │  • Refresh panel automatically ────────────┘                   │
│  │                                                                 │
│  └─────────────────────────────────────────────────────────────┐  │
│                                                                  │  │
│  [🔙 返回控制台]                                                  │  │
│   backstart                                                      │  │
└──────────────────────────────────────────────────────────────────┼──┘
                                                                   │
                                                                   └──► Back to Admin Panel


NEW AGENT CREATION FLOW (agent_new):
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────┐
│  Click: ➕ 新增代理                                                  │
└────────────────────────────────────────────────────────┬────────────┘
                                                         │
                                                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   STEP 1 - TOKEN INPUT                              │
│                                                                     │
│  🤖 创建新代理 - 步骤 1/2                                            │
│                                                                     │
│  📝 请发送代理Bot的Token                                             │
│                                                                     │
│  如何获取Token：                                                     │
│  1. 打开 @BotFather                                                 │
│  2. 发送 /newbot 创建新Bot                                          │
│  3. 按提示设置Bot名称和用户名                                         │
│  4. 复制收到的Token并发送到这里                                       │
│                                                                     │
│  Token格式示例：1234567890:ABCdefGHIjklMNOpqrsTUVwxyz             │
│                                                                     │
│  [🚫 取消]                                                          │
│   agent_manage                                                     │
└────────────────────────────────────────────────┬────────────────────┘
                                                 │
                                                 │ User sends token
                                                 ▼
                                        ┌──────────────────┐
                                        │ Validate Token   │
                                        │ • Length >= 30   │
                                        │ • Contains ':'   │
                                        └────┬─────────────┘
                                             │
                           ┌─────────────────┼─────────────────┐
                           │ Invalid         │ Valid           │
                           ▼                 ▼                 │
                    ┌──────────────┐  ┌──────────────────┐   │
                    │ Error Message│  │ Store in context │   │
                    │ • Format     │  │ • Show next step │   │
                    │   example    │  └────────┬─────────┘   │
                    │ • Try again  │           │              │
                    └──────────────┘           ▼              │
                                                               │
┌──────────────────────────────────────────────────────────────┼─────┐
│                   STEP 2 - NAME INPUT                        │     │
│                                                              │     │
│  ✅ Token已接收！                                            │     │
│                                                              │     │
│  🤖 创建新代理 - 步骤 2/2                                     │     │
│                                                              │     │
│  📝 请输入代理的显示名称:                                     │     │
│                                                              │     │
│  例如: 零售代理、批发代理、区域A代理等                         │     │
│  名称长度: 1-50字符                                          │     │
│                                                              │     │
│  [🚫 取消]                                                   │     │
│   agent_manage                                              │     │
└──────────────────────────────────────────────┬───────────────┼─────┘
                                               │               │
                                               │ User sends    │
                                               │ name          │
                                               ▼               │
                                      ┌──────────────────┐    │
                                      │ Validate Name    │    │
                                      │ • Length 1-50    │    │
                                      └────┬─────────────┘    │
                                           │                  │
                         ┌─────────────────┼──────────────┐  │
                         │ Invalid         │ Valid        │  │
                         ▼                 ▼              │  │
                  ┌──────────────┐  ┌──────────────────┐ │  │
                  │ Error Message│  │ Show Processing  │ │  │
                  │ • Length info│  └────────┬─────────┘ │  │
                  │ • Try again  │           │           │  │
                  └──────────────┘           ▼           │  │
                                                          │  │
┌─────────────────────────────────────────────────────────┼──┼──┐
│                   PROCESSING                            │  │  │
│                                                          │  │  │
│  ⏳ 正在创建代理...                                       │  │  │
│                                                          │  │  │
│  1. 保存配置 ✅                                          │  │  │
│  2. 验证Token ⏳                                         │  │  │
│  3. 启动Bot ⏳                                           │  │  │
│                                                          │  │  │
│  请稍候...                                               │  │  │
└──────────────────────────────────────────────┬───────────┼──┼──┘
                                               │           │  │
                                               ▼           │  │
                                      ┌──────────────────┐ │  │
                                      │ Save Agent       │ │  │
                                      │ Start Agent Bot  │ │  │
                                      └────┬─────────────┘ │  │
                                           │               │  │
                         ┌─────────────────┼───────────┐  │  │
                         │ Success         │ Failure   │  │  │
                         ▼                 ▼           │  │  │
┌────────────────────────────────┐  ┌─────────────────┐  │  │  │
│        SUCCESS                 │  │      FAILURE    │  │  │  │
│                                │  │                 │  │  │  │
│  ✅ 代理创建成功！              │  │  ⚠️ 代理已保存， │  │  │  │
│                                │  │     但启动失败   │  │  │  │
│  📋 代理ID: agent_xxx          │  │                 │  │  │  │
│  🤖 名称: 零售代理              │  │  可能原因：      │  │  │  │
│  🟢 状态: 运行中                │  │  • Token无效    │  │  │  │
│                                │  │  • Bot未访问    │  │  │  │
│  代理Bot已成功启动              │  │  • 网络问题     │  │  │  │
│                                │  │                 │  │  │  │
│  [🤖 返回代理管理]              │  │  [🤖 返回代理   │  │  │  │
│   agent_manage                 │  │    管理]        │  │  │  │
└────────────────────────────────┘  │   agent_manage  │  │  │  │
                                    └─────────────────┘  │  │  │
                                                         │  │  │
                                    All return to ───────┘  │  │
                                    Agent Management Panel  │  │
                                                            │  │
════════════════════════════════════════════════════════════┘  │
                                                               │
CALLBACK DATA SUMMARY:                                         │
══════════════════════                                         │
                                                               │
Main Actions:                                                  │
• agent_manage (12 bytes) ─────────────────────────────────────┘
• agent_refresh (13 bytes)
• agent_new (9 bytes)

Per-Agent Actions:
• agent_tgl <agent_id> (~31 bytes)
• agent_del <agent_id> (~31 bytes)

Navigation:
• backstart (return to admin panel)

All callback_data < 64 bytes ✅


ERROR HANDLING:
═══════════════

Every operation includes:
┌────────────────────────────────────┐
│ Try-Catch Block                    │
│ ├─ Operation code                  │
│ ├─ Error logging with stack trace  │
│ └─ User-friendly error message     │
└────────────────────────────────────┘

Examples:
• Token validation fails → Show format example
• Name too long → Show current vs required length
• Agent start fails → Show possible causes + solutions
• MongoDB error → Fallback to JSON storage
• Network timeout → Suggest retry


USER FEEDBACK:
══════════════

All operations provide immediate feedback:
• Success: Alert + Panel refresh
• Failure: Alert with explanation
• Progress: Step indicators (1/2, 2/2)
• Status: Icons (🟢 🔴 🟡)
```

## Button Response Flow

```
User Click → Telegram API → Bot Handler → Validation → Operation → Feedback
                                │               │           │
                                │               │           └─► Alert/Edit Message
                                │               └─► Check Permissions
                                └─► Pattern Match (^agent_xxx)
```

## State Management

```
Agent Creation State:
1. sign = 0 (idle)
2. sign = 'agent_add_token' (waiting for token)
3. sign = 'agent_add_name' (waiting for name)
4. sign = 0 (complete)

Context Storage:
• context.user_data['agent_token'] - Temporary token storage
• Cleared after completion or cancel
```

## Integration Points

```
bot.py
├─ textkeyboard()
│  ├─ sign == 'agent_add_token' ─► Validate and store token
│  └─ sign == 'agent_add_name' ─► Create agent with stored token
│
└─ show_admin_panel()
   └─ Button: callback_data='agent_manage'

bot_integration.py
├─ integrate_agent_system()
│  ├─ Register: agent_manage
│  ├─ Register: agent_refresh
│  ├─ Register: agent_new
│  ├─ Register: agent_tgl
│  ├─ Register: agent_del
│  └─ Register: Legacy handlers
│
└─ Handler Functions
   ├─ agent_manage() ─► Show panel
   ├─ agent_refresh() ─► Refresh panel
   ├─ agent_new() ─► Start creation
   ├─ agent_tgl() ─► Toggle agent
   └─ agent_del() ─► Delete agent
```

---

**All paths lead to successful completion or clear error messages!**
