# ai-rd-team 详细设计 - 10 配置 Schema

> 文档版本：v1.0
> 日期：2026-05-03
> 颗粒度：**实现级**
> 依赖：`00-overview.md`

---

## 1. 目的与范围

### 1.1 目的
定义 ai-rd-team 的配置文件完整 Schema、加载优先级、校验规则、版本迁移策略。配置是用户与系统交互的主要界面之一，必须**清晰、可预测、可校验**。

### 1.2 范围
- `config.yaml`（项目/全局配置）
- `pricing.yaml`（模型价格表，可选）
- `presets/*.yaml`（档位预设）
- 运行时态的 `team.yaml`、`members/*.yaml`（只在本文件中引用，详见 `11-runtime-protocol.md`）

### 1.3 非目标
- ❌ 具体字段在业务逻辑中如何使用（由各模块文档定义）
- ❌ UI 配置编辑器（由 `04-web-panel.md` 定义）

---

## 2. 配置文件层级与优先级

### 2.1 两级配置

```
~/.ai-rd-team/config.yaml              # 全局配置（所有项目共享）
<workspace>/.ai-rd-team/config.yaml    # 项目配置（当前项目独有，优先）
```

### 2.2 合并策略

采用**深度合并 + 项目级覆盖全局级**：

- **标量字段**（string/number/bool）：项目级直接覆盖全局级
- **对象字段**（dict）：递归合并，同 key 项目级覆盖
- **数组字段**（list）：项目级**完全替换**全局级（不做 merge）

**为什么数组不合并**：避免用户困惑。例如全局定义了 5 个角色，项目级定义了 3 个角色，合并后是 5 还是 8？完全替换最直观。

### 2.3 缺省值

- 若全局和项目都未配置，使用代码内置默认值
- 默认值在 `defaults.yaml`（随代码分发，不允许用户编辑）

### 2.4 加载流程

```
1. 读取 defaults.yaml（代码内置）
2. 读取 ~/.ai-rd-team/config.yaml（全局，若存在）
3. 读取 <workspace>/.ai-rd-team/config.yaml（项目，若存在）
4. 按 §2.2 规则合并：defaults < global < project
5. 应用档位 preset（若启动时选择了档位）
6. JSON Schema 校验（见 §6）
7. 配置版本迁移（若需要，见 §7）
8. 最终产出 EffectiveConfig 对象
```

---

## 3. config.yaml 完整 Schema

### 3.1 顶层结构

```yaml
# 配置版本（用于升级迁移）
config_version: "1.0"

# 项目信息
project:
  name: string                        # 项目名
  description: string                 # 项目描述
  workspace: string                   # 工作空间路径（默认当前目录）

# 规则（全局行为约束）
rules:
  proposal:
    - 使用中文撰写
    - 必须包含"非目标"部分
  tasks:
    - 每个任务不超过 4 小时工作量

# 知识库引用
knowledge_base:
  enabled: bool
  base_path: string                   # 默认 .ai-rd-team/memory/

# 角色配置
roles: {...}                          # 见 §3.2

# 技术栈（非硬性约束，供架构师参考）
tech_stack:
  proficiency:                        # 团队熟练度
    go: expert
    python: proficient
    vue3: expert
    wechat-miniprogram: proficient
  preferences:                        # 偏好
    backend: go-kratos
    frontend-pc: vue3
    frontend-mobile: wechat-miniprogram

# 适配器配置
adapter:
  type: "codebuddy"                   # codebuddy / trae / qoder
  version: "auto"                     # auto 或指定版本
  options: {}                         # Adapter 特定选项

# 环境约束
environment:
  os_supported: ["linux", "darwin", "windows"]
  python_min: "3.11"
  auto_install_dependencies: true     # 启动时自动安装运行环境

# 团队运行参数
team:
  interaction_mode: "auto"            # auto / delegate / manual
  safety_limits: {...}                # 见 §3.3
  health_check: {...}                 # 见 §3.4

# 安全约束
security: {...}                       # 见 §3.5

# Web 面板
web:
  enabled: true
  host: "127.0.0.1"
  port: 8765
  auth:
    enabled: false                    # 第一期不强制
    token: null

# Hooks
hooks: {...}                          # 见 §3.6

# 通知
notifications: {...}                  # 见 §3.7

# 质量门禁
quality_gates: {...}                  # 见 §3.8

# 日志
logging: {...}                        # 见 §3.9

# 资源限制（传统，与 cost_control 并行）
resource_limits: {...}                # 见 §3.10

# 成本控制（新增，核心）
cost_control: {...}                   # 见 §3.11

# 工具集成
tools: {...}                          # 见 §3.12
```

