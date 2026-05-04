# Spec: adapter-bridge-auto-responder

> Capability：降低 CodeBuddy file-based bridge 协议下主 Agent 的手动应答负担。
> 关联变更：`openspec/changes/reduce-bridge-burden/`
> 关联设计：`openspec/specs/design/02-adapter.md §5.2`、`openspec/specs/design/04-web-panel.md`、`openspec/specs/design/11-runtime-protocol.md §8.3`

## ADDED Requirements

### Requirement: CodeBuddyAdapter 初始化不得依赖 file bridge 的 `_version` / `_probe` 往返

`CodeBuddyAdapter.initialize()` 在默认配置下 SHALL NOT 通过 `CodeBuddyToolBridge` 发起任何 `_version` 或 `_probe` 意图，也 MUST NOT 因此而阻塞等待主 Agent 应答。

#### Scenario: 默认配置下 initialize 不产生 bridge intent

- **WHEN** `TeamEnvironmentManager.initialize()` 构造 `CodeBuddyAdapter` 且 `config.adapter` 未设置 `version_override` / `available_tools_override` / `auto_bridge=false`
- **THEN** `runtime/adapter-intents/` 在 initialize 结束时 SHALL 为空，且 `adapter.version_info.version` 等于内置常量 `DEFAULT_CODEBUDDY_VERSION`

#### Scenario: 用户可通过配置覆盖 version 和可用工具集合

- **WHEN** `config.adapter.version_override = "my-custom-version"` 且 `config.adapter.available_tools_override = ["team_create", "team_delete", "task", "send_message", "custom_tool"]`
- **THEN** `adapter.version_info.version` 等于 `"my-custom-version"` 且 `adapter.capabilities.supported_tools` 包含 `custom_tool`

#### Scenario: 内置可用工具缺失必要项时拒绝初始化

- **WHEN** `config.adapter.available_tools_override = ["team_create"]`（缺少 `team_delete` / `task` / `send_message` 中任一）
- **THEN** `CodeBuddyAdapter.initialize()` SHALL 抛 `AdapterInitError` 且异常信息 MUST 包含缺失工具名列表

### Requirement: AutoBridgeResponder 自动应答无需真工具能力的 intent

引擎 SHALL 提供一个名为 `AutoBridgeResponder` 的组件，以后台线程形式随 `TeamEnvironmentManager.initialize()` 启动（当 adapter 为 CodeBuddy 且 `config.adapter.auto_bridge` 为 true 或未设置时），负责轮询 `runtime/adapter-intents/*.json` 并自动应答下列 op：

- `op = "_version"`：回 `{"data": {"version": DEFAULT_CODEBUDDY_VERSION}}`（兜底用，正常路径已由 F 规避）
- `op = "_probe"`：回 `{"data": {"available_tools": sorted(DEFAULT_AVAILABLE_TOOLS)}}`
- `op = "send_message"` 且 `type ∈ {"shutdown_request", "shutdown_response", "broadcast"}`：回 `{"data": {"ok": true}}`
- 其它 op 或 `type = "message"` / `"plan_approval_response"`：MUST NOT 应答（保持 intent 文件原样，留给主 Agent）

#### Scenario: shutdown_request 被自动应答

- **WHEN** 引擎在 `stop_run` 阶段向 `runtime/adapter-intents/` 写入 `{"op": "send_message", "type": "shutdown_request", "recipient": "architect", ...}` 意图文件
- **THEN** 在默认 `poll_interval=0.3s` 下，1 秒内 `runtime/adapter-results/{intent_id}.json` SHALL 出现，内容等于 `{"data": {"ok": true}}`，且 `events.jsonl` SHALL 追加一条 `{"event": "bridge_auto_responded", "op": "send_message", ...}` 记录

#### Scenario: 真工具类 intent 不被自动应答

- **WHEN** 引擎写入 `{"op": "task", "name": "architect", "team_name": "...", "prompt": "..."}` 意图
- **THEN** 在 `poll_interval` 后 `runtime/adapter-results/{intent_id}.json` SHALL NOT 由 AutoBridgeResponder 产生，intent 文件 SHALL 保持可读状态，主 Agent 应答后方可继续

#### Scenario: 主 Agent 与 auto-responder 竞态时无副作用

- **WHEN** 对同一个 `_version` intent，主 Agent 已经先写入 result 文件 `{"data": {"version": "custom"}}`，随后 AutoBridgeResponder 轮询到该 intent
- **THEN** AutoBridgeResponder 检测 result 文件存在后 SHALL 直接跳过，不再重复写入；`FileBasedBridge` 读到的 version 等于 `"custom"`

