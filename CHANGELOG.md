# Changelog

All notable changes to `ai-rd-team` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### ⚠️ BREAKING (M7 — relocate-artifacts-to-root)

**交付物落位从 `.ai-rd-team/runtime/artifacts/` 迁移到项目根**。团队产出的代码 / 文档 / 测试 / 部署脚本将直接落项目根，不再埋在隐藏目录下。过程数据（评审 / 阶段报告 / manifest / 状态 / 日志）仍保留 `.ai-rd-team/runtime/`。

**迁移指南**（老 0.1.x workspace）：
```bash
# 1. 删除老的 runtime/artifacts/ 目录（确认不需要保留历史产物）
rm -rf <workspace>/.ai-rd-team/runtime/artifacts/
# 2. 重新运行团队，按新布局产出
ai-rd-team run "..."
```
本次不提供 `ai-rd-team migrate` CLI，beta 期外部用户极少，手动清理成本低；如将来真出现迁移需求会通过 follow-up change 补。

### Added (M7)

- **`ProjectLayout`**（`src/ai_rd_team/artifacts/layout.py`）：描述交付物落位规则的 frozen dataclass，包含 `code_dirs` / `docs_root` / `docs_subdirs` / `tests_root` / `tests_mode` / `deploy_root` / `root_level_files` 字段。
- `DEFAULT_LAYOUTS` 6 档内置布局：`python` / `go` / `js` / `vue3` / `wechat-mp` / `fallback`。
- `ProjectLayout.from_yaml(path)`：从架构师运行时声明的 `data-project-layout.yaml` 加载（支持 `base: <preset>` + `overrides: {...}` 合并）。
- `ProjectLayout.from_memory(mm)`：从 memory 的 `tech-stack-selected.md` 关键词推断（Go / Python / Vue / 微信小程序 等）。
- `ArtifactRecorder` 五个新分派方法：`write_code(module, filename)` / `write_doc(category, filename)` / `write_test(module, filename)` / `write_deploy(filename)` / `write_process(kind, name)`，自动按 layout 决定路径。
- `manifest.yaml` 新增 `category` 字段（`delivery` / `process`），每条 entry 可识别两种语义基。
- `TeamEnvironmentManager.initialize()` 按优先级加载 layout：架构师 yaml > `config.artifacts.layout` > memory 推断 > fallback；解析结果写入 `events.jsonl` 的 `project_layout_resolved` 事件便于调试。
- `GET /api/artifacts` 端点从扫 `runtime/artifacts/` 改为读权威 `manifest.yaml`，返回含 `exists` / `size` 字段。
- `GET /api/artifacts/file` 端点新增 `category` query 参数（默认 `delivery` 相对项目根；`process` 相对 runtime_dir）。
- 新增 `docs/07-artifact-placement.md` 用户手册。
- 新增 `openspec/specs/artifact-placement/spec.md` 正式 spec（5 个 requirement）。

### Changed (M7)

- `ArtifactRecorder.__init__` 签名从 `(artifacts_dir)` 改为 `(project_root, runtime_dir, layout)`（破坏性）。
- `manifest.yaml` 位置从 `<runtime>/artifacts/manifest.yaml` 提升到 `<runtime>/manifest.yaml`。
- `manifest` path 语义：`delivery` 条目为项目根相对、`process` 条目为 runtime_dir 相对（含 kind 前缀）。
- `_RUNTIME_SUBDIRS` 删除 `artifacts/**` 系列，新增 `review/` 和 `reports/` 作为过程数据顶层目录。
- 成员 prompt 模板（`src/ai_rd_team/roles/prompt.py`）的"工作目录"段落全面重写，按角色指导不同落位。
- 各角色"期望产出"（`_DEFAULT_ARTIFACTS`）路径更新为新布局。
- `openspec/specs/design/07-artifacts.md` §4（目录结构 / 落位策略 / 角色映射 / 速查表）整体重写为 M7 语义。
- `openspec/specs/design/11-runtime-protocol.md` 目录树去掉 `artifacts/`，加入 `review/` `reports/` `manifest.yaml`。
- `openspec/specs/design/05-roles-skills.md` 角色速查表、工作目录样板更新。
- 4 个 examples 的 `EXPECTED_OUTPUTS.md` + `README.md` 文件树全部对齐新布局。
- `docs/01-getting-started.md § 第 7 步`、`docs/02-configuration.md`（新增 `artifacts.layout` 段 + `security.file_access.writable` 更新）同步。
- CodeBuddy Skill（`plugins/ai-rd-team/skills/ai-rd-team-launcher/SKILL.md`）路径引导更新。
- 版本号 `0.1.0b1` → **`0.2.0a1`**；Classifier `Development Status :: 4 - Beta` → `3 - Alpha`（标记新地基需要真实 E2E 打磨）。

