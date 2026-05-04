# 06. Bridge 与 Auto-Responder（M5+）

> 关联设计：`openspec/specs/design/02-adapter.md §5.2 / §5.2.1`
> 关联 spec：`openspec/specs/adapter-bridge-auto-responder/spec.md`

## 背景：为什么 E2E 要主 Agent 在线？

ai-rd-team 的 CodeBuddy 适配层使用"文件 bridge（模式 C）"：

```
Python 引擎                        CodeBuddy 主 Agent（你）
    │                                       │
    │ 写 runtime/adapter-intents/*.json     │
    │──────────────────────────────────────▶│
    │                                       │ 读 intent → 按 op 调工具
    │                                       │（team_create / task / send_message / team_delete）
    │ 读 runtime/adapter-results/*.json     │
    │◀──────────────────────────────────────│ 写 result
```

M4 时代的 E2E 里，一次 Standard 档 blog-api 运行需要你手动应答约 **11 次** intent（详见 `prototype/M4-example2-e2e/VERIFIED.md`）。

## M5 做了什么

M5（change: `reduce-bridge-burden`）把**不需要真实 CodeBuddy 工具能力的 intent** 自动化了：

| intent 类型 | M4 | M5 | 说明 |
|------|------|------|------|
| `_version` | 主 Agent 手动 | ✅ 代码侧本地常量 | 不再发 intent |
| `_probe` | 主 Agent 手动 | ✅ 代码侧本地常量 | 不再发 intent |
| `send_message type=shutdown_request` | 主 Agent 手动 | ✅ AutoBridgeResponder 自动 | 礼节性通知，回 `{ok:true}` |
| `send_message type=shutdown_response` | 主 Agent 手动 | ✅ AutoBridgeResponder 自动 | 同上 |
| `send_message type=broadcast` | 主 Agent 手动 | ✅ AutoBridgeResponder 自动 + warning | Standard 档本来禁用 |
| `team_create` | 主 Agent 手动 | ⚠️ **仍需你手动** | 需要真工具 |
| `task`（spawn 成员） | 主 Agent 手动 | ⚠️ **仍需你手动** | 需要真工具 |
| `send_message type=message` | 主 Agent 手动 | ⚠️ **仍需你手动** | 需要真工具 |
| `team_delete` | 主 Agent 手动 | ⚠️ **仍需你手动** | 需要真工具 |

实际效果：blog-api E2E 手动应答从 11 次降到约 6 次，且全部集中在 **spawn 阶段**（30 秒内连续到达），initialize 和 stop 阶段基本无干预。

## 你现在只需要应答这几类 intent

启动 E2E 时，关注 Web 面板总览页的 **Pending bridge intents** 卡片（M5 新增）：

- 卡片空态显示 "✅ 无需干预" → 不用做任何事
- 卡片显示任何 pending 项 → 按 hint 文案调用对应工具

具体清单（M5 后保留给你手动处理的）：

```
{ "team_create", "task", "send_message type=message", "team_delete" }
```

## 配置

所有配置写在 `.ai-rd-team/config.advanced.yaml`：

```yaml
config_version: "1.0"

adapter:
  # M5 新增：后台自动应答（默认 true）
  auto_bridge: true

  # M5 新增：覆盖本地默认常量（调试/升级场景）
  version_override: null              # 例如 "claude-opus-4.8"，null 用内置
  available_tools_override: null      # 例如 ["team_create","team_delete","task","send_message","custom"]

  # 已有字段
  bridge_timeout_seconds: 60          # intent→result 等待超时
```

## 回退：`auto_bridge: false`

如果遇到 AutoBridgeResponder 引发的兼容问题（例如竞态、意外应答），一行配置回退：

```yaml
adapter:
  auto_bridge: false
```

此时等价于 M4 行为——所有 intent 都需要你手动应答。

## 观测

- `.ai-rd-team/runtime/events.jsonl` 新增事件 `bridge_auto_responded`，含 `intent_id` / `op` / `decision` / `type?`
- `engine.log` 记录 `AutoBridgeResponder started/stopped` 与最终 stats（`responded=..., skipped=...`）
- Web 总览页"最近事件"区块可实时看到 auto-responded 事件

## 常见问题

### Q：auto-responder 会不会帮我回 `send_message type=message`？

**不会**。`type=message` 是团队通信的主体消息，内容重要，必须你来调真 `send_message` 工具。AutoBridgeResponder 的决策表明确把这种 intent 留给主 Agent。

### Q：如果我同时在调工具、auto-responder 也要应答同一个 intent，会冲突吗？

**不会**。AutoBridgeResponder 写 result 前先检查文件是否存在，已存在则跳过。写入是原子操作（`atomic_write`：临时文件 + rename）。实测场景下 auto-responder 只应答自己"管辖"的 op 类型，跟主 Agent 不抢。

### Q：我怎么确认 auto-responder 真的在跑？

1. 启动后看 log："AutoBridgeResponder enabled (adapter.auto_bridge=true)"
2. 跑一次 run，`.ai-rd-team/runtime/events.jsonl` 会有 `bridge_auto_responded` 事件
3. `engine.stop_run()` 后 log 输出 "AutoBridgeResponder stats at stop: {'responded': {...}, 'skipped': {...}}"

### Q：GLM-5.1 等其它模型也能用吗？

可以——AutoBridgeResponder 是纯 Python 组件，不依赖具体 LLM；它降低的是**主 Agent 需要轮询 + 调工具的次数**，这个价值对所有能调 CodeBuddy 工具的模型都有效。但首次切换模型时建议按 `openspec/changes/reduce-bridge-burden/tasks.md §6.4-6.5` 做一次基线对比验证。
