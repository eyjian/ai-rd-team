# ai-rd-team 实现路线图

> 文档版本：v1.0
> 日期：2026-05-04
> 状态：实现准备
> 依赖：12 份详细设计文档（`openspec/specs/design/00-11`）

---

## 1. 总览

### 1.1 目标

把 12 份详细设计（10,764 行）拆解成**可执行、可验收、可并行**的实现任务，形成 4 个里程碑、~40 个任务、3-4 周总工作量的实施计划。

### 1.2 实施原则

1. **核心链路优先**：按"能跑通一个最小例子"的顺序推进
2. **测试驱动**：每个模块实现时同步写单元测试（覆盖率 ≥ 80%）
3. **真实集成替代过度抽象**：Adapter Bridge 用文件 IO 即可，不引入 gRPC/队列
4. **里程碑可演示**：每个 M 结束后能给用户演示一个具体场景
5. **不追求一次完美**：M1 先跑通，M4 再打磨

### 1.3 非目标（本路线图不包含）

- ❌ 需求澄清与架构重新设计（已在详细设计阶段完成）
- ❌ 性能优化、大规模测试（延后到 v1.1）
- ❌ 多平台 Adapter（Trae/Qoder，v1.1 再做）
- ❌ UI/UX 精细打磨（M4 简化版即可）

---

## 2. 四个里程碑

| 里程碑 | 目标 | 预计工作量 | 可演示内容 |
|--------|------|----------|----------|
| **M1：骨架跑通** | 最小端到端链路 | 5-7 天 | CLI 启动一个 2 人团队，写出一个计算器 |
| **M2：完整团队** | 7 角色 + 分档 + 成本控制 | 7-10 天 | Standard 档完整开发一个模块 |
| **M3：Web 面板** | 观测 + 控制 | 3-5 天 | 浏览器看到成员状态 / 成本 / 制品 |
| **M4：打磨发布** | 文档 / 示例 / 打包 | 3-5 天 | pip 安装、README 跑通 |

**总计**：18-27 天（3-4 周），单人全职。若并行可压缩到 2-3 周。

---

## 3. M1：骨架跑通（5-7 天）

**目标**：实现最小可跑的端到端链路。能用 2 个成员（architect + developer）做出一个 hello world 级别的代码。

### 3.1 范围

✅ **包含**：
- 项目骨架 + 配置加载（零配置 + Basic + 智能推断）
- 最小 BaseAdapter + CodeBuddyAdapter（Bridge 模式 C）
- 最小 Engine（create_team / spawn_member / send_message）
- 2 个角色（architect + developer）+ Prompt 模板渲染
- runtime/ 基础目录结构
- artifacts/ 基础写入（直写 + manifest）
- CLI：`ai-rd-team run "需求"`

❌ **不包含**：
- Web 面板（M3）
- 成本控制 / 模型降级（M2）
- Skills 加载（M2）
- Memory 系统（M2）
- Hook（M2）
- 其他 5 个角色（M2）

### 3.2 任务清单（13 个）

| # | 任务 | 依赖 | 对应设计文档 | 工作量 |
|---|------|------|-------------|-------|
| T1.1 | 项目骨架（pyproject.toml + src 布局 + 测试框架 + .gitignore） | - | - | 0.5d |
| T1.2 | 配置数据类（EffectiveConfig / BasicConfig 等 dataclass） | T1.1 | 10 §8 | 0.5d |
| T1.3 | ConfigInference 智能推断 | T1.2 | 10 §2B | 0.5d |
| T1.4 | ConfigOnboarding 对话引导（CLI 交互） | T1.2 | 10 §2A | 0.5d |
| T1.5 | ConfigLoader 加载合并 + JSON Schema 校验 | T1.2,T1.3 | 10 §2,§9 | 1d |
| T1.6 | BaseAdapter 抽象接口 + dataclass | T1.1 | 02 §3 | 0.5d |
| T1.7 | CodeBuddyToolBridge（FileBased 模式 C） | T1.6 | 02 §5 | 1d |
| T1.8 | CodeBuddyAdapter（create_team/spawn_member/send_message） | T1.6,T1.7 | 02 §6 | 1d |
| T1.9 | PromptRenderer（角色 Prompt 模板） | T1.2 | 05 §7 | 0.5d |
| T1.10 | TeamEnvironmentManager 主类 + 子管理器骨架 | T1.5,T1.8,T1.9 | 01 §3 | 1d |
| T1.11 | RuntimeStateManager（写 current-run/state/members） | T1.10 | 01 §6, 11 §3-4 | 0.5d |
| T1.12 | ArtifactRecorder（基础直写 + manifest） | T1.10 | 07 §4,§9 | 0.5d |
| T1.13 | CLI 入口（`ai-rd-team run`）+ 端到端烟测 | 全部 | - | 0.5d |

