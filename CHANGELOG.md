# Changelog

All notable changes to `ai-rd-team` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- TestPyPI 上传验证（本地构建 + twine check 已通过，上传需要账号 token，流程见 `RELEASING.md`）
- 正式 PyPI 发布（等 TestPyPI 稳定）
- 更多内置 Skills（Go+Kratos / Vue3 / 微信小程序的完整 SOP 深化）
- 演示视频录制与文档截图
- Web 面板增强：成员消息发送、制品在线编辑

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

### Verified

四次真实 CodeBuddy 环境 E2E 报告：

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
  - 发现并修复 2 个 example 配置 bug（见下方 Fixed）

### Tested

- 389 个测试全部通过（unit + integration + E2E 烟测）
- 整体覆盖率 85%
- `ruff check` + `ruff format` 全绿

### Known Limitations

- 仅支持 CodeBuddy 适配器（Trae / Qoder Adapter 留待后续）
- 只支持 Lite / Standard 档位充分验证（Full 档仅单测覆盖，E2E 未跑）
- Web 面板无鉴权（只监听 127.0.0.1，不适合暴露到公网）
- SSE 在 FastAPI TestClient 下有终止问题（已知，不影响实际使用）
- 成本校准算法（设计文档 §4）M2 阶段暂用固定权重，校准留待后续
