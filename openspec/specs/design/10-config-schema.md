# ai-rd-team 详细设计 - 10 配置 Schema

> 文档版本：v1.1
> 日期：2026-05-04（v1.1：加入零配置 + 分层模型 + 对话引导）
> 颗粒度：**实现级**
> 依赖：`00-overview.md`

---

## 0. 核心理念：低门槛优先（AI 时代）

**问题**：本文档后续章节暴露了 400+ 配置项，但普通用户不该看到这些。

**原则**：
> **零配置即可用；对话式引导补全关键选择；YAML 只是持久化，不是主要交互界面。**

### 0.1 三层配置模型

| 层 | 文件 | 字段数 | 目标用户 | 何时出现 |
|----|------|-------|---------|---------|
| 🟢 **Zero Config（零配置）** | 无 | 0 | 初次使用者 | 默认情况 |
| 🟢 **Basic（基础层）** | `.ai-rd-team/config.yaml` | ~5-10 | 想做一些调整 | 首次启动引导后自动生成 |
| 🟡 **Advanced（高级层）** | `.ai-rd-team/config.advanced.yaml` | 全量 | 企业/定制化 | `ai-rd-team config advanced` 命令生成 |
| 🔴 **Defaults（内置默认）** | 代码内置 `defaults.yaml` | 全量 | 不可见 | 始终加载 |

**加载优先级**：`defaults` ← `global` ← `project/config.yaml` ← `project/config.advanced.yaml`（项目级最高，advanced 覆盖 basic）。

### 0.2 零配置流程

```
$ cd my-project
$ ai-rd-team run "我想做一个日报系统"
```

若 `.ai-rd-team/config.yaml` 不存在，触发**首次启动对话引导**（≤ 3 个问题，20 秒完成）：

```
👋 你好，我是 ai-rd-team。我检测到这是你第一次在这个项目使用我。

我已经看了你的项目（识别到：空项目 / Go项目 / Python项目 / Vue项目等）。
请回答 3 个问题，之后我就能开始工作了：

1. 项目规模大概是？
   [1] 小玩意，几天能搞定（推荐 Lite）
   [2] 正经项目，几周 ← 默认
   [3] 大系统，慢慢来（推荐 Full）
   > [回车接受默认]

2. 技术栈？
   [1] 我不管，架构师自己定 ← 默认
   [2] 复用现有项目的栈（已识别：xxx）
   [3] 指定：Go+Kratos 后端 / Vue3 PC / 微信小程序
   [4] 其他（稍后自己改）
   > [回车接受默认]

3. 预算大约？
   [1] 能省则省（Lite 预算 120 RP）
   [2] 平衡 ← 默认（Standard 400 RP/次, 2000 RP/天）
   [3] 要最好的（Full 1500 RP/次）
   > [回车接受默认]

✅ 已创建 .ai-rd-team/config.yaml（10 行，包含你的选择）
✅ 已准备就绪，开始工作...
```

**之后每次 `ai-rd-team run "xxx"` 就真正零打扰**。

### 0.3 最小 config.yaml（基础层完整形态）

首次引导后自动生成的 `.ai-rd-team/config.yaml`：

```yaml
# 这是 ai-rd-team 的基础配置（自动生成，可手动编辑）
# 完整配置见 config.advanced.yaml（运行 `ai-rd-team config advanced` 生成）

project:
  description: "我想做一个日报系统"  # 首次启动时用户输入

run_mode: standard          # lite / standard / full

# 可选：指定技术栈（留空则架构师自主选择）
tech_stack:
  backend: null
  frontend: null
  mobile: null

budget:
  per_run: 400              # Resource Points 单次上限
  per_day: 2000             # 日上限
```

**就这 5 个顶层字段。** 其他一切都用默认值。

### 0.4 高级配置：按需启用

用户需要调高级选项时：

```bash
$ ai-rd-team config advanced
# 生成 .ai-rd-team/config.advanced.yaml（带全部字段和注释）
# 提示用户打开编辑
```

或通过 Web 面板可视化调整（见 `04-web-panel.md`）。

### 0.5 智能推断（Convention over Configuration）

以下字段**不出现在任何 config.yaml 中**，引擎自动推断：

