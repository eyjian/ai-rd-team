## Context

### 现状

`openspec/specs/design/02-adapter.md §5.2 模式 C` 定义的 file-based bridge 当前要求主 Agent 在线轮询 `runtime/adapter-intents/`、读 intent、按 `op` 调 CodeBuddy 工具、把结果写回 `runtime/adapter-results/`。设计目的是保持"引擎是 Python 进程、工具调用由 main agent 做"的清晰边界，但在 E2E 场景下暴露出真实痛点：

- **主 Agent 离线 / 分心 → 引擎阻塞**：2026-05-04 blog-api v1 E2E 一度卡在 `_version` intent 超过 90 秒，用户以为进程死了
- **无需工具能力的 intent 占用主 Agent 工具调用配额**：`shutdown_request` 类只是礼节性通知，却每条占一次 `send_message` 工具调用
- **intent 流量分布极不均匀**：11 次手动应答集中在 initialize（2 次）+ spawn（6 次）+ stop（3 次），10 分钟 wait 期间 0 次

### 相关模块

- `src/ai_rd_team/adapter/bridge.py`：`CodeBuddyToolBridge` 抽象 + `FileBasedBridge` 实现（模式 C）+ `BridgeSimulator`（纯模拟，测试用）
- `src/ai_rd_team/adapter/codebuddy.py`：`CodeBuddyAdapter.initialize()` 调 `bridge.query_version_string()` + `bridge.probe_available_tools()`
- `src/ai_rd_team/engine/manager.py`：`TeamEnvironmentManager.initialize()` 构造 adapter
- `src/ai_rd_team/service/readers.py`：Web 面板 REST 端点
- `src/ai_rd_team/service/web/index.html`：Vue3 单页前端

### 约束

- **不改文件协议**：JSON schema、目录结构、`atomic_write`、超时语义全部保持不变
- **向后兼容**：旧用户配置（没有 `adapter.auto_bridge` 字段）必须零迁移即可工作
- **无外部依赖**：不依赖 CodeBuddy CLI / REST / IDE 扩展，纯 Python 进程内组件
- **与 `BridgeSimulator` 解耦**：simulator 是另一条并行路径（测试用，canned responses）

### 数据支撑

| 阶段 | bridge intent 数 | 其中需要真工具 | 本 change 后需要人工应答 |
|---|---|---|---|
| initialize | 2（`_version`/`_probe`） | 0 | **0**（F 去除或 D 自动应答） |
| spawn | 6（team_create + task×4 + 启动 send_message） | 6 | **6**（不变，这是 CodeBuddy 硬约束） |
| wait | 0 | 0 | 0 |
| stop | 3-4（shutdown_request × 3-4 + team_delete × 1） | 1（team_delete） | **1**（team_delete） |

**结论**：F + D 把 5 个 intent 从"人工"转成"自动"，总手动数从 11 → 6。

## Goals / Non-Goals

**Goals:**

- G1：initialize 阶段 bridge intent 数从 2 降到 0，用户启动后不再有"诡异 90 秒沉默"
- G2：stop_run 阶段 shutdown_request 的"礼节性 send_message"不再消耗主 Agent 工具调用
- G3：提供 `adapter.auto_bridge: false` 开关完全回退到老行为（用于调试 / 出问题降级）
- G4：Web 面板清楚告诉用户"现在需要主 Agent 应答哪几条 intent"，用户不用盲猜
- G5：整个 change 完全在 bridge 协议之上，不破坏既有文件协议，`BridgeSimulator` 不受影响

**Non-Goals:**

- NG1：不自动化真工具类 intent（team_create / task / send_message type=message / team_delete）
- NG2：不改 CodeBuddy 平台或 CodeBuddy CLI / Adapter SPI
- NG3：不引入进程间通信（无 socket / port / subprocess；纯文件 + Python thread）
- NG4：不处理 P2P 成员内部消息（本来就不走 bridge）
- NG5：不解决"成员 state 延迟更新"（独立 issue）
- NG6：不做 RP → USD 校准、Trae Adapter 等 M5 其它候选项

## Decisions

### D1：F 优化——`_version` / `_probe` 本地化

**决策**：`CodeBuddyAdapter.initialize()` 不再发 bridge intent，改为：

```python
def initialize(self) -> None:
    # 1. version：优先读 config.adapter.version_override，否则用内置常量
    override = self._config.get("version_override")
    version = override if isinstance(override, str) else DEFAULT_CODEBUDDY_VERSION
    # 2. probe：优先读 config.adapter.available_tools_override，否则用内置集合
    override_tools = self._config.get("available_tools_override")
    available = set(override_tools) if isinstance(override_tools, list) else DEFAULT_AVAILABLE_TOOLS

    missing = REQUIRED_TOOLS - available
    if missing:
        raise AdapterInitError(f"CodeBuddy 缺少核心工具: {sorted(missing)}。")

    self._version_info = VersionInfo(platform=self.PLATFORM, version=version, detected_at=datetime.now())
    self._capabilities = Capabilities(...)
```

