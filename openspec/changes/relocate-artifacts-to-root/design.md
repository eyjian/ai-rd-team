## Context

### 现状

`.ai-rd-team/runtime/artifacts/` 当前挂了七类子目录（requirements / design / code / review / test / deployment / reports），每类都是"团队角色的产出主目录"，包括：

- 设计文档（`spec-architecture.md`、`data-interfaces.yaml`）
- 代码文件（`mysh/main.go`、`UserProfile.vue`）
- 测试代码（`test_user_service.py`）
- 部署脚本（`Dockerfile`、`k8s-*.yaml`）
- 报告（`report-phase-dev.md`）
- 评审（`spec-review-user.md`、`log-review-rounds.jsonl`）

这些内容语义**不同质**：

- 代码 / 测试 / 部署脚本 / 设计文档 = **最终交付物**（用户拿着跑、拿着读、拿着部署）
- 评审日志 / 阶段报告 / manifest = **过程证据**（追溯谁在什么时候做了什么）

2026-05-04 blog-api E2E 后用户截图反馈："打开项目根目录只看到 `.ai-rd-team/`，代码埋在 `.ai-rd-team/runtime/artifacts/code/mysh/` 四层深的位置"，这是个典型摩擦证据。

### 相关模块

- `src/ai_rd_team/artifacts/recorder.py`：`ArtifactRecorder` 负责所有类型制品写入，当前统一走 `artifacts_dir / subdir` 路径
- `src/ai_rd_team/roles/prompt.py`：`ROLE_TO_DIR` 决定角色→目录映射，被 recorder 和 prompt 模板共用
- `src/ai_rd_team/runtime/state.py`：`RuntimeState` 只暴露 `runtime_dir` 和 `artifacts_dir`，没有"项目根"的概念
- `src/ai_rd_team/engine/manager.py`：`initialize()` 组装 recorder / memory / state，没有读 layout 的环节
- `plugins/ai-rd-team/skills/ai-rd-team-launcher/SKILL.md` + 各角色 prompt 模板：引导成员写到 `artifacts/design/`、`artifacts/code/` 等具体路径

### 约束

- **beta 期硬切**：不做双写兼容，但必须提供一次性迁移命令
- **架构师自主**：技术栈 + 目录布局由架构师决定，框架不硬编码——这是 ai-rd-team 核心卖点
- **兼容 manifest 消费者**：Web 面板、delivery checklist 依赖 `manifest.path`，迁移后这些消费者必须同步更新
- **security.file_access.writable 约束不变**：新布局下代码写项目根需要 security 允许（当前默认 `project_root_writable: true`，见 07-artifacts §4.3）
- **P2P 成员通信 / adapter bridge / state 协议全部不动**：本 change 只动"产出物落位"，不碰运行时机制

### 数据支撑

参考 M5 归档的 blog-api 产物，按新规划对应新布局：

| 类别 | 当前位置 | 新位置 | 语义 |
|---|---|---|---|
| Go 代码 | `.ai-rd-team/runtime/artifacts/code/mysh/*.go` | `mysh/*.go`（项目根） | 交付物 |
| Go 代码 | `.ai-rd-team/runtime/artifacts/code/mysqler/*.go` | `mysqler/*.go`（项目根） | 交付物 |
| 技术研究 | `.ai-rd-team/runtime/artifacts/code/TECH_RESEARCH.md` | `docs/research/TECH_RESEARCH.md` 或根 `TECH_RESEARCH.md` | 交付物 |
| 架构设计 | `.ai-rd-team/runtime/artifacts/design/spec-architecture.md` | `docs/design/ARCHITECTURE.md` | 交付物 |
| 接口契约 | `.ai-rd-team/runtime/artifacts/design/data-interfaces.yaml` | `docs/design/interfaces.yaml` | 交付物 |
| 需求文档 | `.ai-rd-team/runtime/artifacts/requirements/spec-requirements.md` | `docs/requirements/REQUIREMENTS.md` | 交付物 |
| 测试代码（Go） | `.ai-rd-team/runtime/artifacts/test/*.go` | `mysh/*_test.go` | 交付物（Go 惯例：同包） |
| 测试代码（Py） | `.ai-rd-team/runtime/artifacts/test/test_*.py` | `tests/test_*.py` | 交付物（Py 惯例：tests/） |
| Dockerfile | `.ai-rd-team/runtime/artifacts/deployment/Dockerfile` | `Dockerfile`（项目根） | 交付物 |
| k8s YAML | `.ai-rd-team/runtime/artifacts/deployment/k8s-*.yaml` | `deploy/k8s-*.yaml` | 交付物 |
| 阶段报告 | `.ai-rd-team/runtime/artifacts/reports/report-phase-dev.md` | `.ai-rd-team/runtime/reports/report-phase-dev.md`（**保留 runtime 下**） | 过程 |
| 评审报告 | `.ai-rd-team/runtime/artifacts/review/spec-review-*.md` | `.ai-rd-team/runtime/review/spec-review-*.md` | 过程 |
| 评审日志 | `.ai-rd-team/runtime/artifacts/review/log-review-rounds.jsonl` | `.ai-rd-team/runtime/review/log-review-rounds.jsonl` | 过程 |
| manifest | `.ai-rd-team/runtime/artifacts/manifest.yaml` | `.ai-rd-team/runtime/manifest.yaml`（**提升一层**，不再是 artifacts 的私有索引） | 过程 |
| delivery checklist | `.ai-rd-team/runtime/artifacts/delivery/*.yaml` | `docs/delivery/checklist.md` + `.ai-rd-team/runtime/manifest.yaml`（机器可读部分进 manifest） | 交付物 + 过程 |

