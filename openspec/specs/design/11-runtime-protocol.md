# ai-rd-team 详细设计 - 11 运行时协议

> 文档版本：v1.0
> 日期：2026-05-04
> 颗粒度：**实现级**
> 依赖：`00-overview.md`、`01-engine.md`、`02-adapter.md`、`07-artifacts.md`
> 来自原型：P1（成员→文件→Web）+ P3（文件监听）+ P4（并发写）

---

## 1. 目的与范围

### 1.1 目的
定义 `.ai-rd-team/runtime/` 目录下**所有文件的数据协议**。运行时文件是引擎、成员、Web 面板、Adapter Bridge 之间的**通信契约**——任何一方不能随意改格式。

### 1.2 范围
- 运行时目录完整结构
- state/ 状态文件格式
- messages/ 消息文件格式
- commands/ 指令文件格式
- adapter-intents / adapter-results 的数据契约
- events.jsonl 事件流格式
- 文件生命周期与归档

### 1.3 非目标
- ❌ 制品文件格式（见 `07-artifacts.md`）
- ❌ memory 文件格式（见 `06-memory-system.md`）
- ❌ 业务 Schema（见各业务文档）

---

## 2. 运行时目录完整结构

```
<workspace>/.ai-rd-team/runtime/
│
├── current-run.yaml                 # 当前运行元数据
│
├── state/                           # 状态（多方读写，用原子 rename）
│   ├── team.yaml                    # 团队整体状态
│   ├── members/
│   │   ├── architect.yaml           # 每成员状态（成员写，引擎+Web 读）
│   │   ├── developer_1.yaml
│   │   └── ...
│   └── roster.yaml                  # 名册（引擎写，成员读）
│
├── messages/                        # 消息记录（每消息一文件）
│   ├── 20260504-100000-main-architect.json
│   ├── 20260504-100015-architect-developer_1.json
│   └── ...
│
├── events.jsonl                     # 全局事件流（fcntl 锁追加）
│
├── commands/                        # 用户操作指令队列
│   ├── pending/                     # 待处理
│   │   └── pause-1746950400.json
│   └── processed/                   # 已处理（归档）
│       └── ...
│
├── adapter-intents/                 # Adapter Bridge 的工具调用意图
│   └── {uuid}.json
├── adapter-results/                 # Adapter Bridge 的工具调用结果
│   └── {uuid}.json
│
├── cost/                            # 成本追踪
│   ├── resource-points.yaml         # 实时 RP 累计（原子写）
│   ├── model-history.jsonl          # 模型切换历史
│   └── post-run.jsonl               # 事后填入的真实消耗
│
├── artifacts/                       # 制品（见 07-artifacts.md）
│   └── ...
│
├── logs/
│   ├── engine.log                   # 引擎日志（Python logging）
│   └── adapter-calls.jsonl          # Adapter 调用审计（fcntl 锁追加）
│
└── archive/                         # 归档（每次 stop_run 后）
    └── run-{run_id}/
        └── ...（整个 runtime 子集的快照）
```

---

## 3. current-run.yaml

### 3.1 Schema

```yaml
# 当前运行元数据（原子 rename 写）
schema_version: "1.0"
run_id: "abc12345"
requirement: "实现一个用户管理模块"            # 用户输入的需求
mode: "standard"                              # lite / standard / full
started_at: "2026-05-04T10:00:00Z"
status: "running"                             # initializing / running / paused / stopping / completed / failed
current_phase: "development"                  # requirements / design / development / review / test / deployment
engine_pid: 12345                             # 可选：引擎进程 ID（监测僵尸）
platform: "codebuddy"                         # Adapter 平台
```

### 3.2 生命周期

| 事件 | 写入者 | 字段变化 |
|------|-------|---------|
| `start_run` | 引擎 | 创建文件 |
| 阶段切换 | PM 或引擎 | `current_phase` 更新 |
| `pause_run` | 引擎 | `status` → paused |
| `resume_run` | 引擎 | `status` → running |
| `stop_run` | 引擎 | `status` → completed/failed，之后文件被归档 |

### 3.3 用途

- 引擎启动时读取 → 判断是否有残留运行（断点续跑）
- Web 面板读取 → 展示当前运行基本信息
- CLI `status` 命令读取 → 展示给用户

---