| 字段 | 推断方式 |
|------|---------|
| `project.name` | 工作区目录名 |
| `project.workspace` | 当前目录 |
| `tech_stack.proficiency` | 扫描项目文件（package.json / go.mod / requirements.txt） |
| `display_currency` | 系统 locale（`zh_CN` → CNY，其他 → USD） |
| `environment.os_supported` | 当前 OS |
| `security.file_access.writable` | 默认 `<workspace>/**`（排除 `.git/`） |
| `logging.level` | DEBUG 环境变量 → debug，否则 info |
| `web.host` / `web.port` | 127.0.0.1 + 自动选择空闲端口 |

**智能推断的优先级**：显式配置 > 引导输入 > 环境推断 > 代码默认值。

### 0.6 交互方式优先级

| 场景 | 推荐交互 | 方式 |
|------|---------|------|
| 首次使用 | 对话引导 | CLI 问 3 个问题 |
| 日常调整 | Web 面板 | 表单式，不碰 YAML |
| 特殊需求 | YAML 编辑 | `config.advanced.yaml` |
| 团队共享配置 | Git 提交 | 只提交 `config.yaml`（不含敏感信息） |

---

## 1. 目的与范围

### 1.1 目的
定义 ai-rd-team 的配置文件完整 Schema、加载优先级、校验规则、版本迁移策略。

**注意**：本文档的后续章节（§2 起）描述"**全量 Schema**"——是给**实现者**看的参考手册，不是给**终端用户**看的门槛。
- **终端用户** → 只看 §0
- **实现者** → 看 §1 及以后

### 1.2 范围
- `config.yaml`（Basic 层：5-10 个字段）
- `config.advanced.yaml`（Advanced 层：全量字段）
- `pricing.yaml`（可选，仅高级用户）
- `presets/*.yaml`（档位预设）
- `defaults.yaml`（代码内置，用户不编辑）
- 智能推断机制
- 首次启动对话引导

### 1.3 非目标
- ❌ 具体字段在业务逻辑中如何使用（由各模块文档定义）
- ❌ UI 配置编辑器实现细节（由 `04-web-panel.md` 定义）
- ❌ 首次引导的对话脚本内容（见 §2A，本文档定义数据契约；脚本文案可在实现阶段迭代）

---

## 2. 配置文件层级与优先级

### 2.1 四层配置（呼应 §0.1）

```
代码内置 defaults.yaml                    # 层 4：全量默认（用户不可见）
    ↓ 可覆盖
~/.ai-rd-team/config.yaml                 # 层 3：全局配置（所有项目共享，可选）
    ↓ 可覆盖
<workspace>/.ai-rd-team/config.yaml       # 层 2：项目 Basic 配置（首次引导生成）
    ↓ 可覆盖
<workspace>/.ai-rd-team/config.advanced.yaml  # 层 1：项目 Advanced 配置（CLI 触发生成）
```

**层级越低越优先**（层 1 最终覆盖层 4）。

### 2.2 合并策略

采用**深度合并 + 低层覆盖高层**：

- **标量字段**（string/number/bool）：低层直接覆盖高层
- **对象字段**（dict）：递归合并，同 key 低层覆盖
- **数组字段**（list）：低层**完全替换**高层（不做 merge）

**为什么数组不合并**：避免用户困惑。例如全局定义了 5 个角色，项目级定义了 3 个角色，合并后是 5 还是 8？完全替换最直观。

### 2.3 缺省值

- 若所有配置文件都不存在，使用代码内置默认值
- 默认值在 `defaults.yaml`（随代码分发，不允许用户编辑）
- 用户通过**智能推断**可在运行时覆盖部分默认值（见 §0.5）

### 2.4 加载流程

```
1. 读取 defaults.yaml（代码内置，层 4）
2. 执行智能推断（见 §0.5 和 §2B），产出 inferred 值
3. 读取 ~/.ai-rd-team/config.yaml（层 3，若存在）
4. 读取 <workspace>/.ai-rd-team/config.yaml（层 2，若存在）
5. 读取 <workspace>/.ai-rd-team/config.advanced.yaml（层 1，若存在）
6. 按 §2.2 规则合并：defaults < inferred < global < project_basic < project_advanced
7. 若层 2 不存在 → 触发首次启动对话引导（见 §2A），生成层 2
8. 应用档位 preset（若启动时选择了档位）
9. JSON Schema 校验（见 §6）
10. 配置版本迁移（若需要，见 §7）
11. 最终产出 EffectiveConfig 对象
```