## Goals / Non-Goals

**Goals:**

- **G1**：用户 `cd` 进项目根目录立刻看到代码 / 文档 / 测试 / Dockerfile，不用翻隐藏目录
- **G2**：`.ai-rd-team/` 只含"过程数据"，用户可安全加入 `.gitignore` 而不丢失交付物
- **G3**：落位规则"可被架构师覆盖"，Python / Go / JS / 微信小程序四类栈有合理默认，新栈可由架构师声明
- **G4**：提供 `ai-rd-team migrate <workspace>` 命令，5 秒迁移老 workspace
- **G5**：manifest 作为"权威索引"依然可用，Web 面板不需要改展示逻辑（只需跟进 path 语义变更）
- **G6**：review / reports / manifest 等过程元数据**不**跟着搬到项目根，保持语义纯净
- **G7**：E2E 回归：跑一次 `examples/02-blog-api` Standard 档，确认产物落到项目根

**Non-Goals:**

- **NG1**：不做双写兼容 / 不做 in_place + artifacts_only "both" 模式（07-artifacts §4.3 曾列过 both，这次废弃）
- **NG2**：不引入 monorepo 子项目嵌套模型
- **NG3**：不自动识别已有代码仓库的布局（架构师必须显式声明或用默认）
- **NG4**：不迁移 `prototype/` 下的历史 E2E 快照（它们是"某次运行的冻结证据"，改结构就失真了）
- **NG5**：不在此次 change 中引入"交付物的版本管理"（每次 run 的产物覆盖上次，除非 memory 记了 ADR）

## Decisions

### D1：目录语义二分——"过程 vs 交付"

**决策**：`.ai-rd-team/` 下只保留**过程元数据**；**交付物**一律进项目根。

**过程元数据**（保留在 `.ai-rd-team/`）：

```
<project_root>/.ai-rd-team/
├── config.yaml / config.advanced.yaml
├── memory/                    # 团队记忆
├── commands/                  # 自定义命令
└── runtime/
    ├── state/                 # 运行时状态
    ├── logs/                  # 日志
    ├── cost/                  # 成本
    ├── messages/              # 成员间消息
    ├── adapter-intents/       # bridge 协议
    ├── adapter-results/       # bridge 协议
    ├── archive/               # 历史 run 归档
    ├── review/                # 评审过程（spec-review / log-review-rounds）
    ├── reports/               # 阶段报告（report-phase-* / report-run-summary）
    ├── manifest.yaml          # 交付物索引（指向项目根路径）
    └── current-run.yaml
```

**交付物**（直达项目根，具体路径由 ProjectLayout 决定）：

```
<project_root>/                # 架构师决定的真实项目布局
├── mysh/                      # 代码模块
├── mysqler/
├── docs/                      # 架构师声明的 docs 根
│   ├── design/                #   架构方案 / 接口契约
│   ├── requirements/          #   需求文档
│   └── delivery/              #   交付 checklist（人读版）
├── tests/                     # 架构师声明的 tests 根（Go 会空，走同包 _test.go）
├── deploy/                    # 部署脚本（若有）
├── Dockerfile                 # 常见直接放根
├── README.md                  # 项目自己的 README
└── .ai-rd-team/               # 过程数据
```

