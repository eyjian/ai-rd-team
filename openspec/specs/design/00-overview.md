# ai-rd-team 详细设计 - 00 总览

> 文档版本：v1.1
> 日期：2026-05-04（v1.1：加入"低门槛优先"原则与 D15/D16/D17 决策）
> 状态：进行中
> 上游文档：`openspec/specs/2026-04-14-ai-rd-team-brainstorming.md`

---

## 1. 设计文档导航

本详细设计按"核心链路优先"顺序拆分为 12 份文档。每份文档专注一个关切点，标注其详细程度：

| # | 文档 | 颗粒度 | 状态 |
|---|------|-------|------|
| 00 | [overview](./00-overview.md) | 架构级 | ⚡ 当前 |
| 10 | [config-schema](./10-config-schema.md) | 实现级 | ⏳ 待写 |
| 05 | [roles-skills](./05-roles-skills.md) | 中等详细 | ⏳ 待写 |
| 02 | [adapter](./02-adapter.md) | **实现级**（核心） | ⏳ 待写 |
| 01 | [engine](./01-engine.md) | **实现级**（核心） | ⏳ 待写 |
| 07 | [artifacts](./07-artifacts.md) | 中等详细 | ⏳ 待写 |
| 06 | [memory-system](./06-memory-system.md) | 中等详细 | ⏳ 待写 |
| 08 | [cost-control](./08-cost-control.md) | 中等详细 | ⏳ 待写 |
| 11 | [runtime-protocol](./11-runtime-protocol.md) | **实现级**（核心） | ⏳ 待写 |
| 03 | [service-api](./03-service-api.md) | 架构级 | ⏳ 待写 |
| 04 | [web-panel](./04-web-panel.md) | 架构级 | ⏳ 待写 |
| 09 | [hooks-security](./09-hooks-security.md) | 架构级 | ⏳ 待写 |

---

## 2. 整体架构

### 2.1 四层架构

```
┌────────────────────────────────────────────────────────────┐
│                    ai-rd-team                               │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────────────────────────────────────────┐          │
│  │  【表现层】 Presentation                       │          │
│  │  Web 面板 (Flask + Vue3)                      │          │
│  │  【未来】QQ Bot / WeChat Bot                  │          │
│  └───────────────┬──────────────────────────────┘          │
│                  │ HTTP + SSE                              │
│                  ▼                                         │
│  ┌──────────────────────────────────────────────┐          │
│  │  【服务层】 Service API                        │          │
│  │  REST API - 查询状态 / 接收操作 / 配置管理      │          │
│  └───────────────┬──────────────────────────────┘          │
│                  │ 方法调用                                │
│                  ▼                                         │
│  ┌──────────────────────────────────────────────┐          │
│  │  【引擎层】 Engine - 团队环境管理器             │          │
│  │  · 团队创建与成员生命周期                       │          │
│  │  · 角色加载 (Skills/Config/Memory)            │          │
│  │  · 运行时状态协调（文件层）                     │          │
│  │  · 资源限制与成本控制                          │          │
│  │  · Hook 触发                                  │          │
│  └───────────────┬──────────────────────────────┘          │
│                  │ Adapter API                             │
│                  ▼                                         │
│  ┌──────────────────────────────────────────────┐          │
│  │  【适配层】 Adapter                            │          │
│  │  BaseAdapter (abstract)                      │          │
│  │  ├── CodeBuddyAdapter ✅ (第一期)             │          │
│  │  ├── TraeAdapter ⏳ (第二期，降级模式)        │          │
│  │  └── QoderAdapter ⏳ (第二期，单 Agent 模式)  │          │
│  └──────────────────────────────────────────────┘          │
│                                                            │
└────────────────────────────────────────────────────────────┘
         │
         ├──> .ai-rd-team/ (全局配置 + 项目配置)
         └──> .ai-rd-team/runtime/ (运行时状态 + 制品)
```

