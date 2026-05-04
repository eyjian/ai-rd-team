# ai-rd-team 详细设计 - 09 Hook 与安全

> 文档版本：v1.0
> 日期：2026-05-04
> 颗粒度：架构级
> 依赖：`00-overview.md`、`01-engine.md`、`10-config-schema.md`、`11-runtime-protocol.md`

---

## 1. 目的与范围

### 1.1 目的
定义 **Hook 机制**（用户可在关键节点插入自定义脚本）和 **安全约束**（防止成员做危险操作）。这两块放在一起是因为它们都关心"跨组件的横切关注点"。

### 1.2 范围
- Hook 触发点清单
- Hook 执行机制（环境变量、优先级、失败策略）
- 内置 Hook
- 安全约束（命令 / 文件 / 网络 / 敏感数据）
- 安全策略的执行位置

### 1.3 非目标
- ❌ 沙箱隔离（第一期不做进程沙箱，依赖 CodeBuddy 自带机制）
- ❌ 审计日志的深度分析（日志只是追加，分析由人工或 Web 展示做）

---

## 2. Hook 机制

### 2.1 触发点清单

基于头脑风暴 §20 + 各模块的需要：

#### 运行生命周期

| Hook | 触发时机 | 环境变量（部分） |
|------|---------|---------------|
| `run_starting` | 引擎 start_run 前置 | `RUN_ID`, `REQUIREMENT`, `MODE` |
| `run_started` | 引擎 start_run 成功后 | `RUN_ID`, `TEAM_ID`, `MEMBER_COUNT` |
| `run_paused` | pause_run | `RUN_ID`, `REASON` |
| `run_resumed` | resume_run | `RUN_ID` |
| `run_stopping` | stop_run 前置 | `RUN_ID`, `REASON` |
| `run_stopped` | stop_run 完成 | `RUN_ID`, `REASON`, `DURATION_MINUTES` |
| `run_upgraded` | escalate 成功 | `OLD_MODE`, `NEW_MODE` |

#### 团队与成员

| Hook | 触发时机 |
|------|---------|
| `team_creating` / `team_created` / `team_deleting` / `team_deleted` | 团队生命周期 |
| `member_spawning` / `member_spawned` | 成员派发 |
| `member_shutdown_requesting` | 请求关闭 |
| `member_status_changed` | state 文件被成员更新时 |
| `member_failed` | 成员失败 |

#### 阶段

| Hook | 触发时机 |
|------|---------|
| `phase_starting` | PM 宣告进入新阶段 |
| `phase_complete` | PM 宣告阶段完成 |

#### 制品与记忆

| Hook | 触发时机 |
|------|---------|
| `artifact_written` | 任何制品写入 |
| `adr_written` | 新 ADR 产出 |
| `memory_updated` | memory/ 任何文件被更新 |

#### 成本

| Hook | 触发时机 |
|------|---------|
| `budget_threshold_reached` | 75% 阈值 |
| `budget_exceeded` | 100% 触达 |
| `quota_{day/week/month}_warning` | 80% 窗口警告 |
| `quota_{day/week/month}_blocked` | 超限 |
| `model_fallback_suggested` | 建议切换模型 |
| `model_switched` | 用户确认已切 |

#### 工具

| Hook | 触发时机 |
|------|---------|
| `pre_tool_use` | 成员执行工具前 |
| `post_tool_use` | 成员执行工具后 |
| `tool_blocked` | 工具被 security 拦截 |

---

### 2.2 Hook 配置（`config.advanced.yaml` 中）

```yaml
hooks:
  enabled: true
  
  # 内置开关
  builtin:
    log_every_message: true
    auto_save_state: true
    cost_tracker: true
    git_auto_commit_on_phase: false
  
  # 自定义 Hook
  custom:
    - name: "notify-feishu-on-complete"
      trigger: "run_stopped"
      priority: 50                   # 数字越小越先执行
      command: "python scripts/feishu_notify.py"
      env:                           # 注入到执行环境
        WEBHOOK_URL: "${FEISHU_WEBHOOK}"  # 从环境变量替换
        RUN_ID: "${RUN_ID}"          # 从触发上下文
      on_failure: "warn"             # warn / block / ignore
      timeout_seconds: 30
    
    - name: "scan-for-secrets"
      trigger: "artifact_written"
      priority: 10                   # 安全类优先级高
      command: "python scripts/scan_secrets.py --path=${ARTIFACT_PATH}"
      env:
        ARTIFACT_PATH: "${ARTIFACT_PATH}"
      on_failure: "block"            # 发现密钥则阻断
      timeout_seconds: 10
    
    - name: "deploy-on-phase-deploy-done"
      trigger: "phase_complete"
      priority: 100
      when:                          # 条件过滤
        phase: "deployment"
      command: "bash deploy/publish.sh"
      env:
        ENV: "staging"
      on_failure: "warn"
      timeout_seconds: 600
```

