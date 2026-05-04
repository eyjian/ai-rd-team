# ai-rd-team

**自主驱动的数字人研发团队** —— 多 AI Agent 协作研发框架

> 核心理念：AI 时代的研发不应该是"提示词工程"，而应该是"搭一个数字人团队让他们自己协作"。

---

## 当前状态

🚧 **开发中**（v0.1.0-alpha）：

- ✅ 头脑风暴完成（34 维度，`openspec/specs/2026-04-14-ai-rd-team-brainstorming.md`）
- ✅ 原型验证通过（`prototype/REPORT.md`）
- ✅ 详细设计完成（12 份，10,764 行，`openspec/specs/design/`）
- ✅ 实现路线图（`openspec/specs/design/ROADMAP.md`）
- ✅ 项目骨架搭建
- ✅ M1 代码实现（181 测试，85% 覆盖率）
- ✅ **M1 真实 CodeBuddy 端到端验证通过**（`prototype/M1-real-e2e/REPORT.md`）
- 🚧 M2 准备中

---

## 快速开始（骨架阶段）

### 安装

```bash
# 克隆
git clone https://github.com/eyjian/ai-rd-team.git
cd ai-rd-team

# 安装（开发模式）
pip install -e ".[dev]"

# 验证
ai-rd-team version
# ai-rd-team v0.1.0
```

### 两种使用方式

#### 方式 A：Python 包 + CLI（推荐）

```bash
# 首次运行会触发 3 问引导（20 秒完成）
cd my-project
ai-rd-team run "做一个日报系统"

# 其他命令
ai-rd-team init --yes            # 非交互生成默认 config.yaml
ai-rd-team config show           # 查看当前配置
ai-rd-team config advanced       # 生成完整 config.advanced.yaml
ai-rd-team config validate       # 校验配置
ai-rd-team skills                # 查看 Skills 目录路径
```

**重要前提**：目前 ai-rd-team 的 Adapter 只支持 CodeBuddy，Python 引擎需要**主 Agent 代调 CodeBuddy 工具**。所以 `ai-rd-team run` 命令通常**在 CodeBuddy 会话内启动**（由 CodeBuddy 的主 Agent 通过 `execute_command` 执行），而不是独立的终端。

#### 方式 B：作为 CodeBuddy Skill 使用

安装 Python 包后，把 `skills/` 目录链接到 CodeBuddy Skills 目录：

```bash
# 查看 Skills 目录路径
ai-rd-team skills

# macOS/Linux 链接（路径按实际输出替换）
ln -s $(python -c "import ai_rd_team; print(ai_rd_team.skills_dir())") \
      ~/.codebuddy/plugins/marketplaces/local/skills/ai-rd-team
```

然后在 CodeBuddy 会话中：

```
用户：use skill ai-rd-team-launcher
用户：做一个 TodoList 小程序
```

`ai-rd-team-launcher` Skill 会引导主 Agent 启动 Python 引擎，
`ai-rd-team-bridge` Skill 自动激活处理引擎的工具调用。

### 其他开发命令

```bash
pytest                     # 跑测试
ruff check src tests       # Lint
ruff format src tests      # 格式化
mypy src                   # 类型检查
```

目前 CLI 的 `run` 命令可用但需要 CodeBuddy 主 Agent 配合 bridge Skill。若想在没有主 Agent 的情况下测试引擎，可以用 `BridgeSimulator`（见 `tests/integration/test_e2e_with_simulator.py`）。

---

## 核心理念

传统 AI 编程助手是"一问一答"或"工作流编排"。

**ai-rd-team 不同**：它模拟一个真实的数字人研发团队，成员之间自主协作、异步通信、共享记忆和制品，整体自主推进研发工作。

