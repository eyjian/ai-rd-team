## Why

当前 `CodeBuddyToolBridge`（文件模式 C）要求**主 Agent 必须在线**持续轮询 `runtime/adapter-intents/` 并手动应答，这是阻塞 ai-rd-team E2E "无人值守"的核心痛点。2026-05-04 的 blog-api Standard 档真实 E2E 暴露出：

- `_version` / `_probe` 两个不需要 CodeBuddy 工具的 intent 卡在 initialize 阶段 ~90 秒，用户一度以为 driver 卡死
- `shutdown_request` × 3（stop_run 阶段）是纯礼节性通知，但目前必须占用主 Agent 一次 `send_message` 工具调用
- 整个 10 分钟 wait 阶段 bridge intent 数量是 0（成员间 P2P 不走 bridge），说明**阻塞点集中在 initialize + stop 两段短时间窗口**

M5 第一件事就解决这个：**把不需要真实 CodeBuddy 工具能力的 intent 自动化应答，同时从源头减少这类 intent 的数量**，让手动应答压缩到只剩真正需要工具的 spawn/send 操作。

## What Changes

- **F 优化（Adapter 源头减量）**：`CodeBuddyAdapter.initialize()` 不再通过 bridge 发 `_version` / `_probe` intent；直接用代码侧默认值（`version="claude-opus-4.7"`、`probe_tools={team_create, team_delete, task, send_message}`），并支持通过 `EffectiveConfig.adapter` 覆盖。
- **D Daemon（新能力 `adapter-bridge-auto-responder`）**：引入 `AutoBridgeResponder` 组件，在 `TeamEnvironmentManager.initialize()` 里以后台线程形式启动，自动应答以下 intent：
  - `_version` / `_probe`（兜底；若有人直写 intent 走老路径也能接）
  - `send_message type=shutdown_request`（回 `{ok: true}`，不真调工具）
  - `send_message type=broadcast` 在 Standard 档下（已被 role 约束禁用；若意外产生则自动回 `{ok: true}` 并记录 warning 事件）
  - 遇到 `team_create` / `task` / `send_message type=message` / `team_delete` 等需要真工具能力的 intent，**不应答**，继续留给主 Agent 手动处理
- **Web 面板 UX（在 `04-web-panel.md` 所述总览/团队页基础上）**：加一个 "Pending bridge intents" 区块，只展示需要主 Agent 处理的 intent（auto-responder 已消化的不显示），每条带 `op` / 关键参数摘要 / 等待时长，让用户清楚"我现在需要做什么"。
- **配置开关**：`adapter.auto_bridge: true/false`（默认 true），用户可关闭走老行为。
- **观测**：auto-responder 应答时写 `events.jsonl` 事件 `bridge_auto_responded`，含 `op` / `intent_id` / `decision`，方便调试。

## Capabilities

### New Capabilities

- `adapter-bridge-auto-responder`：在 file-based bridge 协议之上，新增一个后台自动应答组件，负责识别并处理"不需要主 Agent 工具能力"的 intent，降低 E2E 手动干预次数。

### Modified Capabilities

（本次不修改既有 capability 的 requirement，仅在 `openspec/specs/design/02-adapter.md` / `11-runtime-protocol.md` 上做补充文档更新，不属于 spec delta 层。）

## 非目标

- ❌ 不实现自动调 CodeBuddy 真工具（`team_create` / `task` / `send_message type=message` / `team_delete` 仍由主 Agent 手动应答）
- ❌ 不引入 CodeBuddy CLI 子进程 / REST API / IDE 扩展三种"真工具获取路径"（原方案 A/B/C 均排除，见 brainstorming 讨论）
- ❌ 不改 `CodeBuddyToolBridge` 的文件协议、目录结构或 JSON Schema；auto-responder 完全在 bridge 协议之上，向后兼容
- ❌ 不改 `BridgeSimulator`（纯模拟器，E2E 测试用，与本 change 无关）
- ❌ 不解决 `developer_2.yaml` state 延迟更新的问题（属于观测/state 范畴，留给 M5 后续）
- ❌ 不处理 Trae/Qoder 适配（单独立 change，独立里程碑）
- ❌ 不做 RP → 真实 token/USD 成本校准（独立 change）

## Impact

### 代码
- `src/ai_rd_team/adapter/codebuddy.py`：`initialize()` 去掉 `_version` / `_probe` 的 bridge 调用，改本地默认
- `src/ai_rd_team/adapter/bridge.py`：`FileBasedBridge` 不变（auto-responder 作为独立模块写 result 即可）
- `src/ai_rd_team/adapter/auto_responder.py`：新文件，~150 行，实现 `AutoBridgeResponder` + 后台轮询线程 + op 白名单
- `src/ai_rd_team/engine/manager.py`：`initialize()` 启动 `AutoBridgeResponder`；`stop_run` 后关闭
- `src/ai_rd_team/config/models.py`：`AdapterConfig` 增加 `auto_bridge: bool = True` 字段
- `src/ai_rd_team/service/readers.py`：新增 `/api/bridge/pending-intents` 端点（返回当前未被 auto 应答的 intent 列表）
- `src/ai_rd_team/service/web/index.html`：总览页加 "Pending bridge intents" 区块

### 文档
- `openspec/specs/design/02-adapter.md`：§5.2 之后追加 §5.6 AutoBridgeResponder 小节
- `openspec/specs/design/11-runtime-protocol.md`：events.jsonl 事件清单加 `bridge_auto_responded`
- `openspec/specs/design/ROADMAP.md`：追加 "M5：降低 bridge 负担" 条目
- `docs/`：更新 E2E 使用指引，说明"`_version`/`_probe`/shutdown 已自动"，用户只需应答 5 类真工具 intent
- `CHANGELOG.md`：在 `[Unreleased]` 节记录变更

### 测试
- `tests/adapter/test_auto_responder.py`：新文件，覆盖 6 类 op 决策表 + 超时 + 并发
- `tests/adapter/test_codebuddy_adapter.py`：补一个 `initialize_no_bridge_calls_when_probe_local` 回归用例
- `tests/service/test_readers_bridge_pending.py`：新端点契约测试

### 向后兼容
- `adapter.auto_bridge=false` 时完全走老路径（手动应答 11 次）
- file-bridge 的 JSON Schema / 目录结构 / op 协议全部不变
- `BridgeSimulator` 不受影响（其独立应答所有 op，不依赖 AutoBridgeResponder）

### 成本预估
- 工作量：~2 天（F 优化 0.5d + AutoBridgeResponder 1d + Web 面板 UX 0.5d）
- 按本次实际 E2E 体验，预计 M5 完成后一次 blog-api Standard 档 E2E 的主 Agent 手动应答次数从 **11 次** 降到 **5-6 次**，且全部集中在 30 秒内的 spawn 窗口。