---

### 3.2 roles 结构

```yaml
roles:
  # 7 固定角色
  pm:                                 # 项目经理
    enabled: bool                     # 是否启用
    display_name: string              # 展示名（中文名）
    persona: string                   # 人设描述（200 字以内）
    scalable: false                   # 是否可伸缩（单实例）
    skills:                           # 加载的 Skills
      - builtin:pm-coordination
      - global:team-leadership
      - workspace:company-culture
    rules:                            # 角色专属规则
      - 必须在阶段完成后写工作报告
    memory_scope:                     # 记忆范围
      agent_d: ["team-roster", "current-phase"]
      memory_d_topics: ["project-timeline", "stakeholders"]
    model: null                       # 运行时模型（第一期不生效，记录意图）

  analyst:                            # 需求分析师
    enabled: bool
    display_name: string
    persona: string
    scalable: false
    skills: [...]
    rules: [...]
    memory_scope: {...}
    model: null

  architect:                          # 架构师
    enabled: bool
    display_name: string
    persona: string
    scalable: false
    skills: [...]
    rules: [...]
    memory_scope: {...}
    model: null

  developer:                          # 开发者（可伸缩）
    enabled: bool
    display_name_template: string     # e.g. "林{index}号"
    persona: string
    scalable: true
    max_instances: 5                  # 最大实例数
    default_instances: 2              # 默认实例数
    skills: [...]
    rules: [...]
    memory_scope: {...}
    model: null

  reviewer:                           # 代码检视者（可伸缩）
    enabled: bool
    display_name_template: string
    persona: string
    scalable: true
    max_instances: 3
    default_instances: 1
    skills: [...]
    rules: [...]
    memory_scope: {...}
    model: null

  tester:                             # 测试工程师（可伸缩）
    enabled: bool
    display_name_template: string
    persona: string
    scalable: true
    max_instances: 3
    default_instances: 1
    skills: [...]
    rules: [...]
    memory_scope: {...}
    model: null

  devops:                             # DevOps
    enabled: bool
    display_name: string
    persona: string
    scalable: false
    skills: [...]
    rules: [...]
    memory_scope: {...}
    model: null

  # 用户自定义角色（可选）
  custom:
    - name: "security_auditor"
      display_name: "柳安全"
      persona: "..."
      scalable: false
      skills: [...]
      rules: [...]
```

**字段约束**：
- `enabled`：默认 true
- `scalable`：布尔值；scalable=true 时必须有 `max_instances` 和 `default_instances`
- `skills`：格式 `<scope>:<skill-name>`，scope ∈ {builtin, global, workspace}
- `model`：第一期为 null（记录意图但不生效）

---

### 3.3 safety_limits 结构

```yaml
safety_limits:
  review_max_rounds: 3                # 单次评审最大轮次
  fix_max_iterations: 3               # 修复最大迭代
  escalation_timeout_minutes: 30      # 人类介入超时
  max_member_idle_minutes: 15         # 成员闲置超时 → 提示或关闭
```

---

### 3.4 health_check 结构

```yaml
health_check:
  stuck_threshold_minutes: 30         # 卡住检测阈值
  max_retry_on_error: 3               # 出错最大重试
  on_member_stuck: "pm_intervene"     # pm_intervene / human_escalate / restart
  heartbeat_interval_seconds: 30      # 健康检查心跳间隔
```

---

### 3.5 security 结构