### 2.3 Hook 执行机制

#### 优先级

同一 trigger 的多个 Hook 按 `priority` 升序执行（小的先）。内置 Hook 固定 priority 区间 1-99，用户 Hook 默认 100+。

#### 环境变量注入

Hook 执行时注入：

**固定变量**（所有 Hook 都有）：
- `AI_RD_TEAM_WORKSPACE`：工作区路径
- `AI_RD_TEAM_RUNTIME_DIR`：runtime 目录
- `AI_RD_TEAM_HOOK_NAME`：当前 Hook 名
- `AI_RD_TEAM_TRIGGER`：触发点名

**上下文变量**（根据 trigger 不同）：
- `run_*`：`RUN_ID`, `MODE`, `REASON`...
- `member_*`：`MEMBER_ID`, `ROLE`, `DISPLAY_NAME`...
- `artifact_*`：`ARTIFACT_PATH`, `PRODUCER`, `CATEGORY`...
- `budget_*`：`RP_USED`, `RP_LIMIT`, `THRESHOLD`...

**用户自定义**：`env:` 中声明，支持 `${VAR}` 语法（从环境或 context 替换）。

#### 超时与失败

| on_failure | 行为 |
|-----------|------|
| `ignore` | 失败记录日志，继续引擎流程 |
| `warn` | 失败记录日志 + 通知用户，继续引擎流程 |
| `block` | 失败抛异常，阻断当前引擎操作 |

超时时按 `on_failure` 同样处理。

**安全原则**：`block` 级 Hook **只允许内置或经过审核的自定义 Hook**。引擎对 `block` Hook 做额外校验（详见 §3.5）。

### 2.4 HookRunner 接口

```python
class HookRunner:
    """Hook 执行器。"""
    
    def __init__(
        self,
        hooks_config: dict,
        workspace: Path,
    ):
        self.config = hooks_config
        self.workspace = workspace
        self._registered: dict[str, list[HookDef]] = {}  # trigger → hooks
        self._load_builtin()
        self._load_custom()
    
    def trigger(
        self,
        trigger: str,
        **context,
    ) -> list["HookResult"]:
        """触发某个 Hook 点，执行所有注册到该点的 Hook。"""
        results = []
        for hook in self._registered.get(trigger, []):
            if not self._check_when(hook, context):
                continue
            result = self._execute(hook, context)
            results.append(result)
            if result.failed and hook.on_failure == "block":
                raise HookBlockedException(hook.name, result.error)
        return results
    
    def _execute(self, hook: "HookDef", context: dict) -> "HookResult":
        """执行单个 Hook。"""
        # 1. 组装环境变量
        env = os.environ.copy()
        env.update(self._base_env())
        env.update(self._context_env(context))
        env.update(self._user_env(hook.env, context))
        
        # 2. 安全校验（block 级 Hook 额外检查）
        if hook.on_failure == "block":
            self._validate_block_hook(hook)
        
        # 3. 执行
        try:
            proc = subprocess.run(
                hook.command,
                shell=True,
                env=env,
                timeout=hook.timeout_seconds,
                capture_output=True,
                text=True,
            )
            return HookResult(
                hook_name=hook.name,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                failed=proc.returncode != 0,
            )
        except subprocess.TimeoutExpired as e:
            return HookResult(
                hook_name=hook.name,
                exit_code=-1,
                failed=True,
                error=f"Timeout after {hook.timeout_seconds}s",
            )
        except Exception as e:
            return HookResult(
                hook_name=hook.name,
                exit_code=-1,
                failed=True,
                error=str(e),
            )
```

### 2.5 内置 Hook 示例

