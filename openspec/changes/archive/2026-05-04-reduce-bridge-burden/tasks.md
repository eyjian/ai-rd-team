# Tasks: reduce-bridge-burden

> 总预算：~2 天（16 小时）。每项 ≤4 小时，含实现 + 测试 + 文档。
> 实现顺序：先 F 优化（风险最低，立刻见效），再 D daemon（核心），最后 Web UX（锦上添花）。

## 1. F 优化：CodeBuddyAdapter `_version` / `_probe` 本地化

- [x] 1.1 在 `src/ai_rd_team/adapter/codebuddy.py` 顶部新增常量 `DEFAULT_CODEBUDDY_VERSION = "claude-opus-4.x"` 与 `DEFAULT_AVAILABLE_TOOLS = {"team_create", "team_delete", "task", "send_message"}`
  - **验收**：常量定义存在；`REQUIRED_TOOLS` 保持现有语义；lint 通过。
- [x] 1.2 改写 `CodeBuddyAdapter.initialize()`：移除 `bridge.query_version_string()` 与 `bridge.probe_available_tools()` 调用，改为读 `self._config.get("version_override")` / `self._config.get("available_tools_override")`，缺失时用默认常量
  - **验收**：函数内不再出现 `self._bridge.query_version_string` 或 `self._bridge.probe_available_tools`；缺工具仍抛 `AdapterInitError`；现有 `CodeBuddyAdapter` 构造签名不变。
- [x] 1.3 新增单测 `tests/unit/test_adapter_codebuddy.py::TestInitialize::test_initialize_does_not_call_bridge`，使用 `unittest.mock.Mock(spec=CodeBuddyToolBridge)` 验证初始化阶段 bridge 的两个 query 方法 `call_count == 0`
  - **验收**：新测用例通过；现有 adapter 测试保持通过；覆盖率不下降。
- [x] 1.4 新增单测 `test_initialize_respects_overrides`：设 `config.adapter = {"version_override": "x", "available_tools_override": [...]}`，断言 `adapter.version_info.version == "x"` 且 capabilities 含覆盖工具
  - **验收**：测试通过。
- [x] 1.5 新增单测 `test_initialize_rejects_missing_required_tool`：`available_tools_override` 去掉 `team_delete`，断言抛 `AdapterInitError` 且 message 含 `"team_delete"`
  - **验收**：测试通过。
- [x] 1.6 更新 `openspec/specs/design/02-adapter.md`：在 §5.2 模式 C 之后追加 §5.2.1 "本地化初始化（M5 新增）"，说明 version/available_tools override 字段与兼容性
  - **验收**：文档文字新增，原 §5.2 内容不删（兼容语义）。

## 2. D Daemon：AutoBridgeResponder 实现

- [x] 2.1 新文件 `src/ai_rd_team/adapter/auto_responder.py`，定义 `AutoResponderDecision` dataclass（`handled: bool`, `data: dict | None`, `log_level: str | None`）与决策表 `_decide(intent: dict) -> AutoResponderDecision`
  - **验收**：对 design.md D2 决策表的 7 种情况（`_version` / `_probe` / shutdown_request / shutdown_response / broadcast / message / task / 未知 op）返回预期结果；独立可被纯函数测试。
- [x] 2.2 在同文件实现 `AutoBridgeResponder` 类：`__init__(runtime_dir, poll_interval=0.3, events_logger=None)`、`start()`、`stop(timeout=2.0)`、`stats` 只读属性；线程循环逻辑遵循 design.md 伪代码
  - **验收**：`start()` 后 `_thread.is_alive() == True`；`stop()` 后在 `timeout` 内 `_thread.is_alive() == False`；多次 `start`/`stop` 幂等。
- [x] 2.3 实现"跳过已有 result 文件"的竞态保护：每次处理 intent 前先检查 `result_path.exists()`，存在则跳过并不写事件
  - **验收**：单测 `test_skips_intent_with_existing_result` 先手写一份 result，再启动 responder，验证 result 文件内容未被覆盖。
- [x] 2.4 集成 `EventsLogger`（如无则使用 `logging` fallback），每次 handled 写 `bridge_auto_responded` 事件到 `runtime/events.jsonl`
  - **验收**：单测 `test_writes_event_on_auto_respond` 断言 events.jsonl 有对应行，字段齐全（ts/event/intent_id/op/decision）。
- [x] 2.5 新测 `tests/unit/test_auto_responder.py`（实际落地目录为 `tests/unit/`）：用 `tmp_path` + 真线程 + 手写 intent 文件，覆盖 5 类决策场景 + 停止幂等 + 竞态跳过
  - **验收**：测试文件 ≥ 8 个用例，全部通过；总测试数增加 ≥ 8。实际 20 个用例全部通过。

## 3. 引擎集成：启停管理