```yaml
security:
  commands:
    allowed: []                       # 白名单（空表示不限）
    blocked:                          # 黑名单
      - "rm -rf /"
      - "sudo *"
      - "curl * | sh"
      - "> /etc/*"
  
  file_access:
    writable:                         # 成员可写范围
      - "<workspace>/src/**"
      - "<workspace>/.ai-rd-team/runtime/**"
    readonly:                         # 只读
      - "<workspace>/.git/**"
      - "<workspace>/config/secrets/**"
    forbidden:                        # 禁止访问
      - "/etc/**"
      - "~/.ssh/**"
  
  network:
    allowed_hosts: []                 # 空 = 不限
    blocked_hosts:
      - "*.malicious.com"
  
  sensitive_data:
    mask_in_logs: true                # 日志中脱敏
    patterns:                         # 脱敏模式
      - 'sk-[a-zA-Z0-9]{32,}'         # API key
      - '\d{16,19}'                   # 银行卡号
```

---

### 3.6 hooks 结构

```yaml
hooks:
  enabled: true
  
  # 内置 hook 开关
  builtin:
    log_every_message: true           # 记录每条消息
    auto_save_state: true             # 定期保存状态
    cost_tracker: true                # 成本追踪
  
  # 用户自定义 hook
  custom:
    - name: "git_commit_on_phase_complete"
      trigger: "phase_complete"       # 见 §09-hooks 定义的 trigger 列表
      priority: 50                    # 执行优先级
      command: "bash .ai-rd-team/hooks/auto-commit.sh"
      env:
        HOOK_PHASE: "${phase_name}"
      on_failure: "warn"              # warn / block / ignore
```

---

### 3.7 notifications 结构

```yaml
notifications:
  enabled: true
  
  channels:
    web_panel:
      enabled: true
      events: ["all"]                 # 所有事件
    
    console:
      enabled: true
      events: ["error", "phase_complete"]
    
    qq_bot:                           # 第二期
      enabled: false
      webhook: null
    
    wechat_bot:                       # 第二期
      enabled: false
      webhook: null
  
  event_filters:
    min_severity: "info"              # debug / info / warn / error
```

---

### 3.8 quality_gates 结构

```yaml
quality_gates:
  code_review:
    max_blocker_issues: 0
    max_major_issues: 3
    require_all_blockers_fixed: true
  
  testing:
    min_pass_rate: 0.95
    max_blocker_bugs: 0
    max_critical_bugs: 0
    require_all_cases_executed: true
  
  unit_testing:
    min_coverage: 0.80
    enforce_on: ["backend", "core-lib"]
  
  architecture_review:
    required: true
    require_diagrams: true            # 必须有类图/时序图
```

---

### 3.9 logging 结构

```yaml
logging:
  level: "info"                       # debug / info / warn / error
  
  # 文件日志
  file:
    enabled: true
    path: ".ai-rd-team/runtime/logs/engine.log"
    max_file_size_mb: 50
    max_files: 10                     # 滚动文件数
  
  # 控制台
  console:
    enabled: true
    format: "colorful"                # plain / json / colorful
  
  # 敏感内容
  log_member_prompts: false           # 是否记录成员 prompt 全文
  log_member_responses: true
  log_message_content: true
```

---

### 3.10 resource_limits 结构

```yaml
resource_limits:
  max_total_time_minutes: 480         # 全局时长上限
  max_phase_time_minutes: 120         # 单阶段时长
  max_concurrent_members: 10          # 并发成员数
  max_total_review_rounds: 10
  max_total_fix_iterations: 15
  on_limit_exceeded: "pause"          # pause / terminate / notify_human
```

---

### 3.11 cost_control 结构（核心）