### 2.5 错误处理

- **层 4 / 层 2 缺失**：正常情况，触发引导或用默认
- **层 3 存在但格式错**：警告用户，跳过该层，不终止启动
- **层 1 存在但校验失败**：致命，终止启动，提示用户修复

---

## 2A. 首次启动对话引导（数据契约）

**触发条件**：加载时检测到 `<workspace>/.ai-rd-team/config.yaml` 不存在。

### 2A.1 引导问题（≤ 3 个）

每个问题都有**合理默认值**和**回车即接受**的行为。

| # | 问题 | 选项（A/B/C...） | 默认 | 目标字段 |
|---|------|----------------|------|---------|
| 1 | 项目规模 | Lite / Standard / Full | Standard | `run_mode` |
| 2 | 技术栈 | auto / reuse_existing / specify / custom | auto（架构师决定） | `tech_stack.*` |
| 3 | 预算档位 | frugal / balanced / max_quality | balanced | `budget.*` |

### 2A.2 引导产物

引导结束后**必须产出**两样东西：

1. **生成 `<workspace>/.ai-rd-team/config.yaml`**，内容符合 §3A 的 Basic Schema
2. **触发一次 `EffectiveConfig` 构建**，供引擎后续使用

### 2A.3 引导的跳过与重新触发

| 场景 | 行为 |
|------|------|
| `ai-rd-team run --no-onboarding "需求"` | 跳过引导，用默认值 + 智能推断，不生成 `config.yaml` |
| `ai-rd-team init` | 手动触发引导（覆盖已存在的 `config.yaml`） |
| `ai-rd-team init --yes` | 全部采用推荐默认，无交互 |

### 2A.4 引导的实现者契约

引导由 `ConfigOnboarding` 模块实现（见 `01-engine.md` 启动流程）：

```python
class ConfigOnboarding:
    """首次启动引导。
    
    本文档不定义具体问题文案（可迭代），但定义：
    - 产出数据结构（§3A）
    - 可跳过行为（§2A.3）
    - 推断源（§0.5 和 §2B）
    """
    
    def run(
        self,
        workspace: Path,
        interactive: bool = True,
    ) -> "BasicConfig":
        """执行引导，返回 BasicConfig。
        
        - interactive=False：使用默认值，无用户交互
        - 会同时把结果写到 workspace/.ai-rd-team/config.yaml
        """
```

---

## 2B. 智能推断映射表（实现级）

以下推断由 `ConfigInference` 模块在加载阶段完成。

### 2B.1 项目信息

| 目标字段 | 推断来源 | 失败回退 |
|---------|---------|---------|
| `project.name` | `Path.cwd().name`（去除 `.`/`_` 前缀） | `"unnamed-project"` |
| `project.workspace` | `Path.cwd()` | - |
| `project.description` | `README.md` 首行标题 | `""`（引导时问用户） |

### 2B.2 技术栈

| 目标字段 | 推断来源 |
|---------|---------|
| `tech_stack.proficiency.python` | 扫描 `.py` / `requirements.txt` / `pyproject.toml` |
| `tech_stack.proficiency.go` | 扫描 `go.mod` / `*.go` |
| `tech_stack.proficiency.typescript` | 扫描 `package.json` / `tsconfig.json` |
| `tech_stack.proficiency.vue` | 扫描 `package.json` 的 `dependencies.vue` |
| `tech_stack.preferences.backend` | 优先级：`go.mod` → `requirements.txt` → `package.json` |
| `tech_stack.preferences.frontend` | 扫描 `web/` 或 `frontend/` 目录 |

推断结果**仅提示**，不强制使用。架构师仍可自主选择。

### 2B.3 环境

| 目标字段 | 推断来源 |
|---------|---------|
| `display_currency` | `locale.getlocale()` 或 `LANG` 环境变量：`zh_CN` → CNY，其他 → USD |
| `environment.os_supported` | `platform.system()` |
| `environment.python_min` | 当前 Python 版本 |
| `logging.level` | `DEBUG=1` 环境变量 → debug，否则 info |
| `web.host` | 默认 `127.0.0.1`（不要推 `0.0.0.0` 避免安全问题） |
| `web.port` | 默认 `8765`，被占用时 +1 直到找到空闲 |