**理由**：

- 这是 **07-artifacts §4.3 原本就设计好的方向**（"in_place 为推荐第一期默认"），本 change 只是兑现它，并把范围从"只管代码"扩大到"管所有类型"
- `.ai-rd-team/` 对用户来说是"黑盒操作痕迹"（像 `.git/`、`node_modules/`、`.venv/`），天然适合被 `.gitignore`
- 和业界心智匹配（Cursor / Claude Code / aider 都是这样）

**替代方案（否决）**：

- **A：全部保留在 `.ai-rd-team/runtime/artifacts/`**（现状）——用户摩擦大，不做
- **B：只把代码挪出，文档 / 测试 / 部署都保留**——语义割裂，"代码特殊化"没理由
- **C：全部挪到项目根（包括 review / reports）**——过程数据污染用户眼睛，review 日志用户不会看

### D2：manifest 改为"项目根相对路径"索引

**决策**：`manifest.yaml` 位置从 `.ai-rd-team/runtime/artifacts/manifest.yaml` 提升到 `.ai-rd-team/runtime/manifest.yaml`；每条 entry 的 `path` 字段存**项目根相对路径**。

```yaml
# 旧（current）
artifacts:
  - path: "code/mysh/main.go"       # 相对 artifacts_dir
    kind: "raw"
    producer: "developer_1"

# 新（after this change）
artifacts:
  - path: "mysh/main.go"             # 相对项目根
    kind: "code"
    producer: "developer_1"
    category: "delivery"             # 新字段：delivery / process
```

**新增字段 `category: delivery | process`** 让消费者（Web 面板、delivery checklist、CI）能区分"这是用户最终看到的"还是"这是过程数据"。

**实现点**：
- `ArtifactRecorder.__init__` 新增 `project_root: Path` 参数
- `_update_manifest` 计算 `path` 时用 `full_path.relative_to(self.project_root)` 而非 `relative_to(self.artifacts_dir)`
- 老消费者（Web / delivery）跟进更新一次即可，无 API 破坏

**替代方案（否决）**：
- 保持 path 为 artifacts-相对——搬出去后索引就断了，必须改
- 用绝对路径——跨机器不可用

### D3：ProjectLayout 由架构师声明，框架提供默认

**决策**：引入 `ProjectLayout` 概念：

```python
# src/ai_rd_team/artifacts/layout.py
@dataclass(frozen=True)
class ProjectLayout:
    code_dirs: dict[str, str]        # {"backend": "mysh", "cli": "mysqler"}
    docs_root: str = "docs"          # 文档根
    docs_subdirs: dict[str, str] = {
        "requirements": "requirements",
        "design": "design",
        "delivery": "delivery",
        "research": "research",
    }
    tests_root: str | None = "tests"  # Go 项目可能为 None
    tests_mode: str = "separate"      # "separate" | "alongside"（Go 的 _test.go）
    deploy_root: str = "deploy"
    root_level_files: list[str] = ["Dockerfile", "docker-compose.yaml", "README.md"]

# 默认 layout 表（架构师不声明时兜底）
DEFAULT_LAYOUTS = {
    "python": ProjectLayout(code_dirs={"main": "src"}, tests_root="tests", tests_mode="separate", ...),
    "go":     ProjectLayout(code_dirs={}, tests_root=None, tests_mode="alongside", ...),
    "js":     ProjectLayout(code_dirs={"main": "src"}, tests_root="tests", ...),
    "vue3":   ProjectLayout(code_dirs={"frontend": "src"}, ...),
    "wechat-mp": ProjectLayout(code_dirs={"miniprogram": "miniprogram"}, ...),
    "fallback": ProjectLayout(code_dirs={"main": "src"}, tests_root="tests", ...),
}
```

架构师在"技术选型"阶段产出 `<.ai-rd-team/runtime/reports>/data-project-layout.yaml`（注意这是**过程数据**，因为它是架构师决策过程的一部分；但它"影响"交付物落位）：

```yaml
version: "1.0"
base: "go"           # 从 DEFAULT_LAYOUTS 继承
overrides:
  code_dirs:
    shell: "mysh"
    query: "mysqler"
  tests_mode: "alongside"   # Go 惯例
  docs_root: "docs"
```