### Removed (M7)

- `ArtifactRecorder.write()` / `write_raw()` 老接口（无 DeprecationWarning 过渡）。
- `ARTIFACT_KINDS` 常量（五类前缀 `spec/data/result/log/report`）。
- 老的 `ArtifactRecorder(artifacts_dir=...)` 构造签名。
- `ROLE_TO_DIR` 作为"落位决策依据"的语义（保留为字符串映射仅作 prompt hint 用途；新增 `ROLE_TO_WRITE_METHOD` 取代其"决定写入方法"的职责）。
- `config.advanced.yaml:artifacts.code_output.strategy` 三档（`in_place` / `artifacts_only` / `both`）的语义——M7 后 `in_place` 成为唯一策略且扩展到所有交付物类型。

---

### Fixed (M6 — CodeBuddy marketplace 规范化)

- **关键修复**：CodeBuddy Skill 目录结构从 M1 起就不符合 CodeBuddy marketplace 规范，导致主 Agent 无法自动识别 `ai-rd-team-launcher` 和 `ai-rd-team-bridge` 两个 Skill，之前的 E2E 全靠人工念"按 bridge.md 协议处理"激活。
  - 原结构（错误）：`<repo>/skills/ai-rd-team-launcher.md`（单文件 + YAML frontmatter）
  - 新结构（标准）：`<repo>/.codebuddy-plugin/marketplace.json` + `<repo>/plugins/ai-rd-team/.codebuddy-plugin/plugin.json` + `<repo>/plugins/ai-rd-team/skills/ai-rd-team-launcher/SKILL.md`（与 `codebuddy-plugins-official` / `obra_superpowers-marketplace` 完全一致）
- `src/ai_rd_team/__init__.py` 新增 `codebuddy_marketplace_dir()`（返回 marketplace 根）；`skills_dir()` 保留作为向后兼容别名，转发到新函数。
- `src/ai_rd_team/cli/main.py::skills` 输出重写，提供三种安装路径：
  - **方式 1（最推荐）**：`codebuddy plugin marketplace add https://github.com/eyjian/ai-rd-team.git`（从 GitHub，无需 clone）
  - **方式 2（二次开发）**：`codebuddy plugin marketplace add <本地路径>`（本地代码变更即时生效）
  - **方式 3（备用）**：`cp -r plugins/ai-rd-team/skills/* ~/.codebuddy/skills/`（跳过 marketplace）
  - 两种 marketplace 方式均已在真机验证：`codebuddy plugin marketplace add` 成功注册，IDE 插件面板重启后出现 ai-rd-team。
- 安装方式支持 CodeBuddy 插件面板的三种范围：用户 / 项目 / 本地。
- `pyproject.toml` 的 `[tool.hatch.build.targets.sdist].include` 补 `plugins` 和 `.codebuddy-plugin`，确保 sdist 带新结构。
- 文档同步：`docs/01-getting-started.md § 第 2 步`、`README.md § 方式 C`、`skills/README.md`（改为迁移说明页）全部重写。

### Planned

- 首次在 GLM-5.1 上的跨模型基线 E2E（见 `docs/follow-ups/GLM51-compat.md`），需 CodeBuddy 侧切换模型会话后补跑
- 多平台 Adapter（Trae / Cursor / Windsurf / Claude Desktop），架构路径待定，见 `openspec/specs/2026-05-04-multi-platform-brainstorming.md`
- 更多内置 Skills（Go+Kratos / Vue3 / 微信小程序的完整 SOP 深化）
- 演示视频录制与文档截图

---

## [0.1.0b1] - 2026-05-04

首个 beta 版本（PEP 440: `0.1.0b1`）。相较 `0.1.0a1`，M5 完成"降低 bridge 负担"能力，E2E 场景下主 Agent 手动应答次数从 11-12 次降到 7 次（降幅 42%），initialize 从 ~38 秒降到 ~7 毫秒。正式进入 Beta：功能冻结、求用户试用、API 不再破坏性变更。

### Added (M5 - reduce-bridge-burden)