#### Scenario: auto_bridge 开关关闭时完全回退

- **WHEN** `config.adapter.auto_bridge = false`
- **THEN** `TeamEnvironmentManager.initialize()` SHALL NOT 启动 AutoBridgeResponder，`runtime/adapter-intents/` 中所有 intent MUST 都由主 Agent 应答

#### Scenario: 引擎停止时 responder 线程干净退出

- **WHEN** `TeamEnvironmentManager.stop_run()` 已完成 adapter.team_delete 并调用 responder.stop(timeout=2.0)
- **THEN** 后台轮询线程 SHALL 在 2 秒内返回，线程 `is_alive()` 为 False，不残留僵尸线程

### Requirement: 新增 events.jsonl 事件类型 `bridge_auto_responded`

AutoBridgeResponder 每次应答一条 intent 时，SHALL 向 `runtime/events.jsonl` 追加一条事件记录。

#### Scenario: 事件格式包含 intent_id / op / decision

- **WHEN** AutoBridgeResponder 自动应答一条 `_version` intent，intent `_id = "abc-123"`
- **THEN** `events.jsonl` SHALL 新增一行 JSON，至少包含字段 `ts`（ISO 8601）、`event = "bridge_auto_responded"`、`intent_id = "abc-123"`、`op = "_version"`、`decision = "auto"`

#### Scenario: 跳过非自动应答类 intent 时不写事件

- **WHEN** AutoBridgeResponder 轮询到 `op = "task"` intent 决定不处理
- **THEN** `events.jsonl` SHALL NOT 产生 `bridge_auto_responded` 事件（仅主 Agent 应答后由引擎另行记录其它事件）

### Requirement: Web 面板暴露 "Pending bridge intents" 视图

Service API SHALL 新增端点 `GET /api/bridge/pending-intents`，返回当前 `runtime/adapter-intents/` 下所有**未被 AutoBridgeResponder 处理**的 intent 摘要列表；前端总览页 SHALL 显示对应卡片。

#### Scenario: 端点返回 pending intent 列表

- **WHEN** `runtime/adapter-intents/` 下有 2 个文件：一个 `op=task`（未被应答）、一个 `op=_version`（已被 AutoBridgeResponder 应答，result 文件已写）；GET `/api/bridge/pending-intents`
- **THEN** 响应状态 200、响应体 JSON 为 `[{"_id": "<task_intent_id>", "op": "task", "age_seconds": <float>, "hint": "请调用 task(name=..., team_name=..., ...)"}]`，MUST 不含 `_version` 项

#### Scenario: 无 pending 时返回空列表

- **WHEN** `runtime/adapter-intents/` 为空或所有 intent 都已有对应 result 文件；GET `/api/bridge/pending-intents`
- **THEN** 响应状态 200、响应体等于 `[]`

#### Scenario: 前端卡片空状态

- **WHEN** 前端总览页打开，`/api/bridge/pending-intents` 返回 `[]`
- **THEN** 卡片 SHALL 显示"✅ 无需干预"或等价文案，不渲染列表

#### Scenario: 前端卡片展示 pending hint

- **WHEN** `/api/bridge/pending-intents` 返回含一条 `op=team_create` 的 intent，`team_name = "ai-rd-team-abcd"`
- **THEN** 前端 SHALL 在卡片中展示一条带有 `team_create` 关键字与 `ai-rd-team-abcd` 的 hint 文本，等待时长以秒为单位显示

### Requirement: AutoBridgeResponder 默认启用且向后兼容

新版本发布后 SHALL 默认启用 AutoBridgeResponder（`adapter.auto_bridge` 缺省为 true）；旧用户配置 MUST 在零修改的情况下继续工作。

#### Scenario: 缺省配置视作 auto_bridge=true

- **WHEN** 用户 `config.yaml` 中未出现 `adapter.auto_bridge` 字段
- **THEN** `TeamEnvironmentManager.initialize()` 产出的 `EffectiveConfig.adapter.get("auto_bridge", True)` 等于 True，AutoBridgeResponder SHALL 被启动

#### Scenario: 显式关闭

- **WHEN** `config.yaml` 写 `adapter.auto_bridge: false`
- **THEN** `EffectiveConfig.adapter["auto_bridge"]` 等于 False，AutoBridgeResponder 对象 MUST 不被创建，后台线程 MUST 不启动