### 2B.4 安全

| 目标字段 | 推断 |
|---------|------|
| `security.file_access.writable` | `[<workspace>/**]` 排除 `.git/`、`.ai-rd-team/memory/decisions/` |
| `security.file_access.readonly` | `[<workspace>/.git/**, <workspace>/.ai-rd-team/memory/decisions/**]` |
| `security.file_access.forbidden` | `[/etc/**, /usr/**, ~/.ssh/**, ~/.aws/**, ~/.kube/**]` |
| `security.commands.blocked` | 预设黑名单（见 §3.5） |

### 2B.5 推断优先级

```
显式写入 config.advanced.yaml
    > 显式写入 config.yaml
    > 引导输入
    > 环境推断（本节）
    > defaults.yaml 默认值
```

---

## 3A. Basic 层 Schema（用户直接接触）

**这才是 99% 用户实际看到的 `config.yaml`**——最多 10 个字段。

### 3A.1 完整 Basic Schema

```yaml
# <workspace>/.ai-rd-team/config.yaml
# Basic 层：首次启动引导自动生成，可手动编辑
# 高级配置用 `ai-rd-team config advanced` 生成 config.advanced.yaml

# 配置版本
config_version: "1.0"

# 项目简要描述（可在首次引导中输入，或留空让成员读 README.md）
project:
  description: "一句话描述你想做什么"

# 运行档位（lite/standard/full）
run_mode: standard

# 技术栈（留空表示让架构师自主选择；架构师会参考已有代码 + proficiency）
tech_stack:
  backend: null              # null / "go-kratos" / "python-flask" / "node-express" / ...
  frontend: null             # null / "vue3" / "react" / ...
  mobile: null               # null / "wechat-miniprogram" / "react-native" / ...

# 预算（Resource Points）
budget:
  per_run: 400               # 单次运行上限
  per_day: 2000              # 日上限
```

### 3A.2 字段说明

| 字段 | 必填 | 默认 | 说明 |
|------|-----|------|------|
| `config_version` | ✅ | - | 自动生成 |
| `project.description` | ❌ | 引导输入或 README | 一句话需求描述 |
| `run_mode` | ❌ | `standard` | 档位 |
| `tech_stack.backend` | ❌ | `null` | null 表示自主选择 |
| `tech_stack.frontend` | ❌ | `null` | 同上 |
| `tech_stack.mobile` | ❌ | `null` | 同上 |
| `budget.per_run` | ❌ | 见档位（Lite 120 / Std 400 / Full 1500） | 随 `run_mode` 联动 |
| `budget.per_day` | ❌ | 2000 | 日上限 |

### 3A.3 与 Advanced Schema 的关系

- **Basic 是 Advanced 的严格子集**：Basic 中所有字段都存在于 Advanced
- **Basic 对应 Advanced 的路径映射**：

| Basic | Advanced（§3）|
|-------|--------------|
| `project.description` | `project.description` |
| `run_mode` | `cost_control.default_mode` + `cost_control.remembered_mode` |
| `tech_stack.backend` | `tech_stack.preferences.backend` |
| `budget.per_run` | `cost_control.budget_{mode}.max_resource_points` + `cost_control.quota.windows.per_run` |
| `budget.per_day` | `cost_control.quota.windows.per_day` |

加载器的职责是把 Basic 展开成 Advanced 全量视图后再合并（见 §8 `ConfigLoader`）。

### 3A.4 Advanced 层的生成

```bash
$ ai-rd-team config advanced
# 生成 <workspace>/.ai-rd-team/config.advanced.yaml
# 内容：当前 EffectiveConfig 的全量导出（含所有推断+默认值），带注释说明
# 用户编辑其中的字段后，下次启动生效
```

生成的 `config.advanced.yaml` 是**完整可读的全量配置**（不含推断源），用户可以放心删除不想改的部分（会回退到 Basic 或默认）。

### 3A.5 Basic 校验规则

| 字段 | 校验 |
|------|------|
| `run_mode` | 枚举：lite / standard / full |
| `tech_stack.*` | string 或 null |
| `budget.per_run` | 正整数 |
| `budget.per_day` | ≥ `budget.per_run` |

---

## 3. config.advanced.yaml / defaults.yaml 完整 Schema