```yaml
cost_control:
  enabled: true
  
  # 计费模式
  billing_mode: "auto"                # auto / subscription / resource_units / estimated_cost / central_quota
  
  # 首次启动询问
  confirm_on_startup: true            # 首次启动问用户（记住选择）
  
  # 展示
  show_cost_in_ui: "auto"             # auto / always / never
  display_currency: "auto"            # auto / CNY / USD
  confirm_currency_on_startup: true
  
  # Resource Points 权重（v1，基于 P5 校准）
  resource_point_weights:
    per_member_spawn: 40
    per_message: 2
    per_broadcast_target: 2
    per_minute_runtime: 5
    per_iteration: 15
    version: "v1"                     # 权重版本，用于跟踪
  
  # 档位预算
  budget_lite:
    max_members: 2
    max_messages: 30
    max_broadcasts: 0
    max_runtime_minutes: 30
    max_total_iterations: 5
    max_resource_points: 120
  
  budget_standard:
    max_members: 5
    max_messages: 150
    max_broadcasts: 3
    max_runtime_minutes: 120
    max_total_iterations: 15
    max_resource_points: 400
  
  budget_full:
    max_members: 15
    max_messages: 500
    max_broadcasts: 10
    max_runtime_minutes: 480
    max_total_iterations: 50
    max_resource_points: 1500
  
  # 超限行为
  on_budget_exceeded: "smart_pause"   # smart_pause / pause_and_ask / warn_only / terminate
  
  # 时间窗口额度
  quota:
    enabled: true
    unit: "resource_points"
    windows:
      per_run: 400                    # 通常 = 档位预算
      per_day: 2000
      per_week: 10000
      per_month: 30000
    on_exceed:
      per_run: "smart_pause"
      per_day: "block_new_run"
      per_week: "warn_and_block"
      per_month: "block_and_report"
    tracking:
      storage: "~/.ai-rd-team/quota-history.jsonl"
      report_on_startup: true
    central:                          # 第二期
      enabled: false
      endpoint: null
      policy_sync: true
      user_id_from: "env.USER_EMAIL"
  
  # 模型降级
  model_fallback:
    enabled: true
    fallback_mode: "auto"             # auto / semi_auto / full_auto / disabled
    trigger_threshold: 0.75
    strategy: "hybrid"                # hybrid / cascade / role_based
    model_chain:
      - "claude-sonnet-4"
      - "claude-haiku"
      - "deepseek-v3"
      - "local-qwen"
    role_priority:
      log_writer: 1
      tester: 2
      reviewer: 3
      developer: 4
      architect: 5
      pm: 5
    on_trigger: "auto"                # auto / ask / notify_only
  
  # 事后记录
  post_run_recording:
    enabled: true
    prompt_user: true                 # 运行结束引导用户填入真实消耗
    storage: ".ai-rd-team/runtime/cost/post-run.jsonl"
  
  # 档位
  default_mode: "ask"                 # ask（首次启动问）/ lite / standard / full
  remembered_mode: null               # 上次选择（自动写入）
```

---

### 3.12 role_models 结构

```yaml
role_models:
  enabled: true
  warning_if_unsupported: true        # 当前 Adapter 不支持时警告
  config:
    architect: "claude-sonnet-4"
    pm: "claude-sonnet-4"
    analyst: "claude-sonnet-4"
    developer: "claude-sonnet-4"
    reviewer: "claude-haiku"
    tester: "claude-haiku"
    log_writer: "local-qwen"
```

---

### 3.13 tools 结构

```yaml
tools:
  git:
    auto_commit_on_phase: false
    commit_message_template: "[ai-rd-team] {phase} by {members}"
  
  linter:
    python: "ruff"
    go: "golangci-lint"
    typescript: "eslint"
  
  formatter:
    python: "black"
    go: "gofmt"
    typescript: "prettier"
  
  test_runner:
    python: "pytest"
    go: "go test"
    typescript: "vitest"
  
  mcp_servers: []                     # 第一期不强依赖
```

---

## 4. pricing.yaml 结构

```yaml
# ~/.ai-rd-team/pricing.yaml（可选，仅 billing_mode=estimated_cost 时用）
display_currency: "CNY"               # 全局默认币种

models:
  claude-sonnet-4:
    input_per_1m:
      USD: 3.0
      CNY: 21.0
    output_per_1m:
      USD: 15.0
      CNY: 105.0
  
  claude-haiku:
    input_per_1m:
      USD: 0.25
      CNY: 1.75
    output_per_1m:
      USD: 1.25
      CNY: 8.75
  
  gpt-4o:
    input_per_1m:
      USD: 2.5
      CNY: 17.5
    output_per_1m:
      USD: 10.0
      CNY: 70.0
  
  deepseek-v3:
    input_per_1m:
      USD: 0.27
      CNY: 1.9
    output_per_1m:
      USD: 1.1
      CNY: 7.7
  
  local-qwen:
    input_per_1m:
      USD: 0
      CNY: 0
    output_per_1m:
      USD: 0
      CNY: 0

fx_rate:
  USD_to_CNY: 7.0
  last_updated: "2026-05-01"
```

---

## 5. presets/*.yaml 结构

