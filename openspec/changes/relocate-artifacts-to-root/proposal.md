## Why

当前 `.ai-rd-team/runtime/artifacts/` 既存**过程元数据**（谁在什么时候产出），又存**最终可交付物**（代码 / 设计 / 文档 / 测试 / 部署脚本），两类数据语义严重混杂，在真实项目中造成多项摩擦：

- **用户视角错位**：2026-05-04 blog-api 真实 E2E 结束后，用户打开项目根目录 `tmp/` 期望看到 `mysh/ mysqler/ docs/`，结果根目录只有一个 `.ai-rd-team/` 隐藏目录，真正的代码埋在 `.ai-rd-team/runtime/artifacts/code/{mysh,mysqler}/` 四层深的位置
- **IDE 不友好**：大多数 IDE / 资源管理器默认折叠 `.` 开头的目录，新手几乎找不到代码
- **Git 冲突**：用户想对交付的代码仓库化（`git init`），但代码不在项目根，要么把过程数据也带进 git（污染），要么手动拷贝（违背"一体感"）
- **与业界心智背离**：Cursor / Claude Code / aider 的代码产出都直接落在项目根目录，`.xxx/` 只存状态 / 缓存 / 日志
- **已有设计的半成品**：`openspec/specs/design/07-artifacts.md §4.3` 早在设计阶段就预想了 `in_place / artifacts_only / both` 三种策略，**默认推荐 `in_place`**（代码直接进项目根），但实际 M1-M6 实现退化为 `artifacts_only`，且"只给代码"开了口子，其它文档类产物（requirements/design/reports/deployment）仍埋在 runtime 里，语义割裂

第一期仍处于 `0.1.0b1` beta，是做**路径语义统一**成本最低的窗口期。再晚改，example 示例、用户本地项目、外部博客引用都会成为兼容性负担。

## What Changes

- **目录语义拆分**（核心）：
  - `.ai-rd-team/`（项目根）**只存"过程 + 元数据"**：runtime 状态、日志、成本、消息、adapter intents/results、archive、memory、commands、config
  - **项目根目录**直接承载"最终交付物"：代码（`mysh/`、`mysqler/`）、文档（`docs/design/`、`docs/requirements/`、`docs/reports/`、`docs/deployment/` 等，或由架构师按惯例决定）、测试（`tests/` 或跟代码走）
  - `.ai-rd-team/runtime/artifacts/` 语义收窄为"**过程快照 + manifest 索引**"，不再是代码主副本
- **兑现 07-artifacts §4.3 默认策略**：`artifacts.code_output.strategy` 默认从实际运行的 `artifacts_only` 改为 **`in_place`**，且把该策略从"只管代码"扩展为"管所有交付物类型"（code / docs / tests / deployment）
- **落位规则引入"架构师决策"**：落位路径**不再由框架硬编码**，而是由架构师角色在"技术选型"阶段通过 `data-project-layout.yaml` 声明（见 design.md D3）。框架提供 **合理默认**（Python/Go/JS 三类语言的常见布局），架构师可覆盖。体现"自主研发团队"理念，不做工作流编排。
- **保留 review 为过程数据**：`review/` 保留在 `.ai-rd-team/runtime/` 下（不进项目根）。review 是"过程证据"，不是用户期望交付的内容。
- **保留 manifest 作为索引**：`.ai-rd-team/runtime/artifacts/manifest.yaml` 仍由 `ArtifactRecorder` 维护，但 entry 的 `path` 字段改为"项目根相对路径"（如 `mysh/main.go`）而非"artifacts 相对路径"。Web 面板、delivery checklist 依赖此索引。
- **明确不迁移的项**：`memory/`、`commands/`、`runtime/state/`、`runtime/logs/`、`runtime/cost/`、`runtime/messages/`、`runtime/adapter-*`、`runtime/archive/`、`runtime/current-run.yaml` 全部保留在 `.ai-rd-team/` 下。
- **硬切，不提供自动迁移工具**：当前处于 `0.1.0b1` beta，PyPI 未发布，外部用户约等于零。采取硬切策略：老的 `ArtifactRecorder.write()` / `write_raw()` API 直接重写为新接口（不保留 DeprecationWarning 兼容层）；老 workspace 的迁移建议是"删除 `.ai-rd-team/runtime/artifacts/` 后重新运行一次团队"，CHANGELOG 明确标 **BREAKING**。若将来真出现需要迁移的真实用户反馈，再补 `ai-rd-team migrate` 命令不迟。
- **文档 / Skills / 示例同步**：更新 `07-artifacts.md` 主版本、所有角色 Skills 的路径引导、`docs/01-getting-started.md` 演示截图、`examples/01-smart-bookmark` / `02-blog-api` / `03-todo-mini` / `04-custom-skill` 预期产物路径、`NEXT.md` 记录迁移点。