### 2.2 架构原则

1. **自主驱动，非工作流编排**
   - 成员通过角色+Skills+目标自主决策
   - 引擎只提供"环境"，不"调度"每一步
   - 原型 P1 已验证：main 零干预下成员能自主完成完整任务

2. **文件层作为状态事实源**
   - 团队状态、成员状态、消息记录、制品全部落盘
   - Web 面板监听文件变化获取全局视图
   - 断点续跑依赖文件层

3. **适配层屏蔽平台差异**
   - BaseAdapter 接口平台无关
   - 各平台 Adapter 实现能力查询（capability）+ 能力降级
   - 新增平台不改引擎代码

4. **资源单位统一**
   - 不依赖具体模型价格
   - 以 Resource Points 为核心计量维度
   - 币种/美元估算作为辅助展示

5. **低门槛优先（AI 时代）**
   - 零配置即可用（智能推断 + 默认值）
   - 首次启动对话引导 ≤ 3 问，20 秒完成
   - 配置分层：Basic（~10 字段）是主流，Advanced（400+ 字段）给企业/定制化
   - YAML 不是主要交互界面，Web 面板才是
   - 详见 `10-config-schema.md §0`

---

## 3. 核心数据流

### 3.1 一次完整运行的数据流

```
用户输入需求
    ↓
Web 面板 → Service API → 引擎
    ↓
引擎加载 config.yaml + Skills + Memory
    ↓
引擎根据档位（Lite/Standard/Full）确定成员组成
    ↓
引擎 → BaseAdapter → CodeBuddyAdapter
    ↓
CodeBuddyAdapter.create_team() → team_create(CodeBuddy)
    ↓
CodeBuddyAdapter.spawn_member() × N → task(async) × N
    ↓ ← ← ←
成员独立运行 ──┐
    ├── 自主协作（send_message P2P）
    ├── 产出制品到 .ai-rd-team/runtime/artifacts/
    ├── 写状态到 .ai-rd-team/runtime/state/members/{name}.yaml
    └── 写消息流到 .ai-rd-team/runtime/messages/
    
同时（并行）：
Web 面板 → watchdog 监听 runtime/ → SSE 推送前端
    ↓
用户通过前端查看实时状态、发指令
    ↓
前端 → POST /api/team/xxx → Service API → runtime/commands/
    ↓
成员轮询 commands/ 响应操作
    ↓
任务完成或达到资源上限
    ↓
引擎触发 shutdown 流程 + 生成最终报告
```

### 3.2 运行时目录结构

```
<workspace>/
├── .ai-rd-team/                         # 项目级配置（优先）
│   ├── config.yaml                      # 项目配置
│   ├── skills/                          # 项目自定义 Skills
│   ├── memory/                          # 项目级记忆
│   │   ├── agent.d/                     # 启动加载（简要/高频）
│   │   ├── memory.d/                    # 按需检索（详细/低频）
│   │   └── decisions/                   # ADR 决策追溯
│   └── runtime/                         # ⭐ 运行时（每次清理或归档）
│       ├── state/
│       │   ├── team.yaml                # 团队全局状态（原子写）
│       │   └── members/
│       │       ├── architect.yaml       # 各成员状态
│       │       └── developer.yaml
│       ├── messages/
│       │   └── 20260503-214700-main-architect.json  # 每条消息一文件
│       ├── events.jsonl                 # 全局事件流（fcntl 锁追加）
│       ├── artifacts/                   # 制品产出
│       │   ├── design/                  # 架构师产出
│       │   ├── code/                    # 开发者产出
│       │   ├── test/                    # 测试产出
│       │   └── reports/                 # 工作报告
│       ├── commands/                    # 用户指令队列
│       │   └── pending/
│       ├── cost/
│       │   └── resource-points.yaml     # 实时资源计量
│       └── logs/
│           └── engine.log
│
~/.ai-rd-team/                           # 全局配置（备用）
├── config.yaml                          # 全局默认配置
├── skills/                              # 用户全局 Skills
├── pricing.yaml                         # 模型价格表（可选）
├── quota-history.jsonl                  # 跨项目额度累计
└── presets/                             # 档位预设
    ├── lite.yaml
    ├── standard.yaml
    └── full.yaml
```