## 4. state/team.yaml

### 4.1 Schema

```yaml
schema_version: "1.0"
team_id: "ai-rd-team-abc12345"
platform_id: "ai-rd-team-abc12345"            # CodeBuddy 内部 team_name
created_at: "2026-05-04T10:00:15Z"
status: "running"                              # creating / running / pausing / paused / shutting_down / shut_down / error
last_heartbeat: "2026-05-04T10:05:30Z"
```

### 4.2 读写方

- **写**：`TeamLifecycleManager`（引擎子模块）
- **读**：引擎、Web 面板

---

## 5. state/members/{member_id}.yaml

### 5.1 Schema

```yaml
schema_version: "1.0"
# 身份
name: "architect"
role: "architect"
display_name: "陈架构"
team_id: "ai-rd-team-abc12345"

# 状态
status: "working"                              # idle / working / waiting / done / failed
current_task: "设计用户管理模块接口"
created_at: "2026-05-04T10:00:15Z"
last_updated: "2026-05-04T10:05:30Z"
progress: "60%"                                # 粗略进度（字符串）

# 产出
produced_files:
  - "artifacts/design/spec-architecture.md"
  - "artifacts/design/data-interfaces.yaml"

# 阻塞
blocking_issues:
  - description: "需要澄清 email 注册是否要求验证"
    since: "2026-05-04T10:04:00Z"
    expecting: "answer from user via pm"

waiting_for:                                   # 当前等待谁的响应
  - "developer_1"                              # 等 developer_1 确认接口
  - "user"                                     # 通过 pm 等用户答复

# 最近通信记录（简要，避免文件过大）
communication_log:
  - ts: "2026-05-04T10:00:30Z"
    direction: "in"
    from: "main"
    summary: "启动任务"
  - ts: "2026-05-04T10:03:00Z"
    direction: "out"
    to: "developer_1"
    summary: "接口设计已就绪"

# 自报的资源消耗（粗略，供对比 CostTracker）
resource_usage:
  message_count: 3
  files_written: 2
  runtime_minutes: 5.5
```

### 5.2 读写方

- **写**：成员（通过 Write 工具写 YAML）
- **读**：引擎、Web 面板、其他成员（查看队友状态）

### 5.3 并发安全

成员用原子 rename 写（P4 的 S2）。  
引擎读时若文件刚被改可能读到旧版，读失败时重试 1 次。

### 5.4 更新频率约定

成员应在以下时机更新 state（由 Prompt 引导，成员自觉遵守）：
- 开始新任务
- 产出一个文件
- 发出/收到关键消息
- 遇到阻塞
- 完成全部工作

**不要**每秒更新（避免 IO 压力 + 写放大）。

---

## 6. state/roster.yaml

```yaml
schema_version: "1.0"
team_id: "ai-rd-team-abc12345"
members:
  - member_id: "architect"
    role: "architect"
    display_name: "陈架构"
    spawned_at: "2026-05-04T10:00:15Z"
  - member_id: "developer_1"
    role: "developer"
    display_name: "林1号"
    spawned_at: "2026-05-04T10:00:16Z"
  - ...
```

**用途**：成员间互相发现；Web 面板展示团队组成。

---

## 7. messages/

### 7.1 命名规则

```
{YYYYMMDD-HHMMSS}-{from_member}-{to_member}.json
```

- 时间戳精确到秒（同秒内多条消息追加 `.1`、`.2`）
- `to_member` 可以是 `all`（broadcast）或 `main`
- 文件名不含内容摘要（避免特殊字符问题）

### 7.2 Schema

```json
{
  "schema_version": "1.0",
  "message_id": "msg-abc123",
  "ts": "2026-05-04T10:03:00.123Z",
  "from": "architect",
  "to": "developer_1",
  "type": "message",
  "summary": "接口设计已就绪",
  "content": "接口已完成，详见 artifacts/design/data-interfaces.yaml...",
  "triggered_by": "main->architect:start_task",  
  "related_artifacts": [
    "artifacts/design/data-interfaces.yaml"
  ],
  "estimated_tokens": 45
}
```

### 7.3 写入方

**两种来源**：

**A. CodeBuddyAdapter 的日志拦截**：每次 `send_message` 调用后，Bridge 把消息写到 `messages/`（作为审计记录）

