# ai-rd-team

**自主驱动的数字人研发团队** —— 多 AI Agent 协作研发框架

> 不是"提示词工程"，不是"工作流编排"。  
> 是"你搭一个数字人团队，他们自己协作把活干完"。

[![Tests](https://img.shields.io/badge/tests-425%20passed-brightgreen)]()
[![Coverage](https://img.shields.io/badge/coverage-83%25-green)]()
[![Python](https://img.shields.io/badge/python-3.10+-blue)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)]()
[![Version](https://img.shields.io/badge/version-0.1.0b1-orange)]()

---

## 这是什么？

给 AI 主 Agent（目前是 CodeBuddy）加一个 Python 引擎，让它**派生 2-7 个子 Agent 成员**组成研发团队，每个成员带**自己的角色/技能/记忆**，成员之间**P2P 通信**、**自主决策**、**协作产出文件**——你看着面板等他们完工即可。

**一张图概括**：

```
你（主 Agent 会话）
  │
  │  ai-rd-team run "需求描述"
  ▼
┌─────────────────────────────────────────┐
│  TeamEnvironmentManager（Python 引擎）   │
│   ├─ 装配团队（按 Lite/Standard/Full）   │
│   ├─ 注入 Skills + Memory 到每个 Prompt  │
│   ├─ 成本追踪 + Hook + 安全约束          │
│   └─ Web 面板 (127.0.0.1:8765)          │
└─────────────┬───────────────────────────┘
              │ 通过 BaseAdapter + Bridge 协议
              ▼
      ┌───────┴────────┐
      │  主 Agent      │ ← 代理 team_create / task / send_message
      │  (CodeBuddy)   │    等平台工具调用
      └───┬────┬───┬───┘
          │    │   │
      ┌───▼┐ ┌─▼─┐ ┌─▼─┐
      │ PM │ │Dev│ │QA │  ← 子 Agent 成员们（自主工作）
      └────┘ └───┘ └───┘
```

---

## 可信度：五次真实 CodeBuddy E2E 全部跑通

不是「本地 mock 测试通过」，是**真实 CodeBuddy Claude-Opus-4.7 派发 subagent 干了活**：

| 里程碑 | 任务规模 | 成员产出 | 报告 |
|-------|---------|---------|------|
| M1 E2E | 1 个 developer 跑计算器 | 1 源码文件 | [prototype/M1-real-e2e/REPORT.md](prototype/M1-real-e2e/REPORT.md) |
| M2 E2E | Lite 档 + 自定义 Hook + agent.d 记忆 | 源码 + **15 个 pytest 测试** | [prototype/M2-real-e2e/REPORT.md](prototype/M2-real-e2e/REPORT.md) |
| M3 E2E | Web 引导 + 面板实时刷新 | 源码 + **23 个测试** + 报告 | [prototype/M3-real-e2e/REPORT.md](prototype/M3-real-e2e/REPORT.md) |
| M4 Example 01 | `examples/01-smart-bookmark`（Lite） | **10 文件 + 28 测试 + 可 pip install** | [prototype/M4-example-e2e/VERIFIED.md](prototype/M4-example-e2e/VERIFIED.md) |
| **M4 Example 02** | `examples/02-blog-api`（Standard × 4 成员） | **28 文件 Go+Kratos，多成员自主协作** | [prototype/M4-example2-e2e/VERIFIED.md](prototype/M4-example2-e2e/VERIFIED.md) |

**Skills 是否真的影响行为？是。** M4 的成员：
- **没被要求** 做 `title_fetcher` 依赖注入，但它为了测试能离线主动这么做
- **没被要求** 加 CLI 的 `--store` 覆盖，但它为了方便测试加了
- **没被要求** 用 `fsync` 保证磁盘持久，但 `python-best-practices` Skill 里写了"关键文件用原子写"它就做到位了
- 从 URL **实际抓取网页 title**（go-kratos.dev 的真实页面标题）

---

## 当前状态（v0.1.0b1，beta）

| 里程碑 | 状态 | 交付物 |
|-------|------|-------|
| M1 核心引擎 | ✅ | 181 测试，Engine + Adapter + Config + CLI |
| M2 完整团队 | ✅ | Skills + Memory + Cost + Hook + Security + Preset + 升档 |
| M3 Web 面板 | ✅ | 14 读 + 4 写端点 + SSE + Vue3 单页 + Web 引导 |
| M4 打磨发布 | ✅ | README + docs/ + 3 个示例 + 6 内置 Skills + CHANGELOG + CI |
| M5 减轻 bridge 负担 | ✅ | AutoBridgeResponder + Web Pending 卡片（E2E 手动应答 12→7，降幅 42%） |

**设计文档**：`openspec/specs/design/` 下 12 份共 10,764 行，覆盖架构总览 → 引擎 → 适配层 → REST API → Web 面板 → 角色 → 记忆 → 制品 → 成本 → Hook → 配置 → 运行时协议。

---

## 5 分钟快速开始

### 前置要求

- Python 3.10+
- CodeBuddy IDE（Trae / Qoder 的适配器尚未实现）
- 一个你想让 AI 团队干活的工作区目录

### 安装

```bash
# 开发模式（推荐，便于看代码和本地修改）
git clone https://github.com/eyjian/ai-rd-team.git
cd ai-rd-team
pip install -e ".[dev]"

# 或（未来）从 PyPI 装
# pip install ai-rd-team

# 验证
ai-rd-team version
# → ai-rd-team 0.1.0
```

### 方式 A：Web 面板引导（最友好）

```bash
# 1. 进入你的项目
cd ~/projects/my-todo-app

# 2. 启动 Web 面板（只读模式也 OK）
ai-rd-team serve --port 8765

# 3. 浏览器打开 http://127.0.0.1:8765
#    首次会自动弹出引导模态，3 步填写：
#    - 项目规模（Lite / Standard / Full）
#    - 项目描述
#    - 预算（RP/次）
#    → 生成 .ai-rd-team/config.yaml

# 4. 在 CodeBuddy 会话中启动引擎
#    此时 Web 面板会实时显示成员状态和产出
```

### 方式 B：纯 CLI

```bash
cd ~/projects/my-todo-app

# 首次运行会触发 3 问引导（20 秒完成）
ai-rd-team init --yes       # 用默认值非交互生成 config.yaml
# 或
ai-rd-team init              # 交互式 3 问引导

# 查看当前档位对应的 preset
ai-rd-team config preset --list

# 启动运行
ai-rd-team run "做一个带 JWT 登录的 TodoList API"
```

### 方式 C：作为 CodeBuddy Skill 触发（推荐）

ai-rd-team 仓库本身就是一个 **CodeBuddy marketplace**（含 `.codebuddy-plugin/marketplace.json` + `plugins/ai-rd-team/`）。

**最简路径（从 GitHub 装，真机已验证）**：

```bash
# 无需先 git clone，CodeBuddy 会自动拉取
codebuddy plugin marketplace add https://github.com/eyjian/ai-rd-team.git
codebuddy plugin install ai-rd-team@ai-rd-team

# 重启 CodeBuddy IDE → 插件面板会出现 ai-rd-team → 点「安装」选范围
```

然后在 CodeBuddy 会话中：
```
你：用 ai-rd-team 做一个 TodoList 小程序
```

**二次开发 / 离线版本**（先 clone 再从本地路径装）：

```bash
git clone https://github.com/eyjian/ai-rd-team.git
cd ai-rd-team
codebuddy plugin marketplace add "$(pwd)"
codebuddy plugin install ai-rd-team@ai-rd-team
```

详细步骤（3 种安装方式、3 种范围对比、常见坑、验证命令）见 [docs/01-getting-started.md § 第 2 步](docs/01-getting-started.md#第-2-步把-skill-安装到-codebuddy只做一次)。

---

## 核心理念（为什么不是工作流编排？）

| 维度 | 工作流编排 | ai-rd-team |
|------|---------|-----------|
| 控制流 | 中心化 DAG | 成员自主决策 |
| 通信 | Pipeline | P2P send_message |
| 容错 | 节点重试 | 成员自救 + 队友兜底 |
| 灵活度 | 流程固定 | 按需临时 add_member / escalate |
| 调试 | 看 DAG 执行日志 | 看消息流 + 状态文件 |

**ai-rd-team 不预设流程。** 你丢一个需求，架构师决定怎么切分，开发者决定怎么实现，测试者决定怎么覆盖——就像真实团队。

### 7 角色团队

| 角色 | 默认实例 | 可伸缩 | 默认 Skills |
|------|---------|-------|------------|
| pm 项目经理 | 1 | ✗ | - |
| analyst 需求分析 | 1 | ✗ | - |
| architect 架构师 | 1 | ✗ | code-review-checklist |
| **developer 开发者** | 2 | ✓ (max 5) | python-best-practices + pytest-guide |
| **reviewer 检视者** | 1 | ✓ (max 3) | code-review-checklist + python-best-practices |
| **tester 测试** | 1 | ✓ (max 3) | pytest-guide |
| devops | 1 | ✗ | - |

### 三档运行（按需求规模选）

| 档位 | 默认角色 | 预算 (RP/次) | 适用场景 |
|------|---------|-------------|---------|
| Lite | developer × 1 | 120 | 小玩意、几天搞定 |
| Standard | architect + developer × 2 + tester | 400 | 正经项目、几周 |
| Full | 7 角色全启 | 1500 | 大系统、持续迭代 |

**运行中升档**：Lite → Standard → Full（通过 `engine.escalate_mode("standard")` 或 Web 面板）

### 成本控制（Resource Points）

不直接用钱或 token 数计量，用 **RP（Resource Points）**：

| 事件 | RP 成本 |
|------|--------|
| spawn 一个成员 | 40 |
| 单条消息 | 2 |
| broadcast（每目标） | 2 |
| 运行 1 分钟 | 5 |
| 一轮迭代 | 15 |

超 75% 预算自动 **WARN + 模型降级建议**；超 100% 触发 **smart_pause**（前端弹模态让你选：继续 / 提高预算 / 停止）。

---

## 最小化架构

```
src/ai_rd_team/
├── config/        # Basic + Advanced + Inference + Onboarding + Presets
├── adapter/       # BaseAdapter + CodeBuddyAdapter + Bridge 协议
├── engine/        # TeamEnvironmentManager（核心）
├── roles/         # PromptRenderer + SkillsLoader + 7 内置角色
├── memory/        # MemoryManager（agent.d / memory.d / decisions）
├── skills/builtin/# 内置 Skills（python-best-practices 等）
├── cost/          # CostTracker + QuotaTracker
├── hooks/         # HookRunner + SecurityGuard
├── runtime/       # RuntimeStateManager（状态持久化）
├── artifacts/    # ArtifactRecorder
├── service/       # FastAPI Web 面板
└── cli/           # ai-rd-team CLI 入口
```

**读类数据流**：Engine → `.ai-rd-team/runtime/*.yaml/jsonl` → Web 面板**直接读文件**（单向数据流，不走 API）

**写类数据流**：Web 面板 → `EngineProxy` → Engine 方法调用

---

## 常见问题

<details>
<summary><b>为什么只支持 CodeBuddy，不支持 Trae / Qoder / Cursor？</b></summary>

第一期聚焦把引擎 + Adapter 抽象做扎实，所以只实现了 CodeBuddy Adapter。`BaseAdapter` 的接口已经稳定（create_team / spawn_member / send_message / broadcast / shutdown_request / delete_team / get_*_status 等 10 个方法），实现其他平台的 Adapter 预计 1-2 天。欢迎 PR。
</details>

<details>
<summary><b>Bridge 是什么？为什么需要主 Agent 代调工具？</b></summary>

Python 引擎本身不能调 CodeBuddy 的 `task` / `team_create` / `send_message` 等内部工具——这些工具只在主 Agent 的 context 里可用。Bridge 通过 `adapter-intents/` 和 `adapter-results/` 两个文件夹实现**异步 RPC**：引擎写 intent 文件，`ai-rd-team-bridge` Skill 检测到文件就代调工具，把结果写回。
</details>

<details>
<summary><b>我的 Prompt 被注入了什么？</b></summary>

每个成员的 Prompt 包含：
1. 身份与职责（role / persona / team_roster）
2. 工作目录（artifacts 产出路径）
3. 协作约束（允许做 / 禁止做）
4. **Skills**（三层加载的 Markdown）— 核心
5. **Memory**（agent.d 启动记忆）— 核心
6. 关键要求（完成后写报告 + 更新 state）

M3 E2E 实际 Prompt 长度：4646 字。
</details>

<details>
<summary><b>成本 RP 怎么校准到"花了多少钱"？</b></summary>

M2 阶段用固定权重（见上表）。校准算法留待 M5：真实跑多次后按 token 消耗回归得到更精确的权重映射。当前的固定权重对 Lite 档基本够用（错在 ±20% 内）。
</details>

<details>
<summary><b>能接入自己的大模型吗？</b></summary>

引擎本身不调用大模型，大模型的 token 消耗和调用时机完全由主 Agent（CodeBuddy）和 subagent 决定。你能控制的是：
- 档位 / 预算（Basic 配置）
- Skills（影响成员判断与产出）
- Memory（给成员注入背景）
- 模型降级 Hook（触发时给主 Agent 发建议切模型）
</details>

---

## 文档索引

### 顶层

- [CHANGELOG.md](CHANGELOG.md)：版本变更
- [openspec/specs/design/ROADMAP.md](openspec/specs/design/ROADMAP.md)：完整路线图（4 里程碑 / 40+ 任务）
- [openspec/specs/2026-04-14-ai-rd-team-brainstorming.md](openspec/specs/2026-04-14-ai-rd-team-brainstorming.md)：头脑风暴全记录（34 维度）

### 详细设计（12 份）

| # | 主题 | 文档 |
|---|------|------|
| 00 | 架构总览 | [overview.md](openspec/specs/design/00-overview.md) |
| 01 | 引擎层 | [engine.md](openspec/specs/design/01-engine.md) |
| 02 | 适配层 | [adapter.md](openspec/specs/design/02-adapter.md) |
| 03 | REST API | [service-api.md](openspec/specs/design/03-service-api.md) |
| 04 | Web 面板 | [web-panel.md](openspec/specs/design/04-web-panel.md) |
| 05 | 角色与 Skills | [roles-skills.md](openspec/specs/design/05-roles-skills.md) |
| 06 | 三层记忆 | [memory-system.md](openspec/specs/design/06-memory-system.md) |
| 07 | 制品格式 | [artifacts.md](openspec/specs/design/07-artifacts.md) |
| 08 | 成本控制 | [cost-control.md](openspec/specs/design/08-cost-control.md) |
| 09 | Hook 与安全 | [hooks-security.md](openspec/specs/design/09-hooks-security.md) |
| 10 | 配置 Schema | [config-schema.md](openspec/specs/design/10-config-schema.md) |
| 11 | 运行时协议 | [runtime-protocol.md](openspec/specs/design/11-runtime-protocol.md) |

---

## 开发

```bash
pytest                       # 393 测试，~7 秒
pytest -q --no-cov          # 快跑
ruff check src tests         # Lint
ruff format src tests        # 格式化
mypy src                     # 类型检查
pytest --cov=src/ai_rd_team  # 覆盖率报告（term + html）
```

### 代码规范

- Python 3.10+，**类型注解必加**
- Ruff 管理 lint + format（配置见 `pyproject.toml`）
- Mypy `--strict`（允许的 override 写在 `[[tool.mypy.overrides]]`）
- 单测覆盖率 ≥ 80%（当前 85%）
- 提交信息中文，主题行 ≤ 50 字

### 贡献流程

1. 读对应的设计文档
2. 从 ROADMAP 选一个任务
3. 开分支实现 + 写测试
4. 本地跑通 `ruff + pytest`
5. 提 PR

---

## License

[Apache License 2.0](LICENSE)

---

## 致谢

- 原型阶段与三次真实 E2E 验证基于 [CodeBuddy](https://codebuddy.ai) Team Mode
- 头脑风暴与详细设计由 CodeBuddy 辅助完成，人工主导决策
- 部分 Skills 参考 PEP 8 / PEP 20 / Ruff Rules / pytest 官方文档