- `DEFAULT_CODEBUDDY_VERSION = "claude-opus-4.x"`（保留大版本的模糊匹配，便于后续升级时不改代码）
- `DEFAULT_AVAILABLE_TOOLS = {"team_create", "team_delete", "task", "send_message"}`
- `REQUIRED_TOOLS` 保持现有逻辑

**Alternatives considered：**

- **Alt-A**：保留 bridge intent 但让 AutoBridgeResponder 兜底——多一层绕路、启动时延仍然比直接本地化慢 0.3+ 秒
- **Alt-B**：环境变量 `AI_RD_TEAM_CODEBUDDY_VERSION`——与整体配置风格不一致（项目主打 `config.yaml`）

**Trade-off**：version 从"动态探测"变成"代码常量"，CodeBuddy 升级到不兼容版本时 ai-rd-team 不会自动发现；缓解——保留 `version_override` 字段让用户可临时覆盖；真·不兼容场景会被 `REQUIRED_TOOLS` 缺失检查兜住。

### D2：AutoBridgeResponder 作为引擎内后台线程

**决策**：新建 `src/ai_rd_team/adapter/auto_responder.py`，实现 `AutoBridgeResponder`。API：

```python
class AutoBridgeResponder:
    def __init__(self, runtime_dir: Path, poll_interval: float = 0.3,
                 events_logger: EventsLogger | None = None) -> None: ...
    def start(self) -> None: ...                  # 启动后台线程
    def stop(self, timeout: float = 2.0) -> None: ...  # 停并 join
    @property
    def stats(self) -> dict[str, int]: ...        # responded_count / skipped_count by op
```

线程循环：

```
while not stop_event.is_set():
    for intent_file in sorted(glob(intent_dir/"*.json"), key=mtime):
        if result_file(intent_file).exists():   # 已被其他人（主 Agent）应答，跳
            continue
        intent = read_json_safe(intent_file)
        decision = decide(intent)
        if decision.handled:
            write_result(intent, {"data": decision.data})
            log_event("bridge_auto_responded", op=intent["op"], decision="auto")
    sleep(poll_interval)
```

`decide(intent)` 决策表：

| intent.op | intent.type | decision |
|---|---|---|
| `_version` | — | handled=True, data={"version": DEFAULT_CODEBUDDY_VERSION} |
| `_probe` | — | handled=True, data={"available_tools": list(DEFAULT_AVAILABLE_TOOLS)} |
| `send_message` | `shutdown_request` | handled=True, data={"ok": True} |
| `send_message` | `shutdown_response` | handled=True, data={"ok": True} |
| `send_message` | `broadcast` | handled=True, data={"ok": True}, log warning |
| `send_message` | `message` / `plan_approval_response` | handled=False（留给主 Agent） |
| `team_create` / `task` / `team_delete` | — | handled=False |
| 其它未知 op | — | handled=False |

**Alternatives considered：**

- **Alt-A（独立进程 `ai-rd-team bridge-worker`）**：用户要额外起一个终端跑它，UX 差；daemon 内嵌进 engine 更自然
- **Alt-B（asyncio event loop 替代 thread）**：引擎其它部分是纯同步代码，为一个小组件引入 asyncio 成本不值
- **Alt-C（使用 watchdog 文件监听）**：多一个依赖，且 `adapter-intents/` 轮询粒度 0.3s 对本场景已足够

**Trade-off**：auto-responder 与主 Agent 可能**并发**去应答同一个 intent（主 Agent 看到后手动回、同时 auto-responder 也回）。缓解策略：

1. auto-responder 只处理"决策表明确 handled=True"的 op，主 Agent 看 Web 面板会知道这些不用它处理
2. `write_result` 用原子写（temp + rename），`FileBasedBridge._write_intent_and_wait` 检查 result 存在后 unlink，重复写无害
3. 若真碰撞（极罕见），`FileBasedBridge` 读到先到的那份，后到的写失败（rename 覆盖），不影响引擎

### D3：配置开关 + 启停由 TeamEnvironmentManager 负责

**决策**：

- `config.adapter.auto_bridge` bool，默认 **true**（M5 起 opt-out，而非 opt-in）
- `TeamEnvironmentManager.initialize()` 构造 adapter 之后，**如果**是 CodeBuddy adapter 且 `auto_bridge=true`，启动 `AutoBridgeResponder`
- `TeamEnvironmentManager.stop_run()` 在 adapter team_delete 完成后 `responder.stop()`
- manager 直接持引用，不通过 DI（引擎其它组件也没用 DI）

**Alternatives considered：**