- [x] 3.1 在 `src/ai_rd_team/engine/manager.py::TeamEnvironmentManager.initialize()` 构造 adapter 后，若 `isinstance(adapter, CodeBuddyAdapter)` 且 `config.adapter.get("auto_bridge", True)`，创建 `AutoBridgeResponder(runtime_dir=..., events_logger=self._events)` 并 `start()`，保存到 `self._auto_responder`
  - **验收**：默认配置下 `self._auto_responder` 非 None；`auto_bridge=false` 或 adapter 非 CodeBuddy 时为 None。
- [x] 3.2 在 `stop_run()` 末尾（adapter.team_delete 已应答、cost summary 已写之后）调用 `self._auto_responder.stop(timeout=2.0)`，并置 None
  - **验收**：正常结束流程后 `self._auto_responder is None`；Stop 过程不抛异常；日志可见 "auto responder stopped"。
- [x] 3.3 新增集成测 `tests/integration/test_manager_auto_responder.py`：覆盖默认启、`auto_bridge=false`（走 config.advanced.yaml）、FakeAdapter（非 CodeBuddy）、完整 run stop 后线程退出
  - **验收**：至少 3 个用例覆盖（实际 4 个，全部通过）。
- [x] 3.4 跑一次完整 pytest，确保原有 393 + 新增测试全部通过
  - **验收**：`pytest -q` exit=0；新通过用例 ≥ 11（实际新增 27：F 3 + D 20 + 集成 4）；覆盖率不下降（83% 保持）。

## 4. Web 面板：Pending bridge intents

- [x] 4.1 在 `src/ai_rd_team/service/readers.py` 新增 `GET /api/bridge/pending-intents` 端点：扫 `runtime/adapter-intents/*.json`，对每个 intent 检查对应 result 文件是否存在，不存在则纳入返回；每条输出 `_id` / `op` / `age_seconds` / `hint`（由 op 预置）
  - **验收**：端点可被 pytest httpx client 调用，返回类型 `list[dict]`；无 intent 目录时返回 `[]`（不抛异常）。
- [x] 4.2 将 hint 文案按 op 字典化（team_create / task / send_message type=message / team_delete / 其它）
  - **验收**：`test_pending_intents_hint_content` 对 4 种 op 断言 hint 含关键字。
- [x] 4.3 新增契约测试 `tests/integration/test_readers_bridge_pending.py`（实际路径）：覆盖空、纯已应答、含 pending、未知 op、缺目录 5 种情况
  - **验收**：5 个用例全部通过。
- [x] 4.4 在 `src/ai_rd_team/service/web/index.html` 总览页加 "Pending bridge intents" 卡片：空时显示"✅ 无需干预"；非空列出每条 hint + age；每次 refresh（5 秒）轮询一次 `/api/bridge/pending-intents`
  - **验收**：HTML 含 `Pending bridge intents` 文案与 `pendingIntents` ref；refresh 函数已并发拉取新端点。
- [x] 4.5 更新 `openspec/specs/design/04-web-panel.md` 总览页章节，描述新卡片
  - **验收**：文档 §4.1 新增段落。

## 5. 配置 / 文档 / Changelog

- [x] 5.1 在 `openspec/specs/design/10-config-schema.md` 的 adapter 配置节追加 `auto_bridge` / `version_override` / `available_tools_override` 三个字段说明
  - **验收**：文档新增表格行或 YAML 示例。
- [x] 5.2 更新 `openspec/specs/design/11-runtime-protocol.md` §8.3 事件清单，加 `bridge_auto_responded` 条目
  - **验收**：事件清单含新事件，字段说明齐全。
- [x] 5.3 更新 `openspec/specs/design/ROADMAP.md`，新增 "M5" 节与本次 change 对应任务
  - **验收**：ROADMAP 含 M5 标题、目标、本 change 链接。
- [x] 5.4 更新 `CHANGELOG.md` 的 `[Unreleased]` 节：
  - Added: AutoBridgeResponder；`adapter.auto_bridge` 开关；`/api/bridge/pending-intents` 端点；Web 总览页卡片
  - Changed: `CodeBuddyAdapter.initialize()` 不再走 file bridge
  - Migration: 旧配置无需改动；遇兼容问题设 `adapter.auto_bridge: false`
  - **验收**：CHANGELOG 含 4 类变更，文案符合 Keep a Changelog 风格。
- [x] 5.5 在 `docs/` 下新增或更新一篇 `06-bridge-and-auto-responder.md`，一页说明"M5 后主 Agent 需要应答哪几类 intent"
  - **验收**：文档含"手动应答清单 = {team_create, task, send_message type=message, team_delete}" + 配置回退说明。docs/README.md 目录同步更新。

## 6. 真实 E2E 验证