**B. 成员主动记录（可选）**：成员判断某消息重要，主动写入

**第一期**：只用 A，成员不需要管。

---

## 8. events.jsonl（全局事件流）

### 8.1 用途

记录系统级事件（非业务制品）：成员 spawn、团队创建、Hook 触发、预算告警等。**fcntl 锁追加**。

### 8.2 格式

每行一个 JSON 对象：

```jsonl
{"ts":"2026-05-04T10:00:00Z","event":"run_started","run_id":"abc","mode":"standard"}
{"ts":"2026-05-04T10:00:15Z","event":"team_created","team_id":"ai-rd-team-abc"}
{"ts":"2026-05-04T10:00:16Z","event":"member_spawned","member_id":"architect","role":"architect"}
{"ts":"2026-05-04T10:03:00Z","event":"message_sent","from":"architect","to":"developer_1"}
{"ts":"2026-05-04T10:15:00Z","event":"budget_threshold_reached","threshold":0.75,"rp":300}
{"ts":"2026-05-04T10:30:00Z","event":"artifact_written","producer":"developer_1","path":"src/api/user.go"}
{"ts":"2026-05-04T10:45:00Z","event":"phase_complete","phase":"development"}
...
```

### 8.3 事件类型清单

| 事件 | 触发方 | 关键字段 |
|------|-------|---------|
| `run_started` | 引擎 | run_id, mode |
| `run_paused` | 引擎 | reason |
| `run_resumed` | 引擎 | - |
| `run_stopped` | 引擎 | reason |
| `team_created` | 引擎 | team_id |
| `team_deleted` | 引擎 | team_id |
| `member_spawned` | 引擎 | member_id, role |
| `member_shutdown_requested` | 引擎 | member_id |
| `member_status_changed` | FileWatcher | member_id, from, to |
| `message_sent` | Adapter | from, to, type |
| `artifact_written` | FileWatcher | producer, path |
| `budget_threshold_reached` | CostTracker | threshold, rp |
| `budget_exceeded` | CostTracker | limit, used |
| `quota_{day/week/month}_warning` | CostTracker | window, ratio |
| `quota_{day/week/month}_blocked` | CostTracker | window |
| `phase_complete` | PM 或 Hook | phase |
| `hook_triggered` | HookRunner | hook_name |
| `bridge_auto_responded` | AutoBridgeResponder（M5） | intent_id, op, decision, type? |
| `error` | 任何 | error, context |

### 8.4 保留策略

- 当次运行的 `events.jsonl` 归档到 `archive/run-{id}/`
- 跨次运行不累积（避免无限增长）

---

## 9. commands/（用户指令队列）

### 9.1 用途

用户对运行中团队的操作（暂停/恢复/发消息/升档等）通过"指令文件"下发。

**流程**：

```
用户 → Web 前端 → Flask API → 写 commands/pending/*.json → 引擎轮询 → 执行 → 移到 processed/
```

### 9.2 命名规则

```
{command}-{timestamp}.json
```

例：
- `pause-1746950400.json`
- `resume-1746950500.json`
- `message-to-architect-1746950600.json`
- `escalate-to-full-1746950700.json`

### 9.3 通用 Schema

```json
{
  "schema_version": "1.0",
  "command_id": "cmd-abc123",
  "command": "pause",
  "issued_at": "2026-05-04T10:00:00Z",
  "issued_by": "user",
  "params": {...}
}
```

### 9.4 各命令的 params

**pause**：

```json
{"command": "pause", "params": {"reason": "lunch"}}
```

**resume**：

```json
{"command": "resume", "params": {}}
```

**message**（用户给某成员发消息）：

```json
{
  "command": "message",
  "params": {
    "to": "architect",
    "content": "请再考虑一下移动端兼容性",
    "summary": "补充需求"
  }
}
```

**escalate**（升档）：

```json
{"command": "escalate", "params": {"target_mode": "full"}}
```

**prompt_response**（对 smart_pause 菜单的响应）：

```json
{
  "command": "prompt_response",
  "params": {
    "prompt_id": "budget-exceeded-123",
    "choice": "add_budget",
    "extra": {"amount": 200}
  }
}
```

**manual_model_switched**（用户确认已手工切换模型）：

```json
{
  "command": "manual_model_switched",
  "params": {"new_model": "claude-haiku"}
}
```