预设档位配置，按档位加载覆盖用户配置。

### 5.1 lite.yaml

```yaml
# ~/.ai-rd-team/presets/lite.yaml
preset_name: "lite"
description: "精简模式：单开发者 + 可选测试"

roles:
  pm: { enabled: false }
  analyst: { enabled: false }
  architect: { enabled: false }
  developer:
    enabled: true
    default_instances: 1
  reviewer: { enabled: false }
  tester:
    enabled: true                     # 可选，用户可自行关闭
    default_instances: 1
  devops: { enabled: false }

team:
  interaction_mode: "auto"
  safety_limits:
    review_max_rounds: 1

cost_control:
  default_mode: "lite"
  # 使用 budget_lite
```

### 5.2 standard.yaml

```yaml
preset_name: "standard"
description: "标准模式：架构师 + 开发 + 检视 + 测试"

roles:
  pm: { enabled: false }
  analyst: { enabled: false }
  architect: { enabled: true }
  developer:
    enabled: true
    default_instances: 2
  reviewer:
    enabled: true
    default_instances: 1
  tester:
    enabled: true
    default_instances: 1
  devops: { enabled: false }

cost_control:
  default_mode: "standard"
```

### 5.3 full.yaml

```yaml
preset_name: "full"
description: "完整模式：全角色 + 可伸缩"

roles:
  pm: { enabled: true }
  analyst: { enabled: true }
  architect: { enabled: true }
  developer:
    enabled: true
    default_instances: 3
  reviewer:
    enabled: true
    default_instances: 2
  tester:
    enabled: true
    default_instances: 2
  devops: { enabled: true }

cost_control:
  default_mode: "full"
```

---

## 6. JSON Schema 校验

### 6.1 校验时机
1. 加载配置后立即校验
2. Web 面板保存配置前校验
3. 发布前（CI）校验示例配置

### 6.2 校验规则（关键项）

```python
# 伪代码
CONFIG_SCHEMA = {
    "type": "object",
    "required": ["config_version", "project", "adapter"],
    "properties": {
        "config_version": {"type": "string", "pattern": r"^\d+\.\d+$"},
        "project": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string", "minLength": 1, "maxLength": 100},
            },
        },
        "adapter": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"enum": ["codebuddy", "trae", "qoder"]},
            },
        },
        "cost_control": {
            "type": "object",
            "properties": {
                "billing_mode": {"enum": ["auto", "subscription", "resource_units", "estimated_cost", "central_quota"]},
                "resource_point_weights": {
                    "type": "object",
                    "properties": {
                        "per_member_spawn": {"type": "integer", "minimum": 1},
                        "per_message": {"type": "integer", "minimum": 1},
                        "per_broadcast_target": {"type": "integer", "minimum": 1},
                        "per_minute_runtime": {"type": "integer", "minimum": 1},
                        "per_iteration": {"type": "integer", "minimum": 1},
                    },
                },
            },
        },
        # ... 其他字段
    },
}
```

### 6.3 校验错误处理

| 错误类型 | 处理 |
|---------|------|
| 必填字段缺失 | 致命，终止启动，提示用户 |
| 字段类型错误 | 致命 |
| 字段值越界 | 警告 + 用边界值替代（如 max_instances > 允许上限） |
| 未知字段 | 警告但不终止（允许用户扩展） |

---

## 7. 配置版本迁移

### 7.1 版本号规则

`config_version: "major.minor"`

- `major` 变化：不兼容变更，需要用户干预
- `minor` 变化：向后兼容，自动迁移

### 7.2 迁移流程

```python
# 伪代码
def migrate_config(config: dict) -> dict:
    current_version = config.get("config_version", "1.0")
    target_version = LATEST_CONFIG_VERSION
    
    while current_version != target_version:
        migration = MIGRATIONS.get(current_version)
        if migration is None:
            raise ConfigMigrationError(f"No migration from {current_version}")
        
        config = migration.apply(config)
        current_version = migration.target_version
    
    return config

# 示例迁移：1.0 -> 1.1
class Migration_1_0_to_1_1:
    source_version = "1.0"
    target_version = "1.1"
    
    def apply(self, config):
        # 将旧的 resource_limits.max_token 字段拆分到 cost_control
        if "resource_limits" in config:
            old = config["resource_limits"].pop("max_token", None)
            if old:
                config.setdefault("cost_control", {})["max_tokens"] = old
        
        config["config_version"] = "1.1"
        return config
```

