# Changelog

All notable changes to `ai-rd-team` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- PyPI 正式发布（目前仅 test 仓）
- 更多内置 Skills（Go+Kratos、Vue3、微信小程序的完整 SOP）
- 演示视频录制与文档截图
- Web 面板增强：成员消息发送、制品在线编辑

---

## [0.1.0-alpha] - 2026-05-04

首个 alpha 版本。**M1 + M2 + M3 三个里程碑全部在真实 CodeBuddy 环境下端到端验证通过**。

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

### Verified

三个真实 CodeBuddy 环境 E2E 报告：

- `prototype/M1-real-e2e/REPORT.md`：M1 基础引擎验证
- `prototype/M2-real-e2e/REPORT.md`：Skills + Memory + Cost + Hook 全链路验证
  - 成员产出 **15 个 pytest parametrize 测试全过**
  - 深度引用 `python-best-practices` / `pytest-guide` Skill
- `prototype/M3-real-e2e/REPORT.md`：Web 面板 + driver/serve 并行验证
  - 成员产出 **23 个 pytest 测试全过**（含 bool 陷阱 + 递推验证）
  - Web 引导 + 面板实时刷新端到端可用

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