### 9.5 处理流程

```python
# 引擎每秒轮询一次（或 FileWatcher 触发）
def process_pending_commands(runtime_dir: Path, engine) -> None:
    pending = runtime_dir / "commands" / "pending"
    processed = runtime_dir / "commands" / "processed"
    
    # 按文件名时间戳排序，依次处理
    for cmd_file in sorted(pending.glob("*.json")):
        cmd = json.loads(cmd_file.read_text())
        try:
            dispatch_command(cmd, engine)
        except Exception as e:
            logger.exception("Command failed: %s", cmd)
            cmd["_error"] = str(e)
        # 移到 processed
        cmd["_processed_at"] = datetime.now().isoformat()
        (processed / cmd_file.name).write_text(json.dumps(cmd, ensure_ascii=False))
        cmd_file.unlink()
```

---

## 10. adapter-intents / adapter-results（Bridge 通道）

### 10.1 用途

`02-adapter.md §5.2 模式 C` 的实现——Python 引擎通过文件与主 Agent 的工具调用能力对接。

### 10.2 intent 文件 Schema

`adapter-intents/{uuid}.json`：

```json
{
  "schema_version": "1.0",
  "_id": "550e8400-e29b-41d4-a716-446655440000",
  "_ts": "2026-05-04T10:00:15Z",
  "op": "team_create",
  "team_name": "ai-rd-team-abc",
  "description": "..."
}
```

**op 枚举**：
- `_probe`：探测可用工具
- `_version`：查询版本
- `team_create`
- `team_delete`
- `task`：派发成员
- `send_message`

**op 参数** 依 op 而不同，见 `02-adapter.md §5.2`。

### 10.3 result 文件 Schema

`adapter-results/{uuid}.json`：

```json
{
  "schema_version": "1.0",
  "_intent_id": "550e8400-e29b-41d4-a716-446655440000",
  "_ts": "2026-05-04T10:00:16Z",
  "success": true,
  "data": {
    "platform_id": "ai-rd-team-abc"
  }
}
```

失败：

```json
{
  "success": false,
  "error": "team already exists: ai-rd-team-abc",
  "error_code": "TEAM_EXISTS"
}
```

### 10.4 生命周期

```
Python Bridge 写 intents/{uuid}.json
    ↓
主 Agent 通过内置 Skill 感知 + 执行对应 CodeBuddy 工具
    ↓
主 Agent 写 results/{uuid}.json
    ↓
Python Bridge 读取 result → 返回调用方 → 清理两个文件
```

### 10.5 超时与清理

- intent 写入 60 秒仍无 result → Bridge 抛 TimeoutError
- 每次 start_run 清空 intents/ 和 results/（避免残留污染）

### 10.6 并发处理顺序

intents 按**文件 mtime** 顺序处理（或文件名前缀时间戳）。同一时刻只处理一个，避免工具调用竞争。

---

## 11. cost/ 目录

### 11.1 resource-points.yaml（原子写）

```yaml
schema_version: "1.0"
run_id: "abc12345"
mode: "standard"
timestamp: "2026-05-04T10:15:00Z"

# 计数
member_spawn_count: 5
message_count: 87
broadcast_target_count: 0
runtime_minutes: 35.5
iteration_count: 4

# Resource Points
resource_points: 285

# 预算剩余
run_budget_remaining: 115
day_budget_remaining: 1615
week_budget_remaining: 8000
month_budget_remaining: 25000

# 模型降级状态
fallback_triggered: false
```

### 11.2 model-history.jsonl（追加）

```jsonl
{"ts":"2026-05-04T10:20:00Z","event":"fallback_suggested","rp":300,"threshold":0.75}
{"ts":"2026-05-04T10:21:00Z","event":"manual_switch_confirmed","from":"claude-sonnet-4","to":"claude-haiku"}
```

### 11.3 post-run.jsonl（追加）

见 `08-cost-control §7.1`。

---

## 12. logs/ 目录

### 12.1 engine.log

Python logging 标准格式，按配置 `logging.*` 滚动。

### 12.2 adapter-calls.jsonl

Adapter 所有调用审计，格式见 `02-adapter.md §10`。

**fcntl 锁追加**（S3 策略）。

---

## 13. archive/ 归档机制