框架加载顺序：
1. 架构师声明的 `data-project-layout.yaml`（若存在）
2. `config.advanced.yaml` 里的 `artifacts.layout`（若显式配置）
3. 默认语言对应的 `DEFAULT_LAYOUTS[lang]`（从 `tech-stack-selected.md` memory 推断）
4. `DEFAULT_LAYOUTS["fallback"]`（最后兜底）

**理由**：
- 不硬编码 = 符合"自主研发团队"理念
- 有默认 = 新手开箱即用
- 架构师可覆盖 = 适配任何语言 / 框架 / 组织习惯

**替代方案（否决）**：
- 只给配置文件表达 layout——违背"架构师自主"主张
- 只给架构师声明无默认——新手第一次跑没有 layout，recorder 会报错

### D4：ArtifactRecorder 分派 write_*

**决策**：`ArtifactRecorder.write()` 拆分为 5 个方法（老 `write()` / `write_raw()` **直接删除**，不保留 deprecated 包装）：

```python
class ArtifactRecorder:
    def __init__(self, project_root: Path, runtime_dir: Path, layout: ProjectLayout):
        self.project_root = project_root
        self.runtime_dir = runtime_dir
        self.manifest_path = runtime_dir / "manifest.yaml"
        self.layout = layout

    # ===== 交付物（进项目根）=====
    def write_code(self, module: str, filename: str, content: str, producer: str) -> Path: ...
    def write_doc(self, category: str, filename: str, content: str, producer: str) -> Path: ...
        # category ∈ {"requirements", "design", "delivery", "research"}
    def write_test(self, module: str | None, filename: str, content: str, producer: str) -> Path: ...
        # module=None + layout.tests_mode="separate" → tests/<filename>
        # module="mysh" + layout.tests_mode="alongside" → mysh/<filename>
    def write_deploy(self, filename: str, content: str, producer: str) -> Path: ...

    # ===== 过程（进 .ai-rd-team/runtime）=====
    def write_process(self, kind: str, name: str, content: str, producer: str, ext: str = "md") -> Path: ...
        # kind ∈ {"review", "report", "log"}，落 runtime/<kind>/
```

**理由**：
- 调用方（成员 prompt 模板 / engine / 测试）语义清晰，不需要自己拼路径
- manifest 能根据方法名打 `category: delivery | process` 标签
- **硬切而非 deprecated**：当前处于 beta（PyPI 未发、外部用户 ≈ 0），保留老 API 只会给长期维护加负担；项目内 `tests/unit/test_runtime_and_artifacts.py` 等调用点一次性跟进即可

**替代方案（否决）**：
- 保留 `write()` + DeprecationWarning 包装——短期兼容但长期要维护双套路径，beta 期不值
- 只加 `write_code` 一个新方法，其他类型仍走老 `write`——语义割裂

### D5：不提供 migrate CLI（硬切）

**决策**：不在本 change 中新增 `ai-rd-team migrate` 子命令。老 workspace 的迁移指引是"删除 `.ai-rd-team/runtime/artifacts/` 目录后重新运行一次团队"。

**理由**：
- beta 期外部用户约等于零，唯一可能的老 workspace = 作者本机开发时跑出来的 `examples/02-blog-api/<workspace>/`，手动清理成本 < 5 秒
- `examples/` 目录里是"示例项目"不是"活 workspace"，不需要迁移
- `prototype/M*/` 是冻结快照，明确不迁移
- 维护一个几乎没人用的 CLI 命令 = 长期维护债；真有用户反馈需要时再补
- 省掉整个 tasks 第 4 组（~0.5d 工作量 + ~200 行代码 + fixture 测试 + 维护面）

**替代方案（否决）**：
- 提供 `ai-rd-team migrate`——过度工程，beta 期无受益方
- 在 engine 启动时自动检测并迁移——隐蔽性太强，bug 隐患大
- 不提供且不写清迁移指引——用户摸不着头脑

**若将来触发条件**：PyPI 发布后有真实用户反馈"老 workspace 不想删"，再立 follow-up change 补 CLI。届时已有具体痛点和数据，避免拍脑袋。

### D6：BREAKING 版本号 bump 到 0.2.0a1

**决策**：版本号从 `0.1.0b1` → `0.2.0a1`。