- **AutoBridgeResponder**（`src/ai_rd_team/adapter/auto_responder.py`）：file-bridge 协议之上的后台自动应答组件，自动处理 `_version` / `_probe` / `shutdown_request` / `shutdown_response` / `broadcast` 五类 intent，降低 E2E 场景下主 Agent 手动介入次数。真工具类 intent（team_create / task / send_message type=message / team_delete）保持由主 Agent 处理。
- 配置开关 `adapter.auto_bridge`（默认 true）：关闭后完全回退到 M4 行为。
- 配置覆盖 `adapter.version_override` / `adapter.available_tools_override`：替代 bridge 探测的本地默认常量。
- REST 端点 `GET /api/bridge/pending-intents`：返回未被 auto-responder 处理的 intent 列表，含每条 `op` / `hint` / `age_seconds`。
- Web 总览页新增 **Pending bridge intents** 卡片：空态显示"✅ 无需干预"，非空 amber 高亮列出每条 intent 的工具调用提示。
- `events.jsonl` 新增事件类型 `bridge_auto_responded`。
- `docs/06-bridge-and-auto-responder.md`：面向用户的 bridge 协议与 auto-responder 使用说明。
- OpenSpec：新增正式 spec `openspec/specs/adapter-bridge-auto-responder/spec.md`（5 个 requirement），change `reduce-bridge-burden` 归档到 `openspec/changes/archive/2026-05-04-reduce-bridge-burden/`。

### Changed (M5)

- **BREAKING（内部行为）**：`CodeBuddyAdapter.initialize()` 不再通过 bridge 发 `_version` / `_probe` intent，改用本地常量 `DEFAULT_CODEBUDDY_VERSION` / `DEFAULT_AVAILABLE_TOOLS`。同步修改 2 个集成测试断言（`_probe` / `_version` ops 不再出现在 `BridgeSimulator.processed` 中）。
- 旧用户配置无需修改：缺省等价于启用 auto_bridge + 用默认 version/tool 常量。
- `openspec/specs/design/02-adapter.md` §5.2.1、`04-web-panel.md` §4.1、`10-config-schema.md` adapter 节、`11-runtime-protocol.md` §8.3 同步更新。
- Classifier 从 "Development Status :: 3 - Alpha" 升级为 "4 - Beta"。

### Verified (M5)

- `prototype/M4-example2-e2e/VERIFIED-m5.md`：Claude-Opus-4.7 baseline blog-api Standard 档 E2E。
  - 手动应答 **7 次**（M4 baseline 12 次，降幅 42%）
  - initialize **7 ms**（M4 baseline ~38 s）
  - auto-responder 自动应答 4 次 shutdown_request
  - `go build ./...` / `go vet ./...` / biz test 全绿，可执行二进制 27.6 MB
- `pytest` **425 passed**，`ruff check` / `ruff format --check` 全绿，覆盖率保持 83%+。

### Migration

- 从 `0.1.0a1` → `0.1.0b1`：无需任何配置变更。
- 若遇 auto-responder 兼容问题，在 `config.advanced.yaml` 写 `adapter: {auto_bridge: false}` 回退。
- 若 CodeBuddy 升级到不同版本字符串，在 `config.advanced.yaml` 写 `adapter: {version_override: "claude-opus-4.8"}` 覆盖。

### Deferred

- GLM-5.1 基线对比 E2E 从 M5 拆分为独立 follow-up（阻塞外部条件：需 CodeBuddy 侧切到 GLM-5.1 会话执行），跟踪文档 `docs/follow-ups/GLM51-compat.md`。

---

## [0.1.0a1] - 2026-05-04

首个 alpha 版本（PEP 440: `0.1.0a1`）。**M1 + M2 + M3 + M4 四个里程碑全部在真实 CodeBuddy 环境下端到端验证通过**。

### Added

#### M1 - 核心引擎

- `TeamEnvironmentManager` 引擎：initialize / start_run / stop_run 生命周期
- `BaseAdapter` 抽象 + `CodeBuddyAdapter` 实现（通过 FileBasedBridge / CodeBuddyToolBridge）
- `ConfigLoader`：Basic (config.yaml) + Advanced (config.advanced.yaml) 分层合并
- `ConfigInference`：从工作区自动推断项目名 / README 描述 / 技术栈
- `ConfigOnboarding`：3 问对话引导（交互式 + --yes 全默认）
- `PromptRenderer`：7 个内置角色的 Persona + Prompt 模板
- `ArtifactRecorder`：制品目录管理
- `RuntimeStateManager`：current-run / team / members / roster / events / messages 状态持久化
- CLI：`init` / `run` / `status` / `config validate/generate-advanced` 命令