### 3.3 M1 验收标准

- ✅ 零配置场景：在空目录运行 `ai-rd-team run "写一个计算器"`，触发 3 问引导，生成 config.yaml，2 个成员协作产出 calculator.py
- ✅ 生成的 `runtime/artifacts/` 包含 design-note.md + calculator.py
- ✅ `runtime/state/members/*.yaml` 反映真实状态
- ✅ `runtime/events.jsonl` 记录全部事件
- ✅ 单元测试覆盖率 ≥ 70%（M1 放宽）
- ✅ 核心接口（ConfigLoader / Adapter / Engine）的契约测试通过

---

## 4. M2：完整团队（7-10 天）

**目标**：完整 7 角色 + 分档 + 成本控制 + Skills + Memory。Standard 档能跑完整开发流程。

### 4.1 范围

✅ **包含**：
- 剩余 5 个角色（pm / analyst / reviewer / tester / devops）
- 可伸缩角色实例化（developer × N / reviewer × N / tester × N）
- Skills 三层加载（builtin / global / workspace）
- Memory 三层系统（agent.d / memory.d / decisions）
- 成本控制（CostTracker + Budget + smart_pause）
- 模型降级（semi_auto CodeBuddy 模式）
- Hook 系统（触发点 + 内置 Hook）
- 安全约束（命令/文件白黑名单）
- 档位 preset（Lite / Standard / Full）
- 广播消息 + 可伸缩成员

### 4.2 任务清单（15 个）

| # | 任务 | 依赖 | 设计文档 | 工作量 |
|---|------|------|---------|-------|
| T2.1 | SkillsLoader（三层加载 + 合并） | M1 | 05 §6 | 0.5d |
| T2.2 | MemoryManager（读写 agent.d/memory.d/decisions） | M1 | 06 §3-5 | 1d |
| T2.3 | ADR 编号生成 + 模板 | T2.2 | 06 §5 | 0.5d |
| T2.4 | 剩余 5 个角色的 persona.md + 默认 Skills | T2.1 | 05 §3 | 1d |
| T2.5 | 可伸缩角色实例化（multiple developer 等） | M1 | 05 §4 | 0.5d |
| T2.6 | 广播消息（Adapter.broadcast） | M1 | 02 §6 | 0.5d |
| T2.7 | CostTracker（5 类事件计量） | M1 | 08 §3 | 1d |
| T2.8 | Budget + smart_pause 流程 | T2.7 | 08 §4 | 1d |
| T2.9 | QuotaTracker（日/周/月窗口） | T2.7 | 08 §5 | 0.5d |
| T2.10 | 模型降级 semi_auto（CodeBuddy 提示切换） | T2.7 | 08 §6 | 0.5d |
| T2.11 | HookRunner（触发点 + 环境变量 + 超时） | M1 | 09 §3 | 1d |
| T2.12 | 内置 5 个 Hook（log_message / state / cost / events / git） | T2.11 | 09 §4 | 0.5d |
| T2.13 | 安全约束（commands 白黑名单 + file_access + 敏感脱敏） | M1 | 09 §5-7 | 1d |
| T2.14 | 档位 preset（Lite / Standard / Full YAML） | M1 | 10 §5 | 0.5d |
| T2.15 | 升档机制（运行中加成员） | M1,T2.5 | 01 §11 | 0.5d |

### 4.3 M2 验收标准

- ✅ Standard 档跑通完整需求：PRD → 架构 → 并行开发 → 评审 → 测试
- ✅ Lite / Full 档均可切换启动
- ✅ 广播消息可用且计入成本
- ✅ 成员主动写入 memory.d（决策 → ADR）
- ✅ 预算触达 75%/100% 时能触发正确行为（semi_auto 提示 / smart_pause）
- ✅ Hook 能正确拦截并修改消息
- ✅ 敏感命令（如 `rm -rf /`）被拦截
- ✅ 单元测试覆盖率 ≥ 80%

---

## 5. M3：Web 面板（3-5 天）

**目标**：浏览器端可观测 + 可控制。首次启动即输入需求的引导。

### 5.1 范围

✅ **包含**：
- 后端 Service API（REST + SSE）
- 前端静态页（Vue3 + Tailwind CDN 加载）
- 8 个页面（总览 / 团队 / 消息 / 制品 / 记忆 / 成本 / 配置 / 历史）
- SSE 实时事件订阅
- 首次启动引导（Web 版，同步 CLI）
- smart_pause 模态框

### 5.2 任务清单（8 个）