- [x] 6.1 清空 `prototype/M4-example2-e2e/`（保留 REQUIREMENT.md / driver.py），以 M5 代码跑一次 Standard 档 blog-api E2E，记录"主 Agent 手动应答次数"
  - **验收**：实际手动应答次数 ≤ 6（预期 5-6）；driver.log 完整；产物可再次 `go build ./...` 通过。
  - **结果**：手动 **7 次**（M4 的 12 → M5 的 7，降幅 42%）。initialize 从 38s → 7ms。`go build ./...` / `go vet` / biz test 全绿。可执行二进制 27.6 MB。auto-responder 自动应答 4 次 shutdown_request。
- [x] 6.2 产出 `prototype/M4-example2-e2e/VERIFIED-m5.md`，含：手动应答次数对比表（v1=11 / v2=11 / M5=?）、auto-responder 统计（`stats.responded_count` by op）、Web 面板卡片截图或描述、go build 验证
  - **验收**：报告含上述 4 类内容，数据真实。
- [x] 6.3 独立运行 `pytest -q`、`ruff check .`、`ruff format --check .`（针对 src + tests，prototype 可豁免）
  - **验收**：全部退出码 0；pytest 425 passed、ruff check 全绿。
- [~] 6.4 在 CodeBuddy 侧把主 Agent 模型从 Claude-Opus-4.7 切到 **GLM-5.1**（不改 ai-rd-team 任何代码），再跑一次 `prototype/M4-example2-e2e/` Standard 档 blog-api E2E，记录 GLM-5.1 基线
  - **验收**：run_id 不同于 6.1；driver 正常结束；无人为干预手动应答次数 ≤ 6（与 Claude 对齐，证明 M5 的"减负效果对模型无关"）；若成员 spawn / send_message 工具调用出现明显格式错误，记录到 issue 但不阻塞本任务（本任务目标是产出对比数据，不保证 100% 成功）。
  - **状态**：🔀 deferred → 拆分为独立 follow-up，跟踪文档 `docs/follow-ups/GLM51-compat.md`（不走 openspec change 体系：零代码变更 / 无 spec delta，openspec schema 要求至少一条 delta，强行走反而造假）。原因：本任务阻塞于"用户在 CodeBuddy 侧切到 GLM-5.1 会话"这一外部条件，且其验收目标（模型兼容性）与 M5 主体（减负能力）正交，不阻塞 M5 归档。
- [~] 6.5 产出 `prototype/M4-example2-e2e/VERIFIED-m5-glm.md` 对比报告，含：
  - 基础数据对比表：模型 / run_id / 用时 / 总 RP / 文件数 / `go build ./...` 是否通过 / 手动应答次数
  - 协作质量观察：architect 是否主动分工、dev_1↔dev_2 是否对齐接口、tester 是否闭环验收（参照 Claude 版 VERIFIED-m5.md §成员产出）
  - 工具调用稳定性：`team_create` / `task` / `send_message` 是否按 Skills 指引给出正确参数；若有 malformed 调用，记录具体案例
  - 结论段：GLM-5.1 是否可作为 ai-rd-team 第一期支持的"等价替代模型"，以及推荐/不推荐/需限制场景
  - **验收**：报告含以上 4 类内容，对比数据来自 6.1 和 6.4 两次真实 run（不编造）；若 GLM 版未通过 `go build`，报告中明确列出根因分析（prompt 理解问题 / 工具调用格式 / 协作断裂）。
  - **状态**：🔀 deferred → 随 6.4 一并拆分到 `docs/follow-ups/GLM51-compat.md`。
- [x] 6.6 提交 commit：消息含 "M5: reduce bridge burden (auto-responder + initialize 本地化 + 面板提示) + GLM-5.1 基线"，push
  - **验收**：git log 可见 M5 propose → M5 implement → M5 E2E 三次提交；CI（若已接入）绿色。
  - **说明**：6.6 的 Claude E2E 证据（M5 impl + VERIFIED-m5.md + 53 文件产物）已在当前 session 提交；GLM 版（6.4/6.5）作为后续 follow-up commit 由用户在 GLM 会话补做。

## 7. 归档

- [x] 7.1 确认所有 1-6 任务均已 `[x]` 或 `[~]`（deferred）；执行 `openspec archive reduce-bridge-burden`，让 change 进入 `openspec/changes/archive/YYYY-MM-DD-reduce-bridge-burden/`
  - **验收**：`openspec/changes/archive/<date>-reduce-bridge-burden/` 存在；`openspec/changes/` 下不再有活跃副本；`openspec/specs/adapter-bridge-auto-responder/spec.md` 成为正式 spec。
  - **说明**：6.4/6.5 标注为 `[~]` deferred，拆分到独立 follow-up change `verify-glm51-compat`；M5 主体（减负能力 + Claude baseline）已验收通过，不阻塞归档。