#### M2 - Skills / Memory / 成本 / Hook / 安全

- `SkillsLoader`：三层加载（builtin / global / workspace）+ `builtin:xxx` 强制前缀语法
- `MemoryManager`：`agent.d/` 启动记忆 + `memory.d/` 长期记忆 + `decisions/` ADR
  - Token 预算控制（agent.d 总 ≤ 8K，单文件 ≤ 2K 软警告）
  - ADR 自动编号 + MADR 模板
- 3 个内置 Skills：`python-best-practices` / `pytest-guide` / `code-review-checklist`
- `CostTracker` + `QuotaTracker`：
  - 5 类 RP 事件计量（spawn / message / broadcast / iteration / runtime）
  - 日 / 周 / 月窗口额度
  - smart_pause 预算响应 + WARN 阈值告警
  - 模型降级 semi_auto 建议
- `HookRunner`：
  - 5 个内置 Hook（events_emitter / log_message / state / cost / git_commit）
  - 用户自定义 Hook（shell 命令 + 环境变量占位）
  - when 过滤、priority 排序、timeout、block 级安全校验
- `SecurityGuard`：命令黑名单（13 项危险模式）+ 文件访问白名单 + 日志脱敏
- `broadcast` 能力：`TeamEnvironmentManager.broadcast()` 便捷方法
- 3 个档位 preset YAML：`lite` / `standard` / `full`
- `add_member` + `escalate_mode`：运行中追加成员 + 档位升档
- CLI `config preset --mode <lite|standard|full>` 导出 preset

#### M3 - Web 面板

- FastAPI 服务：14 个读端点 + 4 个写端点 + 2 个 SSE 流
- `EngineProxy`：通过 Engine 代理写类调用
- Vue3 单 HTML 前端（Tailwind CDN + Vue 3.4 CDN）：
  - 7 个页面（总览 / 团队 / 消息 / 制品 / 记忆 / 成本 / 配置）
  - 3 秒轮询 + SSE 实时事件
- **T3.8 首次启动 Web 引导**：
  - `GET /api/onboarding/status` + `POST /api/onboarding/init`
  - 前端模态引导（3 步：档位 / 描述 / 预算）
- **T3.8 smart_pause 预算响应**：
  - `POST /api/run/budget-ack`（continue / stop / raise_budget）
  - `CostTracker.raise_rp_budget` 动态调整预算硬限
  - 前端告警模态
- CLI `serve` 命令：独立启动只读 Web 面板

#### M4 - 打磨发布

- 3 个内置 Skills 新增：`go-kratos-basics` / `vue3-basics` / `wxmini-basics`
  （共 6 个 builtin Skills，覆盖 Python + Go + 前端）
- 3 个完整示例：`examples/01-smart-bookmark` / `02-blog-api` / `03-todo-mini`
  （含 REQUIREMENT + config + agent.d memory + EXPECTED_OUTPUTS）
- `docs/` 使用手册 5 篇（快速上手 / 配置 / 角色 / Skills / 成本）
- `CHANGELOG.md` 按 Keep a Changelog 规范
- `RELEASING.md` 发布流程 + 版本号规范 + 清单
- `py.typed` 标记（支持下游 mypy 严格类型检查）
- CI workflow 新增 build job（验证 wheel 可 import + 关键资源完整）
- `pyproject.toml` 完善：
  - `version = "0.1.0a1"`（PEP 440 alpha）
  - License 更正为 Apache 2.0（原 MIT 与 LICENSE 文件内容不一致）
  - `[project.optional-dependencies].publish`（build + twine）
  - 补充 Classifiers（FastAPI / Typing / AI / Code Generators）
  - URLs 补 Documentation / Changelog
  - Wheel 显式 include 非 .py 资源

### Fixed

M1 真实 E2E 发现的 3 个小问题（commit `8011ad8`）：

- **F1 时间戳精度**：`datetime.now().isoformat()` 产生 naive datetime 且 7 位微秒
  - 新增 `utc_now_iso()` 统一生成 UTC + 毫秒精度
  - 形如 `2026-05-04T03:12:45.678+00:00`
  - 所有 current-run / team / members / events / messages / cost 时间戳字段使用