---

## 4. 关键设计决策汇总

这些决策来自头脑风暴和原型验证，在各详细设计文档中将被引用：

| # | 决策 | 依据 | 文档 |
|---|-----|------|------|
| D1 | 四层架构 | 头脑风暴 §3 | 本文 §2 |
| D2 | 自主驱动而非工作流 | 头脑风暴 §3 + P1 验证 | 01, 05 |
| D3 | 文件层作为状态源 | P1 + P3 | 01, 04, 07, 11 |
| D4 | 文件监听 + HTTP 回调（Web） | P3 | 03, 04, 11 |
| D5 | 三种并发写策略分工 | P4 | 07 |
| D6 | Resource Points v1 权重 | P5 | 08 |
| D7 | 三档运行模式 | 头脑风暴 §21 | 05, 08 |
| D8 | 首次启动问计费模式 | 头脑风暴 §21.5 | 08 |
| D9 | 7 固定角色 + 可伸缩 | 头脑风暴 §5 | 05 |
| D10 | 三层记忆（agent.d + memory.d + decisions） | 头脑风暴 §19 | 06 |
| D11 | 三层 Skills（内置 + 全局 + 项目） | 头脑风暴 §6 | 05 |
| D12 | BaseAdapter 抽象接口 | 头脑风暴 §21 + P1 | 02 |
| D13 | 半自动降级（第一期） | 头脑风暴 §21.6 + CodeBuddy 限制 | 08 |
| D14 | Prompt 模板化 | P1 验证的有效格式 | 05 |
| D15 | **低门槛优先 / 零配置即可用** | AI 时代用户不该面对 400+ 配置项；首次引导 ≤3 问，之后零打扰 | 10 (§0) |
| D16 | **配置分层**（Basic / Advanced / Defaults / Inferred） | Basic 层 ≤10 字段满足 99% 用户；Advanced 层给企业/定制化 | 10 (§0.1, §2, §3A) |
| D17 | **智能推断**（Convention over Configuration） | 项目名/技术栈/locale/OS 等从环境推断，不让用户填 | 10 (§0.5, §2B) |

---

## 5. 模块依赖关系

```
┌─────────────────────────────────────────────┐
│              Web 前端（Vue3 CDN）             │
└────────┬────────────────────────────────────┘
         │ HTTP + SSE
         ▼
┌─────────────────────────────────────────────┐
│    Service API (Flask)                       │
│    · /api/team/* : 团队操作                    │
│    · /api/config/* : 配置管理                 │
│    · /api/cost/* : 成本查询                   │
│    · /api/stream : SSE 实时推送               │
└────────┬────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│    Engine (Python)                           │
│    · TeamManager                             │
│    · MemberManager                           │
│    · ConfigLoader                            │
│    · SkillsLoader                            │
│    · MemoryManager                           │
│    · CostTracker                             │
│    · HookRunner                              │
│    · FileWatcher (runtime/)                  │
└────────┬────────────────────────────────────┘
         │ BaseAdapter ABC
         ▼
┌─────────────────────────────────────────────┐
│    Adapter (CodeBuddyAdapter)                │
│    · create_team / delete_team               │
│    · spawn_member / shutdown_member          │
│    · send_message (P2P / broadcast)          │
│    · query_capabilities                      │
└────────┬────────────────────────────────────┘
         │ CodeBuddy 工具调用
         ▼
    [CodeBuddy Team]
```

**依赖方向**：表现层 → 服务层 → 引擎层 → 适配层 → 平台。严禁反向依赖。