**理由**：
- 老语义 "0.1 系列" = "artifacts 统一在 runtime 下"；新语义 "0.2 系列" = "交付物进项目根"——语义演进，MINOR 版本 bump 合理
- alpha（a1）标记"刚动完地基，会有小坑"
- 发布后 b/rc/final 按常规演进

**替代方案（否决）**：
- 继续 `0.1.0b2`——隐藏了 BREAKING 变更信号
- 直接 `0.2.0`（final）——没跑够真实 E2E 不敢贴 stable 标

## Risks / Trade-offs

### R1：架构师生成的 layout 质量
- **风险**：架构师漏写 `data-project-layout.yaml`，或字段拼错
- **缓解**：
  - 严格的 `DEFAULT_LAYOUTS` 兜底（每种主流栈都有合理默认）
  - `ProjectLayout.from_yaml()` 做 schema 校验，异常时 fallback 到默认 + warning
  - 架构师 Skill 里明确提示"如果使用的是主流栈可以不写这个文件"

### R2：Web 面板 / delivery checklist 回归漏改
- **风险**：消费者用老 path 语义，显示 broken
- **缓解**：
  - tasks.md 里列清所有消费者（Web / readers / delivery 报告模板）
  - 集成测试覆盖 `/api/artifacts` 端点

### R3：老用户示例 README 不匹配
- **风险**：`examples/0{1,2,3,4}-*/` 的 `EXPECTED_OUTPUTS.md` 写的是老路径，用户照着 `docs/01-getting-started.md` 跑会看到不一致
- **缓解**：
  - tasks 里 4 个 example 的 README + EXPECTED_OUTPUTS 全部一次性更新
  - 跑一次 example 02 真实 E2E 验证

### R4：架构师 data-project-layout.yaml 是过程还是交付？
- **纠结点**：它是架构师决策的产物，但其他成员"要拿它去落盘"，半过程半交付
- **决定**：归为**过程数据**，落 `.ai-rd-team/runtime/reports/data-project-layout.yaml`。理由：用户不需要读它（它不是"给人的设计文档"），它是"给机器的路由表"；真正给人的架构文档是 `docs/design/ARCHITECTURE.md`。

## Migration Plan

### 对新项目（zero-config 冷启动）
- 开箱就是新布局，无感知

### 对老项目（0.1.x 的 workspace，极少数）
- 不提供自动迁移工具（见 D5）
- **操作步骤**：
  1. 升级 ai-rd-team：`pip install -U ai-rd-team`（bump 到 0.2.0a1 后）
  2. 清理老数据：`rm -rf <workspace>/.ai-rd-team/runtime/artifacts/`（若确认不需要保留历史产物；否则先手动拷贝到其它位置）
  3. 重新跑一次团队：`ai-rd-team run "..."`，新运行将按新布局落位
- 如果用户强烈反馈需要保留历史产物自动迁移，再立 follow-up change 补 `migrate` 命令

### 对示例仓库
- `examples/*/` 里所有 `EXPECTED_OUTPUTS.md` 一次性更新
- `examples/*/` 本身不存 "历史 workspace"（它们是示例项目而非 workspace），只改文档
- `prototype/M*/` 保持原状（冻结的 E2E 快照，改了就失真）

## Resolved Decisions（原 Open Questions，本次敲定）

- **Q1 已定**：`docs/` 采用**两层结构**（`docs/design/ARCHITECTURE.md` / `docs/requirements/REQUIREMENTS.md` / `docs/delivery/checklist.md`）。对大项目有扩展性，对小项目也只多一层目录开销；架构师想扁平可以在 `data-project-layout.yaml` 里 override `docs_subdirs={design: "", requirements: "", ...}` 实现。
- **Q2 已定**：`report-run-summary.md` 归**纯过程**（`.ai-rd-team/runtime/reports/`）。理由：它是"本次 run 的快照"，下次 run 会被覆盖；真正给人看的交付物是 `docs/delivery/checklist.md`（累积式人工版）。PM 角色同时产出两份（runtime 版 + docs 版），避免把过程数据和交付物混在一起。
- **Q3 已定**：`data-project-layout.yaml` 字段与 `config.advanced.yaml:artifacts.layout` **合一**（共用 `ProjectLayout` schema）。来源优先级见 D3（架构师 yaml > config > memory 推断 > fallback）。只要架构师 yaml 能表达 config 能表达的全部即可。