> **读者提醒**：以下是**全量 Schema**（约 400 字段）。  
> 终端用户**不需要看**——他们通过 §0.2 的引导 + §3A 的 Basic Schema 就够用。  
> 本章节供**实现者**参考。

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
config = ConfigLoader(workspace_dir=Path.cwd() / ".ai-rd-team").load()

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
        self._onboarding = ConfigOnboarding()
        self._inference = ConfigInference()
    
    def load(
        self,
        preset: Literal["lite", "standard", "full"] | None = None,
        allow_onboarding: bool = True,
        interactive: bool = True,
    ) -> EffectiveConfig:
        """加载配置（推荐入口）。
        
        完整流程：defaults → inferred → global → basic → advanced → preset → 校验
        
        Args:
            preset: 启动时强制指定档位（覆盖 config 中的 run_mode）
            allow_onboarding: 若项目 config.yaml 不存在，是否触发引导
            interactive: 引导时是否允许用户交互（False 则用推荐默认）
        
        Raises:
            ConfigValidationError: 校验失败
            ConfigMigrationError: 版本迁移失败
        """
        ...
    
    def load_basic(self) -> "BasicConfig | None":
        """只加载 Basic 层（§3A），不做合并。
        
        用途：Web 面板显示"用户视角"的配置。
        """
    
    def load_advanced(self) -> dict | None:
        """只加载 Advanced 层（§3），不做合并。
        
        用途：Web 面板的高级编辑视图。
        """
    
    def expand_basic_to_advanced(
        self,
        basic: "BasicConfig",
    ) -> dict:
        """将 Basic 配置展开为 Advanced 全量字段（§3A.3 的映射）。
        
        用途：生成 config.advanced.yaml、Web 面板的"查看 advanced 形态"。
        """
    
    def save_basic(
        self,
        basic: "BasicConfig",
        target: Literal["global", "project"] = "project",
    ) -> None:
        """保存 Basic 层。"""
    
    def save_advanced(
        self,
        config: EffectiveConfig,
        target: Literal["global", "project"] = "project",
    ) -> None:
        """保存 Advanced 层（导出当前 EffectiveConfig 为 config.advanced.yaml）。"""
    
    def validate(self, raw: dict, layer: Literal["basic", "advanced"] = "advanced") -> list[str]:
        """仅校验，不加载。返回错误列表。"""
        ...
    
    def get_effective_source(self, key_path: str) -> Path | Literal["inferred", "default"]:
        """查询某配置项的最终来源（调试用）。
        
        返回：
        - Path：来自某个配置文件
        - "inferred"：来自智能推断
        - "default"：来自代码内置默认
        """
        ...


class ConfigOnboarding:
    """首次启动对话引导（见 §2A）。"""
    
    def run(
        self,
        workspace: Path,
        interactive: bool = True,
        inferred: dict | None = None,
    ) -> "BasicConfig":
        """执行引导，返回 BasicConfig 并写到 workspace/.ai-rd-team/config.yaml。"""
        ...


class ConfigInference:
    """智能推断（见 §0.5 + §2B）。"""
    
    def infer(self, workspace: Path) -> dict:
        """扫描工作区 + 环境，产出推断字段字典。"""
        ...
    
    def infer_project_info(self, workspace: Path) -> dict:
        """推断 project.* 字段。"""
    
    def infer_tech_stack(self, workspace: Path) -> dict:
        """扫描代码推断 tech_stack.proficiency / preferences。"""
    
    def infer_environment(self) -> dict:
        """推断 display_currency / environment.* / logging.level 等。"""
    
    def infer_security(self, workspace: Path) -> dict:
        """产出安全默认（file_access / commands）。"""