| # | 任务 | 依赖 | 设计文档 | 工作量 |
|---|------|------|---------|-------|
| T3.1 | Flask/FastAPI 服务骨架 + EngineProxy | M2 | 03 §3,§10 | 0.5d |
| T3.2 | REST 端点（read 类全部 + 写入 `/api/commands`） | T3.1 | 03 §4-6 | 1d |
| T3.3 | SSE 事件推送（events / cost / member） | T3.1 | 03 §7 | 0.5d |
| T3.4 | 前端骨架（单 HTML + Vue3 + Router + Store） | T3.1 | 04 §4-5 | 0.5d |
| T3.5 | 总览页 + 团队页 + 消息页 | T3.4 | 04 §6 | 1d |
| T3.6 | 制品页 + 记忆页 + 成本页 | T3.4 | 04 §6 | 1d |
| T3.7 | 配置页（Basic/Advanced 双视图） + 历史页 | T3.4 | 04 §6 | 0.5d |
| T3.8 | 首次启动 Web 引导 + smart_pause 模态框 | T3.5 | 04 §7 | 0.5d |

### 5.3 M3 验收标准

- ✅ `ai-rd-team run` 后浏览器自动打开面板
- ✅ 总览页实时显示成员状态 / 成本 / 进度
- ✅ SSE 流稳定（断网重连）
- ✅ 可暂停 / 恢复 / 升档
- ✅ 可在配置页编辑 Basic/Advanced 并生效
- ✅ smart_pause 触发时弹窗，用户选项可用
- ✅ E2E 测试：首次启动 → 完成运行 → 查看归档

---

## 6. M4：打磨发布（3-5 天）

**目标**：文档齐全、示例可跑、打包可发布。

### 6.1 任务清单（7 个）

| # | 任务 | 依赖 | 工作量 |
|---|------|------|-------|
| T4.1 | README.md 快速开始 + 截图 + 演示 gif | M3 | 0.5d |
| T4.2 | 默认 Skills 内置（Go+Kratos / Vue3 / 微信小程序） | M2 | 1d |
| T4.3 | 3 个演示案例（SmartBookmark / 博客 / CRM 模块） | M2,M3 | 1d |
| T4.4 | pyproject.toml 完善 + 发布到 PyPI（test 仓） | M3 | 0.5d |
| T4.5 | CHANGELOG.md + 版本号规范 | - | 0.2d |
| T4.6 | 使用手册（`docs/`）：配置 / 角色 / Skills / 成本 | M3 | 1d |
| T4.7 | 集成测试 + CI（GitHub Actions 跑 pytest + lint） | M2 | 0.5d |

### 6.2 M4 验收标准

- ✅ `pip install ai-rd-team && ai-rd-team init` 走通
- ✅ README 照抄能跑通首个例子
- ✅ 3 个演示案例可复现
- ✅ GitHub Actions CI 绿色
- ✅ PyPI test 仓发布成功（暂不发正式仓）

---

## 6A. M5：降低 bridge 负担（~2 天）✅ 已完成（2026-05-04 归档）

**目标**：降低 file-based bridge 在 E2E 场景下对主 Agent "在线手动应答"的依赖，把一次 Standard 档 blog-api E2E 的主 Agent 手动应答次数从 **~11** 降到 **~6**。

**关联 openspec change**：`openspec/changes/archive/2026-05-04-reduce-bridge-burden/`（已归档）
**关联 capability**：`openspec/specs/adapter-bridge-auto-responder/spec.md`（正式 spec）

**实际结果**：
- ✅ 手动应答从 11-12 次 → **7 次**（降幅 42%）
- ✅ initialize 从 ~38 秒 → **7 毫秒**（本地化）
- ✅ AutoBridgeResponder 后台线程自动应答 4 条 shutdown_request
- ✅ pytest 425 全绿，ruff 全绿，`go build ./...` 通过
- 🔀 GLM-5.1 基线对比拆分为独立 follow-up（参见 `docs/follow-ups/GLM51-compat.md`）——阻塞外部条件：需用户在 CodeBuddy 侧切到 GLM-5.1 会话执行。零代码变更、无 spec delta，不走 openspec change 体系。

### 6A.1 范围

✅ **包含**：
- F 优化：`CodeBuddyAdapter.initialize()` 的 `_version` / `_probe` 本地化，不再发 bridge intent
- D Daemon：`AutoBridgeResponder` 后台线程，自动应答 `_version` / `_probe` / `shutdown_request` / `shutdown_response` / `broadcast`
- 配置开关：`adapter.auto_bridge` 默认 true，可关闭回退到 M4 行为
- Web 面板：Pending bridge intents 卡片，清楚展示"需主 Agent 介入"的 intent
- 观测：`events.jsonl` 新增 `bridge_auto_responded` 事件
- 真实 E2E 验证：Claude-Opus-4.7 + GLM-5.1 两次 baseline 对比