## Capabilities

### New Capabilities

- `artifact-placement`：明确 ai-rd-team 产出物落位的语义分层规则，包括：过程元数据（保留在 `.ai-rd-team/`）vs 最终交付物（直达项目根）、架构师声明 layout 的扩展点、manifest 的索引语义、迁移命令的契约。

### Modified Capabilities

- `openspec/specs/design/07-artifacts.md`：§4.1 / §4.3 / §7 / §10 / §13 全面重写（§4.3 从"可选策略"升级为"默认策略 + 扩展到所有类型"，§13 附录路径大量更新）。属于设计文档演进，不引入新 spec delta（新 spec delta 只在 `specs/artifact-placement/spec.md`）。
- `openspec/specs/design/11-runtime-protocol.md`：`runtime/` 目录树从"artifacts 占大头"改为"纯过程 + 少量索引"。

## 非目标

- ❌ **不改 memory / runtime/state / runtime/logs 等过程元数据的位置**——这些是对的，保留不动
- ❌ **不改 manifest.yaml 的 Schema 字段语义**，仅改 `path` 取值惯例（artifacts-相对 → 项目根-相对）
- ❌ **不引入多项目 workspace 模型**（一个 `.ai-rd-team/` 始终对应一个项目根，不支持 monorepo 子项目嵌套，后续有需求再立 change）
- ❌ **不支持自动猜测已有项目的布局**（若用户在已有代码仓库上运行 ai-rd-team，架构师必须显式写 `data-project-layout.yaml`）
- ❌ **不做"同时支持新旧两种目录"的双写兼容**——强制迁移，beta 期硬切成本最低
- ❌ **不提供 `ai-rd-team migrate` CLI**——beta 期外部用户 = 0，老 workspace 手动删 `runtime/artifacts/` 后重跑即可；若未来 PyPI 发布后出现真实迁移需求，再立 follow-up change
- ❌ **不保留 `ArtifactRecorder.write()` / `write_raw()` 老 API 的 deprecated 兼容层**——直接重写为新 write_* 分派，项目内测试一次性跟进
- ❌ **不处理 E2E 已归档产物的回填迁移**（`prototype/` 下的历史 E2E 产物保持原状，作为历史快照）

## Impact

### 代码

- `src/ai_rd_team/artifacts/recorder.py`：
  - `ArtifactRecorder` 新签名 `(project_root, runtime_dir, layout)`
  - 提供 5 个新方法：`write_code` / `write_doc` / `write_test` / `write_deploy` / `write_process`
  - 老的 `write()` / `write_raw()` **直接删除**（项目内所有调用一次性跟进，不走 deprecated）
  - `manifest.path` 改写项目根相对路径；新增 `category: delivery | process` 字段