```

---

## 10. 用户交互流程（薄壳，细节见 §0 + §2A）

### 10.1 CLI 命令总览

| 命令 | 作用 |
|------|------|
| `ai-rd-team init` | 手动触发首次引导（覆盖已有 config.yaml） |
| `ai-rd-team init --yes` | 全部采用推荐默认，无交互 |
| `ai-rd-team run "需求"` | 若 config 缺失则自动触发引导，再执行 |
| `ai-rd-team run --no-onboarding "需求"` | 跳过引导，用默认 + 推断 |
| `ai-rd-team config show` | 查看当前 EffectiveConfig |
| `ai-rd-team config show --layer basic` | 只看 Basic 层 |
| `ai-rd-team config show --source <key>` | 查询某字段来自哪里（推断/文件/默认） |
| `ai-rd-team config advanced` | 生成 config.advanced.yaml（全量字段 + 注释） |
| `ai-rd-team config validate` | 仅校验 config 文件 |

### 10.2 交互优先级

| 用户类型 | 首选交互 | 补充 |
|---------|---------|------|
| 普通用户 | 首次引导（≤3 问） + Web 面板 | 绝不直接改 YAML |
| 工程师 | `config.yaml`（Basic）+ Web 面板 | 偶尔 `config.advanced.yaml` |
| 企业/定制化 | `config.advanced.yaml` + CI 同步 | 全量 YAML 审计 |

### 10.3 引导后的再启动

- 第 2 次起：完全零打扰，直接 `ai-rd-team run "xxx"` 即可
- 修改 run_mode / 技术栈：直接改 `config.yaml` 或用 Web 面板
- 重新走引导：`ai-rd-team init`（会备份旧 config 到 `.bak`）

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

### 12.1 低门槛（核心）
- ✅ **零配置可运行**：用户不写任何 config，`ai-rd-team run "需求"` 能走到"首次引导"或直接使用智能推断 + 默认值
- ✅ **首次引导 ≤ 3 个问题**，每题有合理默认，用户回车即过
- ✅ **生成的 Basic `config.yaml` ≤ 20 行**（含空行和注释）
- ✅ **智能推断**按 §2B 覆盖所有字段，推断失败时优雅回退默认
- ✅ **`ai-rd-team config advanced`** 能正确导出完整 `config.advanced.yaml`
- ✅ **Basic → Advanced 展开映射**按 §3A.3 正确工作（含 run_mode 联动预算）

### 12.2 加载与合并
- ✅ 能加载 defaults + inferred + global + basic + advanced 五层并正确合并
- ✅ 层级优先级严格符合 §0.1
- ✅ `get_effective_source(key)` 能准确返回每个字段的来源
- ✅ JSON Schema 校验覆盖所有必填字段和关键约束
- ✅ 支持从 v1.0 到最新版的迁移
- ✅ EffectiveConfig 对象不可变，线程安全
- ✅ 提供 3 份 preset（lite/standard/full）

### 12.3 错误处理
- ✅ 缺失 basic + 禁用引导时能用推断 + 默认运行
- ✅ advanced 校验失败给出可修复的提示
- ✅ 单元测试覆盖 ≥ 80%（加载/合并/校验/迁移/推断/引导）
- ✅ 集成测试：从零配置到完整运行一次 Standard 档

### 12.4 可达性
- ✅ 所有基础操作（init / run / config show / config advanced）都有对应 CLI
- ✅ Web 面板能加载 Basic / Advanced 双视图（由 `04-web-panel.md` 实现）

---

## 13. 附录：配置示例文件

将提供 4 份完整示例（实现阶段产出）：
- `examples/config-zero.md`：零配置场景的说明（无实际 yaml 文件）
- `examples/config-basic.yaml`：首次引导生成的 Basic 示例（~20 行）
- `examples/config-advanced.yaml`：完整 Advanced 示例（带全部注释）
- `examples/config-enterprise.yaml`：企业场景示例（含 central_quota、securty 强化）

---

## 14. 对其他文档的接口

| 使用方 | 接口 |
|-------|-----|
| `01-engine.md` | `ConfigLoader.load(allow_onboarding=True)` → `EffectiveConfig`；Engine.initialize 在 ConfigLoader 之后检查是否刚做过引导（用于日志） |
| `02-adapter.md` | `EffectiveConfig.adapter` 决定 Adapter 类型 |
| `05-roles-skills.md` | `EffectiveConfig.roles` 定义成员与 Skills；Basic 层不直接含 roles，由 Advanced 或 preset 提供 |
| `08-cost-control.md` | `EffectiveConfig.cost_control` 完整配置；Basic 的 `run_mode` / `budget.*` 映射到此 |
| `04-web-panel.md` | Basic/Advanced 双视图表单；Web 面板调用 `ConfigLoader.load_basic/load_advanced` |
| `09-hooks-security.md` | `EffectiveConfig.hooks` + `.security`；security 默认值由 §2B.4 智能推断 |
| CLI（本文档 §10） | `ai-rd-team init/run/config` 系列命令的数据契约 |