❌ **不包含**：
- 自动调 CodeBuddy 真工具（team_create / task / send_message type=message / team_delete 仍由主 Agent 处理）
- 引入 CodeBuddy CLI / REST / IDE 扩展路径
- Trae / Qoder 适配器
- RP → USD 校准

### 6A.2 验收标准

- ✅ `pytest -q` 全绿（≥ 425 用例）
- ✅ blog-api Standard 档 E2E 手动应答 ≤ 6 次
- ✅ 产物 `go build ./...` 通过
- ✅ 同一代码在 GLM-5.1 上也能跑通 E2E（作为"模型无关性"证据）
- ✅ CHANGELOG 记录，openspec archive 归档

---

## 7. 关键风险与应对

| 风险 | 可能性 | 影响 | 应对 |
|------|--------|------|------|
| CodeBuddy 工具 API 变动 | 中 | 高 | Adapter 版本探测（02 §9），多版本兼容 |
| Bridge 模式 C 宿主响应不及时 | 中 | 中 | intent 超时机制 + 重试（02 §5.3） |
| 成员卡死不退出 | 低 | 中 | shutdown + kill 兜底（01 §8） |
| 首次引导交互体验差 | 中 | 中 | M1 后跑 3-5 个真人测试 |
| 成本控制误差过大 | 低 | 低 | 第一期用资源单位，第二期校准 |
| Web 面板性能差（大量事件） | 中 | 低 | 事件限流 + 前端虚拟滚动 |

---

## 8. 并行化建议

单人全职推荐串行 M1 → M2 → M3 → M4，有 2 人可并行如下：

| 阶段 | 成员 A | 成员 B |
|------|-------|-------|
| M1 | T1.1-T1.5（配置） | T1.6-T1.8（Adapter） |
| M1 后期 | T1.9-T1.13 | 为 M2 做 Skills/Memory 原型 |
| M2 | T2.1-T2.5（角色 Skills Memory） | T2.7-T2.13（成本 Hook 安全） |
| M3 | T3.1-T3.3（后端） | T3.4-T3.8（前端） |
| M4 | T4.1-T4.3（文档示例） | T4.4-T4.7（发布 CI） |

---

## 9. 里程碑交付物

### M1 交付物
- `src/ai_rd_team/` 核心代码（config / adapter / engine / cli）
- `tests/` 单元测试 + 一个端到端烟测
- 能跑通"计算器"案例

### M2 交付物
- 7 角色完整定义 + 可伸缩机制
- Skills / Memory / Cost / Hook / Security 全部可用
- Lite/Standard/Full 三档 preset
- 能跑通"用户管理模块"案例

### M3 交付物
- Web 面板（单 HTML + 后端 API）
- SSE 实时事件流
- 能通过浏览器观测 + 控制整个运行

### M4 交付物
- PyPI test 发布版
- README + docs/ 文档
- 3 个演示案例
- CI 绿色

---

## 10. 下一步决策

实现准备阶段还需确认：

1. **Python 版本**：建议 3.10+（用 `match` / 类型注解）
2. **依赖库选型**：
   - YAML：`pyyaml` 或 `ruamel.yaml`（推荐后者保留注释）
   - JSON Schema：`jsonschema`
   - 文件监听：`watchdog`
   - Web 后端：`FastAPI` 或 `Flask`（推荐前者，SSE 好）
   - CLI：`typer`（推荐，类型化）或 `click`
   - 测试：`pytest` + `pytest-cov`
3. **代码风格**：`ruff` + `mypy --strict`
4. **目录布局**：`src/` 布局 vs flat（推荐 src）
5. **License**：已有 LICENSE，确认 MIT

这些将在 B2 搭建项目骨架时具体落实。

---

## 11. 与详细设计的映射关系

每个任务都明确对应设计文档的章节，便于实现时快速查阅。实现者应该：

1. 实现某任务前，**先读对应设计文档相关章节**
2. 发现设计与实际不符时，**先提 issue 讨论再改代码**，同时更新设计文档
3. 每完成一批任务，**对照验收标准自测**

---

## 附录 A：任务粒度说明

- **0.5d（半天）**：2-4 小时实现 + 1-2 小时测试
- **1d（一天）**：4-6 小时实现 + 2-3 小时测试
- 工作量未包含需求澄清、设计改动、真人测试的时间
- 单人工作量估算不适用大团队（团队需额外沟通成本）