- **Alt-A**：让 `CodeBuddyAdapter` 自己持有 responder —— 但 adapter 职责是"发出 intent"，不应同时"代答 intent"，职责混淆
- **Alt-B**：让 `FileBasedBridge` 内嵌 responder —— 同上，bridge 是"请求方"，不应做"应答方"

### D4：Web 面板的 "Pending bridge intents" 区块

**决策**：

- 新增后端端点 `GET /api/bridge/pending-intents` → 返回 `list[PendingIntent]`：
  ```json
  [{"_id": "xxx", "op": "task", "name": "architect", "age_seconds": 12.3, "hint": "请调用 task(subagent_name=..., prompt=..., name=\"architect\", team_name=...)"}]
  ```
- 读侧直接扫 `adapter-intents/*.json`（已被 auto-responder 写了 result 的不算"pending"）
- 前端在总览页加一个卡片：标题 "Pending bridge intents"，若为空显示"✅ 无需干预"，否则列表展示，每条含 op / hint / age
- hint 文案按 op 预置：
  - `team_create` → "请调用 team_create(team_name=%s, description=%s)"
  - `task` → "请调用 task(name=%s, team_name=%s, subagent_name=%s, prompt=..., mode='bypassPermissions')"
  - `send_message type=message` → "请调用 send_message(type='message', recipient=%s, content=..., summary=%s)"
  - `team_delete` → "请调用 team_delete()"

**Alternatives considered：**

- **SSE 推送 pending intent 变化** → 第一期不做，简单轮询（Web 前端已有 5s poll 周期可复用）

### D5：事件观测

新增事件类型 `bridge_auto_responded`，写进 `runtime/events.jsonl`：

```json
{"ts": "2026-05-04T...", "event": "bridge_auto_responded", "intent_id": "...", "op": "_version", "decision": "auto"}
```

对应更新 `openspec/specs/design/11-runtime-protocol.md` §8.3 事件清单。

## Risks / Trade-offs

- **[Risk] auto-responder 与主 Agent 重复应答同一 intent** → 原子写 + intent 协议的"先到先得 + unlink 后冗余 result 无害"语义（D2 Trade-off 已论证）
- **[Risk] `_version` / `_probe` 本地常量过期** → 保留 `config.adapter.version_override` / `available_tools_override`；`REQUIRED_TOOLS` 缺失会抛 AdapterInitError 兜住致命情况
- **[Risk] shutdown_request 自动回 ok 后，成员可能没真正收到关闭通知** → 实际上 `team_delete` 会清理整个团队（M4-ex2 验证过），shutdown_request 更多是"让成员写 status=done 的信号"，即使错过也只是 state 文件不更新最后一次；缓解——`stop_run` 仍会最后发真 `team_delete` intent（由主 Agent 手动应答）
- **[Risk] 用户开了 auto_bridge=false 后 F 优化也失效** → 不，F（`_version`/`_probe` 本地化）是 adapter 内部变更，不受 `auto_bridge` 开关影响；auto_bridge 只控制 D daemon
- **[Trade-off] Web 面板要多一个 poll 端点** → 负担可忽略（读目录）；且只在用户打开面板时触发
- **[Trade-off] 测试需新增 auto_responder 并发场景** → 用 `BridgeSimulator` 一样的 threading + tempdir 模式，~80 行测试搞定

## Migration Plan

1. 发布包含 `auto_bridge=true` 默认值的新版本（0.1.0a2 或 0.2.0）
2. CHANGELOG 显式说明："E2E 手动应答次数从 ~11 降到 ~6，遇到兼容问题可设 `adapter.auto_bridge: false` 回退"
3. 旧工作区无需任何改动（`auto_bridge` 缺省 true）
4. 一个 alpha 周期后把 F 的 `DEFAULT_CODEBUDDY_VERSION` 升到 CodeBuddy 正式版本号

回滚策略：

- **配置级**：`adapter.auto_bridge: false`
- **代码级**：F 行为可通过 `adapter.version_override` / `available_tools_override` 修正；若问题严重可把 `CodeBuddyAdapter.initialize()` 回退成 bridge 调用的 one-liner

## Open Questions

- OQ1：`broadcast` 在 Standard 档被 role 约束"禁止使用"，但引擎不强制拦截。若 auto-responder 遇到 broadcast 是回 `ok=True` 还是 `ok=False` 还是转发给主 Agent？**暂定方案**：auto 应答 `ok=True` 并写 warning 事件（让引擎 log 里有记录，但不阻塞运行）。
- OQ2：`plan_approval_response` 目前没出现过，若未来引入"成员主动请批计划"场景，是否要自动应答？**暂定方案**：handled=False，留给主 Agent（因为"批准计划"是重要决策）。
- OQ3：auto-responder 是否该**速率限制**应答数？**暂定方案**：不限，因为 intent 物理上就是文件产生速率，不会爆。若未来观察到 CPU 占用高再加 `max_responses_per_second`。