- **F2 `stop_run` 后 team.yaml 的 team_id 丢失**：
  - Engine.stop_run 从 `ctx.team_handle.team_id` 显式传入
- **F3 成员完成后未更新 state=done**：
  - Shutdown 消息内容加入 "请更新 state=done" 引导
  - Engine 新增 `_finalize_member_states` 兜底把未终态成员标 `terminated`
  - 成员自报 done 的 state 不会被覆盖

M4 example E2E 发现的 2 个示例配置 bug（commit 将提交）：

- **E1 agent.d 文件命名不匹配默认 memory_scope**：
  - 默认 `developer.memory_scope.agent_d` = `["tech-stack-selected", "interface-contracts"]`
  - 3 个 examples 原来使用 `tech-stack.md` / `cli-spec.md` 等自定义名 → 不被加载
  - 修复：所有 examples 的 agent.d 文件改名到约定俗成的 `tech-stack-selected` / `interface-contracts`
  - `examples/README.md` 补充命名约定说明
- **E2 Bridge timeout 默认 60 秒，真实环境不够**：
  - CodeBuddy 主 Agent 响应 `task` / `send_message` 通常 60-90 秒
  - 修复：所有 examples 的 `config.advanced.yaml` 加 `adapter.bridge_timeout_seconds: 300`
  - 注意：该字段必须放 advanced（basic schema 不包含 adapter）

M4 example2 (BlogAPI) E2E 发现的 1 个代码 bug：

- **C1 ConfigLoader._build_role 完全覆盖，不与 builtin 合并**：
  - 现象：config.advanced.yaml 只写 `roles.architect.skills` 时，
    display_name / persona / memory_scope 等字段被默认值覆盖
  - 根因：`_build_role(name, raw)` 直接用 raw dict 字段的默认值构建 Role，
    不查询 `builtin_roles()` 的默认
  - 修复：`_build_role` 改为 merge 语义，仅覆盖 raw 中显式指定的字段，
    其余从 `builtin_roles()[name]` 继承；builtin 不存在时用 dataclass 默认
  - 新增 4 个回归测试（TestRoleMergeWithBuiltin）

### Verified

五次真实 CodeBuddy 环境 E2E 报告：

- `prototype/M1-real-e2e/REPORT.md`：M1 基础引擎验证
- `prototype/M2-real-e2e/REPORT.md`：Skills + Memory + Cost + Hook 全链路验证
  - 成员产出 **15 个 pytest parametrize 测试全过**
  - 深度引用 `python-best-practices` / `pytest-guide` Skill
- `prototype/M3-real-e2e/REPORT.md`：Web 面板 + driver/serve 并行验证
  - 成员产出 **23 个 pytest 测试全过**（含 bool 陷阱 + 递推验证）
  - Web 引导 + 面板实时刷新端到端可用
- `prototype/M4-example-e2e/VERIFIED.md`：`examples/01-smart-bookmark` 示例端到端验证
  - 成员产出 **28 个 pytest 测试全过** + 可 `pip install -e .` 的命令行工具
  - **自动从 URL 抓取网页 title**（超出需求，展示 Skills 引导的主动性）
  - 发现并修复 2 个 example 配置 bug（见下方 Fixed: E1/E2）
- `prototype/M4-example2-e2e/VERIFIED.md`：`examples/02-blog-api`（Standard 档 4 成员并行）
  - architect + developer × 2 + tester 并行工作
  - **28 文件产出**（proto + schema + biz 层 + pb.go 骨架 + 29 个 t.Run 测试骨架）
  - **成员自主协作**：dev_2 主动与 architect 约定 module 名；tester 用 app_stub.go 解耦 dev_2 的 wireApp
  - 虽然 3 分钟内未完成完整项目（go build 差 1 个包），但协作行为验证充分
  - 发现并修复 1 个代码层 bug（见下方 Fixed: C1）

### Tested

- 393 个测试全部通过（unit + integration + E2E 烟测）
- 整体覆盖率 85%
- `ruff check` + `ruff format` 全绿

### Known Limitations

- 仅支持 CodeBuddy 适配器（Trae / Qoder Adapter 留待后续）
- 只支持 Lite / Standard 档位充分验证（Full 档仅单测覆盖，E2E 未跑）
- Web 面板无鉴权（只监听 127.0.0.1，不适合暴露到公网）
- SSE 在 FastAPI TestClient 下有终止问题（已知，不影响实际使用）
- 成本校准算法（设计文档 §4）M2 阶段暂用固定权重，校准留待后续