### 7.3 迁移安全

- 迁移前**备份原配置**到 `config.yaml.v{version}.bak`
- 迁移失败回滚备份
- 迁移成功写入日志

---

## 8. EffectiveConfig 对象（运行时表示）

加载完成后，所有模块通过 `EffectiveConfig` 对象访问配置。

### 8.1 类设计

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

@dataclass(frozen=True)  # 不可变，避免运行时修改
class ProjectInfo:
    name: str
    description: str
    workspace: Path


@dataclass(frozen=True)
class ResourcePointWeights:
    per_member_spawn: int = 40
    per_message: int = 2
    per_broadcast_target: int = 2
    per_minute_runtime: int = 5
    per_iteration: int = 15
    version: str = "v1"


@dataclass(frozen=True)
class Budget:
    max_members: int
    max_messages: int
    max_broadcasts: int
    max_runtime_minutes: int
    max_total_iterations: int
    max_resource_points: int


@dataclass(frozen=True)
class QuotaWindows:
    per_run: int
    per_day: int
    per_week: int
    per_month: int


@dataclass(frozen=True)
class CostControl:
    enabled: bool = True
    billing_mode: Literal["auto", "subscription", "resource_units", "estimated_cost", "central_quota"] = "auto"
    display_currency: str = "auto"
    resource_point_weights: ResourcePointWeights = field(default_factory=ResourcePointWeights)
    budget_lite: Budget = field(default_factory=...)
    budget_standard: Budget = field(default_factory=...)
    budget_full: Budget = field(default_factory=...)
    on_budget_exceeded: str = "smart_pause"
    quota_windows: QuotaWindows = field(default_factory=...)
    quota_on_exceed: dict = field(default_factory=dict)
    model_fallback: "ModelFallback" = field(default_factory=...)
    post_run_recording_enabled: bool = True
    default_mode: Literal["ask", "lite", "standard", "full"] = "ask"


@dataclass(frozen=True)
class Role:
    name: str
    enabled: bool
    display_name: str
    persona: str
    scalable: bool
    max_instances: int
    default_instances: int
    skills: list[str]
    rules: list[str]
    memory_scope: dict
    model: str | None = None


@dataclass(frozen=True)
class EffectiveConfig:
    config_version: str
    project: ProjectInfo
    roles: dict[str, Role]              # 按角色名索引
    tech_stack: dict
    adapter: dict
    environment: dict
    team: dict
    security: dict
    web: dict
    hooks: dict
    notifications: dict
    quality_gates: dict
    logging: dict
    resource_limits: dict
    cost_control: CostControl
    role_models: dict
    tools: dict
    
    # 元信息
    source_files: list[Path]            # 加载自哪些文件
    loaded_at: datetime
```

### 8.2 访问模式

```python
config = ConfigLoader().load(workspace=Path.cwd())

# 只读访问
config.project.name
config.cost_control.budget_standard.max_resource_points
config.roles["architect"].persona

# 不允许直接修改（frozen）
# 修改必须通过 ConfigLoader.save()，重新 load
```

### 8.3 派生计算

```python
@property
def current_budget(self) -> Budget:
    """根据当前运行档位返回对应预算。"""
    mode = self.cost_control.default_mode  # or from runtime state
    return {
        "lite": self.cost_control.budget_lite,
        "standard": self.cost_control.budget_standard,
        "full": self.cost_control.budget_full,
    }[mode]


def enabled_roles(self) -> list[Role]:
    """返回启用的角色列表。"""
    return [r for r in self.roles.values() if r.enabled]