- **7 角色团队**：项目经理 / 需求分析 / 架构师 / 开发者 / 检视者 / 测试 / DevOps
- **三档运行**：Lite / Standard / Full（按需求规模选择）
- **零配置可用**：首次启动 ≤3 个问题，20 秒开工
- **成本可控**：Resource Points 计量 + 档位预算 + 模型降级 + 日/周/月额度
- **多平台适配**：CodeBuddy（第一期）→ Trae / Qoder / Cursor（未来）

---

## 文档索引

### 顶层文档

- `openspec/specs/2026-04-14-ai-rd-team-brainstorming.md`：头脑风暴全记录（34 维度）
- `openspec/specs/design/ROADMAP.md`：实现路线图（4 里程碑 / ~40 任务）
- `prototype/REPORT.md`：原型验证报告

### 详细设计（12 份）

| # | 文档 | 主题 |
|---|------|------|
| 00 | `overview.md` | 架构总览 |
| 01 | `engine.md` | 引擎层（实现级） |
| 02 | `adapter.md` | 适配层（实现级） |
| 03 | `service-api.md` | REST API |
| 04 | `web-panel.md` | Web 面板 |
| 05 | `roles-skills.md` | 角色与 Skills |
| 06 | `memory-system.md` | 三层记忆 |
| 07 | `artifacts.md` | 制品格式 |
| 08 | `cost-control.md` | 成本控制 |
| 09 | `hooks-security.md` | Hook 与安全 |
| 10 | `config-schema.md` | 配置 Schema（实现级） |
| 11 | `runtime-protocol.md` | 运行时协议（实现级） |

均位于 `openspec/specs/design/`。

---

## 项目结构

```
ai-rd-team/
├── src/ai_rd_team/         # 源代码
│   ├── config/             # 配置加载（对应 10-config-schema）
│   ├── adapter/            # 平台适配层（对应 02-adapter）
│   ├── engine/             # 引擎（对应 01-engine）
│   ├── roles/              # 角色与 Skills（对应 05）
│   ├── memory/             # 记忆系统（对应 06）
│   ├── artifacts/          # 制品（对应 07）
│   ├── cost/               # 成本控制（对应 08）
│   ├── hooks/              # Hook 与安全（对应 09）
│   ├── runtime/            # 运行时文件（对应 11）
│   ├── service/            # REST API（对应 03）
│   ├── web/                # Web 静态资源（对应 04）
│   ├── cli/                # CLI 入口
│   └── utils/              # 工具函数
├── tests/
│   ├── unit/               # 单元测试
│   └── integration/        # 集成测试
├── openspec/specs/
│   ├── 2026-04-14-ai-rd-team-brainstorming.md
│   └── design/             # 12 份详细设计
├── prototype/              # 原型验证产物（已归档）
├── 2026/                   # 年度归档（副本）
└── .github/workflows/ci.yml
```

---

## 开发指南

### 实现路线图

见 `openspec/specs/design/ROADMAP.md`，共 4 个里程碑：

- **M1 骨架跑通**（5-7 天）：配置 + Adapter + Engine + 2 角色 + CLI
- **M2 完整团队**（7-10 天）：7 角色 + 分档 + 成本 + Skills + Memory + Hook
- **M3 Web 面板**（3-5 天）：REST API + SSE + 8 页面
- **M4 打磨发布**（3-5 天）：README + 示例 + PyPI

### 代码规范

- Python 3.10+，类型注解必加
- Ruff 管理 lint + format
- Mypy 类型检查（M2 起强制）
- 单测覆盖率 ≥ 80%（M2 起要求）
- 提交信息用中文，主题行 ≤ 50 字

### 贡献流程

1. 读对应的设计文档
2. 从 ROADMAP 选一个任务
3. 开分支实现 + 写测试
4. 本地跑通 `ruff + mypy + pytest`
5. 提 PR

---

## 许可

MIT License（见 `LICENSE`）

---

## 致谢

- 原型阶段的验证基于 [CodeBuddy](https://codebuddy.ai) Team Mode
- 头脑风暴与详细设计由 CodeBuddy 辅助完成，人工主导决策