### 13.1 触发时机

`engine.stop_run()` 成功后。

### 13.2 归档内容

```
archive/run-{run_id}/
├── summary.yaml                   # 运行总结（由 engine 生成）
├── current-run.yaml               # 最终状态快照
├── state/                         # 最终 state 快照
├── messages/                      # 所有消息
├── events.jsonl                   # 全部事件流
├── cost/                          # 成本数据
├── artifacts/                     # 制品
└── logs/
```

### 13.3 归档后清理

- `state/members/*.yaml`：清空（下次运行重建）
- `messages/`：清空
- `commands/`：清空
- `adapter-intents/` / `adapter-results/`：清空
- `events.jsonl`：清空
- `cost/resource-points.yaml`：清空（quota-history 留在 `~/.ai-rd-team/`）
- `artifacts/`：保留（用户可能还要看 / 用）

### 13.4 summary.yaml

```yaml
schema_version: "1.0"
run_id: "abc12345"
started_at: "2026-05-04T10:00:00Z"
ended_at: "2026-05-04T11:00:00Z"
duration_minutes: 60
mode: "standard"
reason: "completed"                          # completed / user_stopped / budget_exceeded / error

members:
  - member_id: architect
    role: architect
    final_status: done
  - ...

metrics:
  resource_points_used: 385
  message_count: 87
  artifact_count: 14
  iterations: 6

# 引用详细数据
references:
  final_artifacts: "artifacts/"
  full_events: "events.jsonl"
  cost_detail: "cost/resource-points.yaml"
```

---

## 14. 断点续跑协议

### 14.1 恢复条件

引擎启动时检测 `current-run.yaml`：

| 状态 | 动作 |
|------|------|
| 文件不存在 | 正常启动 |
| `status=completed/failed` | 归档后清理，正常启动 |
| `status=running/paused` | **尝试恢复**（见 §14.2） |

### 14.2 恢复流程

```python
def try_resume(engine, current_run: dict) -> bool:
    # 1. 询问用户（第一期 default_mode）
    choice = prompt_user({
        "prompt": f"检测到未完成的运行（{current_run['run_id']}），要恢复吗？",
        "options": [
            ("resume", "恢复"),
            ("archive_and_new", "归档并开新运行"),
            ("abandon", "放弃该运行"),
        ],
    })
    
    if choice == "archive_and_new":
        engine.runtime_state.archive_current_as("interrupted")
        return False
    if choice == "abandon":
        engine.runtime_state.clear_current()
        return False
    
    # 2. 尝试重连 Adapter
    try:
        adapter = create_adapter(current_run["platform"], ...)
        # CodeBuddy 的 team 可能还活着
        team = adapter.reconnect_team(current_run["team_id"])
    except Exception:
        logger.warning("Cannot reconnect; falling back to archive_and_new")
        engine.runtime_state.archive_current_as("reconnect_failed")
        return False
    
    # 3. 恢复 RunContext
    roster = load(state/roster.yaml)
    ctx = RunContext(...)
    for member_record in roster.members:
        member = MemberHandle(...)  # 从文件重建
        ctx.members[member.member_id] = member
    
    # 4. 读取各成员 state，确认是否还活着
    for m in ctx.members.values():
        status = engine.runtime_state.get_member_status(m.member_id)
        if status in ("done", "failed", "terminated"):
            continue  # 已完成，跳过
        # 发消息确认是否还在
        adapter.send_message(Message(from_="main", to=m.member_id, content="你在吗？请回复 state 文件 status=working"))
    
    # 5. 等待回应（超时 30s）
    # 若全部失联 → 只能 archive_and_new
    
    engine._current_run = ctx
    engine._state = EngineState.RUNNING
    return True
```

### 14.3 不可恢复场景

- CodeBuddy Team 已被销毁（无法重连）
- runtime 文件损坏
- 配置已大幅变更（schema 版本不兼容）

这些情况回退到"归档 + 开新运行"。

---

## 15. 文件操作的统一契约

所有 runtime 文件的写入都必须使用 `ai_rd_team/shared/file_ops.py` 提供的函数：