```

---

## 9. ConfigLoader 接口

```python
class ConfigLoader:
    """配置加载器。"""
    
    def __init__(
        self,
        global_dir: Path = Path.home() / ".ai-rd-team",
        workspace_dir: Path | None = None,
    ):
        self.global_dir = global_dir
        self.workspace_dir = workspace_dir or Path.cwd() / ".ai-rd-team"
    
    def load(
        self,
        preset: Literal["lite", "standard", "full"] | None = None,
    ) -> EffectiveConfig:
        """加载配置。
        
        顺序：defaults → global → project → preset
        
        Raises:
            ConfigNotFoundError: 全局和项目配置都不存在
            ConfigValidationError: 校验失败
            ConfigMigrationError: 版本迁移失败
        """
        ...
    
    def save(self, config: EffectiveConfig, target: Literal["global", "project"]) -> None:
        """保存配置。"""
        ...
    
    def validate(self, raw: dict) -> list[str]:
        """仅校验，不加载。返回错误列表。"""
        ...
    
    def get_effective_source(self, key_path: str) -> Path:
        """查询某配置项的最终来源文件（调试用）。"""
        ...
```

---

## 10. 用户交互：首次启动配置

### 10.1 交互流程

若全局配置 `~/.ai-rd-team/config.yaml` 不存在，进入首次引导：

```
欢迎使用 ai-rd-team！
请回答几个问题以完成初始化：

1. 你的项目名称？
   > [输入]

2. 选择计费场景：
   [1] 我用订阅制（Claude Pro / CodeBuddy Plus）
   [2] 我按 token 付费（或公司有明确额度）
   [3] 公司统一管理
   [4] 我不确定，先用默认资源限制模式
   > [选择]

3. 选择展示币种：
   [1] 人民币 (CNY) ← 默认（基于 locale）
   [2] 美元 (USD)
   [3] 双币显示
   > [选择]

4. 每日使用额度（Resource Points）？
   默认 2000，相当于每天约 5 次 Standard 运行。
   > [数字或回车接受默认]

配置已保存到 ~/.ai-rd-team/config.yaml
```

### 10.2 每次启动前检查

- 若首次启动未完成 → 强制进入引导
- 若全局配置存在但项目配置不存在 → 询问是否继承全局 / 定制化
- 若配置版本过旧 → 提示迁移

---

## 11. 错误处理

### 11.1 典型错误

| 错误 | 类 | 处理 |
|------|---|------|
| 全局和项目都无配置 | ConfigNotFoundError | 启动首次引导 |
| YAML 语法错误 | YAMLSyntaxError | 打印错误行号，提示修复 |
| Schema 校验失败 | ConfigValidationError | 打印失败字段 + 建议值 |
| 未知 `adapter.type` | ConfigValueError | 列出支持的类型 |
| 版本迁移失败 | ConfigMigrationError | 回滚备份，提示人工处理 |
| 权限问题 | PermissionError | 清晰错误信息，不打印敏感路径 |

### 11.2 错误提示范例

```
❌ 配置错误
文件：<workspace>/.ai-rd-team/config.yaml
问题：roles.developer.max_instances 超出允许上限
当前值：100
允许范围：1-20
建议：将 max_instances 设置为 ≤ 20

是否自动修正为 20？[Y/n]
```

---

## 12. 验收标准

- ✅ 能加载 defaults + global + project 三级配置并正确合并
- ✅ JSON Schema 校验覆盖所有必填字段和关键约束
- ✅ 支持从 v1.0 到最新版的迁移
- ✅ 首次启动交互式引导可完成基础配置
- ✅ EffectiveConfig 对象不可变，线程安全
- ✅ 提供 3 份 preset（lite/standard/full）
- ✅ 单元测试覆盖 ≥ 80%（加载/合并/校验/迁移各路径）

---

## 13. 附录：配置示例文件

将提供 3 份完整示例：
- `examples/config-minimal.yaml`：最小配置
- `examples/config-standard.yaml`：中等复杂度配置
- `examples/config-full.yaml`：覆盖所有字段的完整配置

（示例文件在实现阶段产出）

---

## 14. 对其他文档的接口

| 使用方 | 接口 |
|-------|-----|
| `01-engine.md` | `ConfigLoader.load()` → `EffectiveConfig` |
| `02-adapter.md` | `EffectiveConfig.adapter` 决定 Adapter 类型 |
| `05-roles-skills.md` | `EffectiveConfig.roles` 定义成员与 Skills |
| `08-cost-control.md` | `EffectiveConfig.cost_control` 完整配置 |
| `04-web-panel.md` | 配置编辑器使用 Schema 生成表单 |
| `09-hooks-security.md` | `EffectiveConfig.hooks` + `.security` |