| Hook | 触发点 | 作用 |
|------|-------|------|
| `log_every_message` | `message_sent` | 写消息到 runtime/messages/ |
| `auto_save_state` | `member_status_changed` | 更新 state/members/*.yaml |
| `cost_tracker` | `member_spawned`, `message_sent`, `iteration_complete` | 更新 cost/resource-points.yaml |
| `events_emitter` | 所有 hook | 追加到 events.jsonl |
| `git_auto_commit_on_phase` | `phase_complete`（当 builtin.git_auto_commit=true） | `git add -A && git commit` |

---

## 3. 安全约束

### 3.1 命令白/黑名单

```yaml
security:
  commands:
    allowed: []              # 空表示不限
    blocked:
      - "rm -rf /"
      - "rm -rf ~"
      - "rm -rf .git"
      - "sudo *"
      - "curl * | sh"
      - "wget * | sh"
      - "> /etc/*"
      - "chmod 777 *"
      - ":(){ :|:& };:"      # fork 炸弹
      - "dd if=/dev/zero"
```

**实现**：
- CodeBuddy 本身有 `bypassPermissions` 模式（我们用这个），但仍需二次校验
- 引擎监听 `adapter-intents/` 里的 `op` 相关内容 → 若有命令执行类意图（如通过 task 执行 bash），校验命令
- 若违反 → 触发 `tool_blocked` Hook + 拒绝执行

### 3.2 文件访问规则

```yaml
security:
  file_access:
    writable:              # 成员可写
      - "<workspace>/**"                   # 项目内
      - "<workspace>/.ai-rd-team/runtime/**"
    readonly:              # 只读
      - "<workspace>/.git/**"
      - "<workspace>/.ai-rd-team/memory/decisions/**"  # ADR 只能 append 新增，不能改旧的
    forbidden:             # 禁止访问
      - "/etc/**"
      - "/usr/**"
      - "~/.ssh/**"
      - "~/.aws/**"
      - "~/.kube/**"
      - "~/.docker/config.json"
```

**实现**：
- 通过 PromptRenderer 把这些约束**写入成员 prompt**（第一级防线，靠成员自律）
- 通过 `pre_tool_use` Hook 监听 Write / Edit 工具调用，校验 path（第二级防线）
- 通过 FileWatcher 监听 runtime/ 外的异常写入 → 告警（第三级，事后发现）

### 3.3 网络访问

```yaml
security:
  network:
    allowed_hosts: []      # 空 = 不限
    blocked_hosts:
      - "*.malicious.com"
      - "127.0.0.1:22"     # 禁止 SSH 本机
```

**实现**：
- 第一期：仅通过 prompt 约束 + `pre_tool_use` 校验（不做真沙箱）

### 3.4 敏感数据脱敏

```yaml
security:
  sensitive_data:
    mask_in_logs: true
    patterns:
      - 'sk-[a-zA-Z0-9]{32,}'           # OpenAI / Anthropic key
      - 'ghp_[a-zA-Z0-9]{36,}'          # GitHub token
      - 'xox[bpoa]-[a-zA-Z0-9-]+'       # Slack
      - '\d{16,19}'                     # 银行卡号
      - '\d{15,18}'                     # 身份证
      - '1[3-9]\d{9}'                   # 手机号
      - 'AKIA[0-9A-Z]{16}'              # AWS access key
      - '-----BEGIN PRIVATE KEY-----'   # PEM
    
    apply_to:
      - logs                 # engine.log / adapter-calls.jsonl
      - messages             # runtime/messages/*.json
      - events               # events.jsonl
      - memory_global        # 全局 memory 写入前拦截
```

**实现**：
- 写任何受保护位置前先脱敏（替换为 `[REDACTED]`）
- 可配置"阻断而非脱敏"（对全局 memory 严格）

### 3.5 block 级 Hook 的额外校验

用户自定义的 `on_failure: block` Hook 具备阻断引擎的能力，风险高。引擎在执行前额外校验：

- Hook command 必须在工作区内（`./scripts/*`）或绝对路径白名单
- 禁止执行非脚本类（如 `rm` 直接作为 command）
- 第一次注册 block Hook 时 Web 面板弹窗确认

### 3.6 安全的执行位置

| 安全检查 | 在哪执行 |
|---------|---------|
| 命令黑名单 | Adapter Bridge 拦截（`pre_tool_use` Hook） |
| 文件路径 | ArtifactRecorder / MemoryManager 写入前校验 |
| 敏感数据 | Logger / MessageRecorder / MemoryWriter 写入前 |
| Hook block 白名单 | HookRunner._validate_block_hook |
| 网络 | `pre_tool_use` Hook（若成员要 curl） |

### 3.7 安全违规的处理

```
违规发生
    ↓
写 events.jsonl: {event: "security_violation", ...}
    ↓
触发 `tool_blocked` Hook
    ↓
Web 面板弹窗告警（显示被拦截的操作 + 原因）
    ↓
根据违规类型决定：
  - 严重（如 rm -rf /）→ 立即 pause_run + 等用户介入
  - 中等（如写只读文件）→ 记录 + 告知发起成员（"你违反了 xx 规则"）
  - 轻微（如读取大文件）→ 仅记录
```

---

## 4. 典型集成场景

### 4.1 评审阶段自动跑 linter

```yaml
hooks:
  custom:
    - name: "auto-lint-on-review"
      trigger: "phase_starting"
      when: {phase: "review"}
      command: "ruff check src/"
      on_failure: "warn"
      timeout_seconds: 60
```

### 4.2 每次运行结束发飞书

```yaml
hooks:
  custom:
    - name: "feishu-on-complete"
      trigger: "run_stopped"
      command: "python scripts/feishu.py --run_id=${RUN_ID} --reason=${REASON}"
      env:
        FEISHU_WEBHOOK: "${FEISHU_WEBHOOK}"
      on_failure: "warn"
```

### 4.3 制品扫描密钥

```yaml
hooks:
  custom:
    - name: "scan-secrets"
      trigger: "artifact_written"
      priority: 10
      command: "gitleaks detect --source=${ARTIFACT_PATH} --no-git"
      on_failure: "block"        # 发现密钥则阻断
      timeout_seconds: 30
```

### 4.4 预算超 50% 通知值班人

```yaml
hooks:
  custom:
    - name: "notify-on-budget-half"
      trigger: "budget_threshold_reached"
      when: {threshold: 0.5}
      command: "python scripts/alert.py --msg='预算过半'"
      on_failure: "ignore"
```

---

## 5. 验收标准

- ✅ Hook 触发点按 §2.1 清单全部覆盖
- ✅ 自定义 Hook 能注册、执行、按优先级排序
- ✅ Hook 环境变量注入正确
- ✅ 三种 `on_failure` 策略工作正确
- ✅ 内置 Hook（cost / state / events）跑通
- ✅ 命令黑名单能拦截危险命令
- ✅ 文件访问超范围能被 ArtifactRecorder 拦截
- ✅ 敏感数据脱敏在 logs/messages/events 生效
- ✅ block 级 Hook 有额外白名单校验
- ✅ 安全违规能被 Web 面板可见
- ✅ 单元测试覆盖 ≥ 80%（触发点、失败策略、脱敏、路径校验）

---

## 6. 对其他文档的接口

| 使用方 | 接口 |
|-------|-----|
| `01-engine.md` | Engine 组合 HookRunner 并在关键时机 trigger |
| `02-adapter.md` | Bridge 在工具调用前做 `pre_tool_use` Hook |
| `07-artifacts.md` | ArtifactRecorder 用 security.file_access 校验 |
| `06-memory-system.md` | MemoryManager 写全局 memory 时做敏感数据校验 |
| `08-cost-control.md` | budget / quota / fallback Hook |
| `10-config-schema.md` | hooks / security 配置定义 |
| `11-runtime-protocol.md` | events.jsonl 事件列表 |

---

## 7. 附录：Hook 最佳实践

1. **保持简短**：Hook 脚本应在秒级完成，避免阻塞引擎
2. **幂等**：同一 Hook 可能因重试多次执行，结果应一致
3. **日志**：Hook 脚本自己也应打日志（stdout/stderr 会被引擎捕获）
4. **不要依赖 runtime 临时状态**：Hook 可能在引擎停止后才执行
5. **block 慎用**：仅用于必须阻断的场景（如密钥泄露）
6. **环境变量优先**：不要在 Hook 里读 config.yaml（版本可能和引擎不一致）