| 文件类别 | 写入方法 | 原因 |
|---------|---------|------|
| `current-run.yaml` | `atomic_write` | 状态文件，读方需要完整性 |
| `state/*.yaml` | `atomic_write` | 同上 |
| `messages/*.json` | `safe_write` | 每文件独占，无竞争 |
| `events.jsonl` | `locked_append` | 多方追加 |
| `adapter-calls.jsonl` | `locked_append` | 同上 |
| `commands/pending/*.json` | `atomic_write` | 完整性 |
| `adapter-intents/*.json` | `atomic_write` | 完整性 |
| `adapter-results/*.json` | `atomic_write` | 完整性 |
| `cost/resource-points.yaml` | `atomic_write` | 状态文件 |
| `cost/*.jsonl` | `locked_append` | 多方追加 |

**严禁**：直接用 `open(path, 'w')` 写 runtime 文件（绕过锁 / 原子性）。

---

## 16. Schema 版本管理

所有 YAML/JSON 文件的**第一行字段**都必须是 `schema_version: "1.0"`。

升级流程：
1. 定义 migration（`0.9 → 1.0`）
2. 加载时检查版本
3. 不匹配 → 自动 migrate（备份原文件到 `.bak`）
4. 写入时总是用最新版本

---

## 17. 验收标准

- ✅ 所有运行时文件有明确 Schema（本文档定义）
- ✅ 每个文件明确读写方
- ✅ 并发策略（S1/S2/S3）按文件类型选定
- ✅ commands/pending 队列可被引擎正确轮询处理
- ✅ adapter-intents/results 配对工作（含超时）
- ✅ events.jsonl 覆盖 §8.3 所有事件类型
- ✅ archive 流程完整（summary + 快照）
- ✅ 断点续跑流程在原型阶段之外至少验证一次
- ✅ Schema 版本号校验生效
- ✅ 集成测试：跑一次 Standard 档，验证所有 runtime 文件正确产生

---

## 18. 对其他文档的接口

| 使用方 | 接口 |
|-------|-----|
| `01-engine.md` | RuntimeStateManager 实现本文档定义的读写 |
| `02-adapter.md` | Bridge 使用 adapter-intents/results |
| `03-service-api.md` | REST API 写 commands/pending |
| `04-web-panel.md` | Web 面板监听 runtime/ 下所有文件 |
| `07-artifacts.md` | artifacts/ 结构（本文档不重复） |
| `08-cost-control.md` | cost/ 目录结构 |
| `09-hooks-security.md` | events.jsonl 事件列表 |

---

## 19. 附录：完整示例（Standard 档运行片段）

启动 10 秒后 `runtime/` 快照：

```
.ai-rd-team/runtime/
├── current-run.yaml                (status=running, phase=design)
├── state/
│   ├── team.yaml                   (status=running)
│   ├── roster.yaml                 (5 members)
│   └── members/
│       ├── architect.yaml          (status=working, task="spec-architecture")
│       ├── developer_1.yaml        (status=idle)
│       ├── developer_2.yaml        (status=idle)
│       ├── reviewer.yaml           (status=idle)
│       └── tester.yaml             (status=idle)
├── messages/
│   └── 20260504-100000-main-architect.json  (启动消息)
├── events.jsonl                    (run_started / team_created / 5 × member_spawned / message_sent)
├── cost/
│   └── resource-points.yaml        (5 × 40 = 200 RP from spawns)
├── adapter-intents/                (已清空)
├── adapter-results/                (已清空)
├── commands/pending/               (空)
├── artifacts/
│   ├── requirements/               (空)
│   ├── design/                     (空，architect 还在写)
│   ├── code/                       (空)
│   ├── test/                       (空)
│   └── reports/                    (空)
└── logs/
    ├── engine.log                  (启动日志)
    └── adapter-calls.jsonl         (team_create + 5 × task + send_message)
```

约 1 分钟后：

```
├── artifacts/design/
│   ├── spec-architecture.md        (architect 写的)
│   └── data-interfaces.yaml        (architect 写的)
├── messages/
│   ├── 20260504-100000-main-architect.json
│   ├── 20260504-100045-architect-developer_1.json   (接口就绪)
│   └── 20260504-100045-architect-developer_2.json
├── state/members/
│   ├── architect.yaml              (status=done)
│   ├── developer_1.yaml            (status=working, task="实现 API-USER-001")
│   └── developer_2.yaml            (status=working, task="实现 API-USER-002")
└── ...
```