- `src/ai_rd_team/artifacts/layout.py`（新文件，~120 行）：`ProjectLayout` dataclass + 默认布局表（Python/Go/JS/Vue3/WeChat MP/fallback 六档）+ 从 `data-project-layout.yaml` 加载
- `src/ai_rd_team/runtime/state.py`：`runtime_dir` / `project_root` 路径区分清楚，`RuntimeState` 暴露 `project_root` 供 recorder 使用
- `src/ai_rd_team/roles/prompt.py`：`ROLE_TO_DIR` 删除（被 `ArtifactRecorder.write_*` 接管），改为 `ROLE_TO_WRITE_METHOD` 映射
- `src/ai_rd_team/engine/manager.py`：`initialize()` 读 `data-project-layout.yaml`（若架构师已产出）→ 注入 recorder
- `src/ai_rd_team/service/readers.py` / `service/web/index.html`：面板展示制品时用新 path 语义
- ~~`src/ai_rd_team/cli/main.py` 新增 `migrate` 子命令~~ **不做**（非目标）

### 文档

- `openspec/specs/design/07-artifacts.md`：§4.1 目录结构 / §4.3 落位策略 / §7.2 接口 / §10 典型制品流 / §13 速查表全面更新
- `openspec/specs/design/11-runtime-protocol.md`：`runtime/` 目录树更新，标注"纯过程数据"
- `openspec/specs/design/05-roles-skills.md`：各角色 Skills 引导路径更新
- `docs/01-getting-started.md`：7 步上手的第 6/7 步演示产物路径截图更新
- `docs/02-configuration.md`：新增 `artifacts.layout` 配置段说明
- `plugins/ai-rd-team/skills/*/SKILL.md`：架构师 / 开发者 / 测试者 / DevOps 四个角色 Skills 的路径引导
- `examples/0{1,2,3,4}-*/EXPECTED_OUTPUTS.md` + `README.md`：预期产物路径全部从 `.ai-rd-team/runtime/artifacts/code/...` 改为项目根
- `CHANGELOG.md`：在 `[Unreleased]`（未发布版）记 **BREAKING**，migration 写法
- `NEXT.md`：记录迁移点 + 小杂事

### 测试

- `tests/unit/test_artifact_placement.py`（新）：`ProjectLayout` 加载 + 默认布局选择 + recorder 分派
- `tests/unit/test_recorder_layout.py`（新）：覆盖 write_code / write_doc / write_test / write_deploy / write_process 五个方法的行为
- `tests/unit/test_runtime_and_artifacts.py`（**重写**）：原断言全部走新 API，`write()` / `write_raw()` 相关用例删除
- `tests/integration/test_service_api.py`（更新）：/api/artifacts 端点返回的 path 字段语义更新
- ~~`tests/integration/test_migrate_cli.py`~~ **不做**（非目标）

### 向后兼容

- **不向后兼容**（BREAKING）。原因：
  - 仍是 beta（0.1.0b1），PyPI 未发，外部用户约等于零
  - 双写兼容会在 recorder / manifest / Skills 所有层加噪声，长期债更重
  - 老 API（`write()` / `write_raw()`）直接删除，不走 DeprecationWarning；项目内测试一次性跟进
  - 不提供 `ai-rd-team migrate` CLI；老 workspace 手动删 `.ai-rd-team/runtime/artifacts/` 后重跑即可
- 发布时版本号 bump 到 `0.2.0a1`（aN 表示 alpha，暗示布局语义演进，符合 PEP 440 + SemVer 惯例）

### 成本预估

- 工作量：~2-3 天（已从原 3-4 天收敛，砍掉 migrate CLI + 老 API 兼容层）
  - `ProjectLayout` + 默认布局表 + 配置加载：0.5d
  - `ArtifactRecorder` 重构（5 个 write_* 方法，老 API 直接删）：0.75d
  - 角色 Skills / Prompt 引导更新：0.5d
  - 文档 / 示例 / CHANGELOG：0.5d
  - 真实 E2E 验证（跑一次 example 02-blog-api，看代码是否落到项目根）：0.5-1d
- 风险：中等。主要风险点是"架构师生成的 `data-project-layout.yaml`"质量，若架构师漏写，必须有默认值托底（见 design.md D3）。