---

## 6. 技术栈

| 组件 | 选型 | 版本 |
|------|------|------|
| 语言 | Python | 3.11+ |
| 配置格式 | YAML | PyYAML 6.x |
| Web 后端 | Flask | 3.x |
| Web 前端 | Vue 3 + TailwindCSS + Chart.js + Mermaid.js | CDN 引入 |
| 文件监听 | watchdog | 4.x |
| 文件锁 | fcntl（Linux/Mac）+ portalocker（Windows 降级） | - |
| 图表 | Mermaid | CDN |
| 日志 | Python logging + structlog | - |
| 测试 | pytest | 8.x+ |
| 文档 | Markdown + openspec | - |

---

## 7. 非目标（第一期不做）

明确声明**第一期不做**的项目，避免 scope creep：

- ❌ QQ/微信 Bot 远程控制
- ❌ Trae/Qoder Adapter（BaseAdapter 接口预留）
- ❌ UI/UX 设计师角色
- ❌ 国际化多语言包（第一期仅中文）
- ❌ 模型全自动降级（CodeBuddy 限制，第二期）
- ❌ 精确 token 计费（无 API，用估算）
- ❌ 角色×模型运行时切换（第二期）
- ❌ 企业集中额度服务（第二期）
- ❌ 分布式部署
- ❌ 需求变更中的运行时重启

---

## 8. 质量目标

### 8.1 功能性目标

1. **能跑通完整研发流程**：从需求输入 → 需求分析 → 设计 → 开发 → 评审 → 测试 → 部署
2. **至少支持 3 档运行模式**：Lite（1-2 人）/Standard（3-5 人）/Full（7-15 人）
3. **成本可控**：Standard 档跑一个中等需求 < 400 Resource Points

### 8.2 非功能目标

| 项 | 目标 |
|----|-----|
| 启动时间 | < 10 秒（加载配置 + Skills） |
| Team 创建时间 | < 30 秒（派发所有成员） |
| Web 面板首次加载 | < 2 秒 |
| 文件监听延迟 | < 500ms |
| 断点续跑能力 | ✅ 支持 |
| 跨平台 | Linux/Mac 一等公民，Windows 降级兼容 |

### 8.3 可维护性目标

- 核心模块单元测试覆盖率 ≥ 80%
- 所有公开 API 有类型注解和 docstring
- 配置文件有 JSON Schema 校验
- 错误信息可追溯（日志包含 team_id + member_name + phase）

---

## 9. 安全与合规

详见 `09-hooks-security.md`。关键要点：

- 命令白/黑名单
- 文件可写范围限制
- API Key 不泄露（第一期无 API Key，但 Adapter 未来可能引入）
- 敏感数据脱敏（日志不记录 prompt 全文，可选配置）
- 用户操作审计

---

## 10. 演进路径

### 第一期（当前）
- 完整实现 CodeBuddyAdapter
- 基础 Web 面板
- 三档模式 + 资源限制

### 第二期
- 模型全自动降级（需 CodeBuddy 或其他 Adapter 支持）
- Trae/Qoder Adapter
- 企业集中额度服务
- QQ/微信 Bot

### 第三期
- 精确计费（如 CodeBuddy 开放 token API）
- 分布式部署
- 跨项目知识库联邦

---

## 11. 验证策略

每个详细设计文档完成后，采用三级验证：

1. **自审**：作者按 openspec `proposal` 规则检查（非目标章节、验收标准等）
2. **用户审**：用户 review 是否符合预期
3. **实现前验证**：详细设计完成后整体评审一次，确认一致性

进入实现前，必须通过上述三级验证。

---

## 12. 附录

- 原型验证报告：`prototype/REPORT.md`
- 头脑风暴记录：`openspec/specs/2026-04-14-ai-rd-team-brainstorming.md`
- 开源地址：`https://github.com/eyjian/ai-rd-team`
