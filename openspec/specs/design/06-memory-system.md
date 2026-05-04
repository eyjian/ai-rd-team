# ai-rd-team 详细设计 - 06 记忆系统

> 文档版本：v1.0
> 日期：2026-05-04
> 颗粒度：中等详细
> 依赖：`00-overview.md`、`01-engine.md`、`05-roles-skills.md`、`07-artifacts.md`
> 头脑风暴相关：§19 三层记忆体系（agent.d + memory.d + decisions）

---

## 1. 目的与范围

### 1.1 目的
定义 ai-rd-team 的**长期记忆体系**。与 Skills（静态技能）不同，Memory 是**项目积累的知识**——从过往决策、历史需求、踩坑经验中形成的经验库。

### 1.2 解决的问题
- 上下文窗口有限，不能每个成员都塞一大堆背景
- 项目迭代时应该"记住"上一版的决策，而不是从零开始
- 团队间应能共享"踩过的坑"和"关键决策"

### 1.3 范围
- 三层记忆结构（agent.d / memory.d / decisions）
- ADR（架构决策记录）格式
- MemoryManager 接口
- 记忆写入与读取时机
- 跨项目记忆共享（全局 memory）

### 1.4 非目标
- ❌ 向量检索（第一期不做 RAG，后续可能引入）
- ❌ 自动摘要压缩（第一期纯 Markdown 静态文件）
- ❌ 记忆版本管理（靠 git 而非系统本身）

---

## 2. 核心原则

### 2.1 分层加载，按需引用

| 层 | 加载时机 | 大小预算 | 用途 |
|----|--------|---------|------|
| **agent.d/** | 成员 spawn 时**强制加载进 prompt** | 每角色 ≤ 2K tokens | 核心身份背景、团队共识 |
| **memory.d/** | 成员运行时**按需 Read 工具读取** | 单文件 ≤ 5K tokens | 详细历史、案例库 |
| **decisions/** | 成员运行时**按需 Read** | 单 ADR ≤ 1K tokens | 架构决策可追溯 |

### 2.2 写入即追溯

所有记忆都有元数据头：**作者 / 日期 / 触发事件 / 关联制品**。方便未来回顾"为什么当时这么记"。

### 2.3 项目级为主，全局级为辅

- **项目级记忆**（`<workspace>/.ai-rd-team/memory/`）：项目独有，与代码一起 git 管理
- **全局级记忆**（`~/.ai-rd-team/memory/`）：跨项目通用经验（如用户的个人工程风格）

项目级优先，同名覆盖全局级。

### 2.4 只记值得记的

避免记忆无用膨胀：
- ✅ 关键决策（ADR）
- ✅ 踩坑经验 / anti-pattern
- ✅ 业务术语表 / 领域知识
- ❌ 日常消息（那是 `events.jsonl` 的事）
- ❌ 代码内容（代码本身就是记忆）

---

## 3. 目录结构

### 3.1 项目级 memory 目录

```
<workspace>/.ai-rd-team/memory/
├── agent.d/                          # 启动加载（简要/高频）
│   ├── team-roster.md                # 团队成员清单
│   ├── current-phase.md              # 当前阶段
│   ├── key-decisions.md              # 关键决策摘要（引用 decisions/）
│   ├── domain-terms.md               # 业务术语表
│   ├── tech-stack-selected.md        # 本项目技术栈（architect 写）
│   └── interface-contracts.md        # 接口契约摘要
│
├── memory.d/                         # 按需检索（详细/低频）
│   ├── domain/
│   │   ├── business-rules.md         # 业务规则详解
│   │   └── user-personas.md          # 用户画像
│   ├── past-cases/
│   │   ├── 2025-12-feature-auth.md   # 历史需求 / 历史实现
│   │   └── 2026-01-refactor-db.md
│   ├── bug-patterns/                 # 已知 Bug 模式
│   │   └── race-condition-cases.md
│   ├── anti-patterns/
│   │   └── over-engineering.md
│   └── benchmarks/
│       └── performance-baselines.md  # 性能基线
│
└── decisions/                        # ADR 决策追溯
    ├── 0001-use-go-kratos-backend.md
    ├── 0002-wechat-miniprogram-frontend.md
    ├── 0003-redis-cache-strategy.md
    └── ...
```

### 3.2 全局级 memory 目录

```
~/.ai-rd-team/memory/
├── agent.d/
│   ├── my-coding-style.md            # 用户个人偏好
│   ├── my-team-culture.md
│   └── my-tech-preferences.md
├── memory.d/
│   └── ...
└── decisions/                        # 跨项目的通用决策（少用）
```

### 3.3 与 Skills 的关系

| 维度 | Skills | Memory |
|------|--------|--------|
| 性质 | 静态技能（知识库） | 项目积累（经验） |
| 是否随项目变 | 不变 | 变 |
| 管理方式 | 代码分发 / 手动编辑 | 自动积累 + 手动整理 |
| 典型内容 | `pytest-guide.md` | `domain-terms.md` |

**边界有重叠时的分类原则**：
- "通用做法" → Skills（如"pytest 怎么写"）
- "本项目的特殊做法" → Memory（如"本项目用 pytest-asyncio 做异步测试"）

---

## 4. 文件格式

### 4.1 通用 Markdown 头

所有 memory 文件都有统一头信息：

```markdown
---
type: memory                            # memory / adr
layer: agent.d                          # agent.d / memory.d / decisions
author: architect                       # 写入者（或 "manual" / "auto"）
created: 2026-05-04T10:00:00Z
updated: 2026-05-04T10:30:00Z
related:
  - artifacts/design/spec-architecture.md
  - decisions/0001-use-go-kratos-backend.md
tags: [backend, architecture]
estimated_tokens: 320                   # 用于控制加载预算
---

# 文件主标题

## 正文章节...
```

Frontmatter 用 YAML 便于程序解析。`estimated_tokens` 在写入时由 `MemoryManager` 计算。

### 4.2 agent.d 文件规范

**严格**要求：
- 每个文件**不超过 2K tokens**（~800 中文字）
- 每个角色引用的 agent.d 文件**总和不超过 8K tokens**
- 使用简洁的**要点格式**，避免冗长段落

**示例**：`agent.d/team-roster.md`

```markdown
---
type: memory
layer: agent.d
author: auto
created: 2026-05-04
updated: 2026-05-04T10:00:00Z
tags: [team]
estimated_tokens: 150
---

# 团队成员清单

- **周立项**（pm）：项目经理，协调全局
- **陈架构**（architect）：架构师，负责技术方案
- **林1号**（developer_1）：后端开发
- **林2号**（developer_2）：前端开发
- **王1号**（reviewer_1）：代码评审
- **赵1号**（tester_1）：测试

**联系方式**：通过 `send_message(recipient="{name}")` 直接对话。
```

**示例**：`agent.d/key-decisions.md`

```markdown
---
type: memory
layer: agent.d
author: architect
updated: 2026-05-04T10:30:00Z
related: [decisions/0001-use-go-kratos-backend.md]
tags: [decisions]
estimated_tokens: 280
---

# 关键决策摘要

以下是本项目的关键决策（简要版），详细背景见 `memory/decisions/`。

| ID | 决策 | 理由 | 详见 |
|----|------|------|------|
| 0001 | 后端用 Go + Kratos | 团队熟悉 + 性能够 | [0001](../decisions/0001-use-go-kratos-backend.md) |
| 0002 | 移动端用微信小程序 | 用户主要在微信生态 | [0002](../decisions/0002-wechat-miniprogram-frontend.md) |
| 0003 | Redis key 前缀统一 `app:` | 多项目共享 Redis | [0003](../decisions/0003-redis-cache-strategy.md) |
```

### 4.3 memory.d 文件规范

更宽松：
- 每个文件 ≤ 5K tokens（~2000 中文字）
- 允许详细展开（但要有清晰目录）
- 必须有"何时应用/不应用"章节

**示例**：`memory.d/bug-patterns/race-condition-cases.md`

```markdown
---
type: memory
layer: memory.d
author: reviewer
updated: 2026-04-10
tags: [bug, concurrency, backend]
estimated_tokens: 850
---

# 本项目并发 Bug 模式库

## 何时应用
- 评审涉及 goroutine / channel / sync 的代码
- 评审 Redis 事务相关代码
- 评审并发数据库写入代码

## 何时不应用
- 前端代码（除非涉及 WebSocket）
- 纯 CRUD 单例代码

## 案例 1：goroutine 泄漏

### 现象
...

### 根因
...

### 正确做法
```go
ctx, cancel := context.WithCancel(ctx)
defer cancel()
go func() {
    select {
    case <-ctx.Done():
        return
    case data := <-ch:
        ...
    }
}()
```

## 案例 2：...
```

### 4.4 decisions (ADR) 文件规范

**ADR**（Architecture Decision Record）采用社区标准 [MADR](https://adr.github.io/madr/) 风格：

```markdown
---
type: adr
layer: decisions
adr_id: "0001"
author: architect
status: accepted              # proposed / accepted / deprecated / superseded
created: 2026-05-04
updated: 2026-05-04
supersedes: null              # 若取代旧 ADR，填 adr_id
superseded_by: null           # 若被新 ADR 取代，填 adr_id
related:
  - artifacts/design/spec-architecture.md
tags: [backend, tech-stack]
estimated_tokens: 450
---

# ADR-0001：后端技术栈选择 Go + Kratos

## 状态
Accepted（2026-05-04）

## 上下文（Why 需要这个决策）
项目是一个高并发的日报系统，预计 DAU 10万+，要求响应时间 < 200ms。
团队成员熟练技术栈：
- Go：expert
- Python：proficient
- Node.js：beginner

## 选项考察

### 选项 A：Go + Kratos
- ✅ 性能好
- ✅ 团队熟练
- ✅ Kratos 内置微服务能力
- ⚠️ 生态不如 Java / Node

### 选项 B：Python + FastAPI
- ✅ 开发快
- ⚠️ 性能稍差（但 FastAPI 够用）
- ✅ 团队 proficient

### 选项 C：Node.js + NestJS
- ✅ 生态好
- ❌ 团队 beginner
- ❌ 学习成本

## 决策
**选择 A：Go + Kratos**。

## 理由
1. 性能要求高，Go 天然合适
2. 团队 expert，无学习成本
3. Kratos 内置的 DI / middleware / 错误码体系成熟

## 后果
**正面**：
- 响应时间预期能达标
- 项目启动快

**负面**：
- Python / TypeScript 背景的新人上手慢
- 需提前准备一份 Kratos 入门 Skill

## 相关
- [spec-architecture.md](../../artifacts/design/spec-architecture.md)
- [tech-stack-selected.md](../agent.d/tech-stack-selected.md)
```

---

## 5. MemoryManager 接口

### 5.1 类结构

```python
# ai_rd_team/memory/manager.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class MemoryLayer(str, Enum):
    AGENT_D = "agent.d"
    MEMORY_D = "memory.d"
    DECISIONS = "decisions"


@dataclass(frozen=True)
class MemoryItem:
    layer: MemoryLayer
    path: Path                  # 绝对路径
    title: str                  # 从 Markdown 第一个 `#` 标题提取
    frontmatter: dict           # 解析后的 YAML 头
    content_body: str           # 去掉 frontmatter 的正文
    estimated_tokens: int
    scope: str                  # "project" or "global"


class MemoryManager:
    """三层记忆管理器。"""
    
    def __init__(
        self,
        workspace_memory_dir: Path,
        global_memory_dir: Path | None = None,
    ):
        self.workspace_dir = workspace_memory_dir
        self.global_dir = global_memory_dir or (Path.home() / ".ai-rd-team" / "memory")
        self._cache: dict[tuple[str, str], MemoryItem] = {}
    
    # ===== 加载（只读） =====
    
    def load_agent_d(
        self,
        role: "Role",
        scope_filter: list[str] | None = None,
    ) -> list[MemoryItem]:
        """加载某角色启动时需要的 agent.d 内容。
        
        返回的内容会被拼入成员 prompt（见 05-roles-skills §6.5）。
        
        Args:
            role: 角色对象，其 memory_scope.agent_d 指明要加载哪些文件
            scope_filter: 可额外过滤（如只加载某些 tag）
        
        Token 预算：
            本方法会确保返回的 item 总 estimated_tokens ≤ 8K
            若超限，按 role.memory_scope.agent_d 列表顺序截断
        """
        files = role.memory_scope.get("agent_d", [])
        items = []
        total = 0
        for name in files:
            item = self._load_file(layer=MemoryLayer.AGENT_D, name=name)
            if item is None:
                continue
            if total + item.estimated_tokens > 8000:
                # 软限：警告但不硬断
                break
            items.append(item)
            total += item.estimated_tokens
        return items
    
    def load_memory_d(
        self,
        topic: str,
        tag_filter: list[str] | None = None,
    ) -> list[MemoryItem]:
        """按主题加载 memory.d 内容（供成员按需检索，不自动注入 prompt）。"""
    
    def load_decision(self, adr_id: str) -> MemoryItem | None:
        """加载某 ADR。"""
    
    def list_decisions(self, status_filter: str | None = None) -> list[MemoryItem]:
        """列出所有 ADR。"""
    
    # ===== 写入 =====
    
    def write_agent_d(
        self,
        name: str,                # 如 "key-decisions"
        content: str,             # 正文（不含 frontmatter）
        author: str,
        tags: list[str] | None = None,
        related: list[str] | None = None,
    ) -> MemoryItem:
        """写/更新 agent.d 文件。
        
        自动处理：
        - frontmatter 生成（author / created / updated / estimated_tokens）
        - 创建时间保留（若文件已存在）
        - 用 atomic_write 写入（状态类文件）
        """
    
    def write_memory_d(
        self,
        relative_path: str,       # 如 "domain/business-rules"
        content: str,
        author: str,
        tags: list[str] | None = None,
        related: list[str] | None = None,
    ) -> MemoryItem:
        """写/更新 memory.d 文件。"""
    
    def write_decision(
        self,
        adr_id: str,              # "0001"
        title: str,
        content: str,             # MADR 正文
        author: str,
        status: str = "proposed",
        supersedes: str | None = None,
        tags: list[str] | None = None,
    ) -> MemoryItem:
        """写一个新 ADR。"""
    
    def next_adr_id(self) -> str:
        """分配下一个 ADR ID（自动递增）。"""
    
    # ===== 辅助 =====
    
    def _load_file(self, layer: MemoryLayer, name: str) -> MemoryItem | None:
        """按层 + 名查找。项目级优先于全局级。"""
        # 先找项目级
        project_path = self.workspace_dir / layer.value / f"{name}.md"
        if project_path.exists():
            return self._parse(project_path, scope="project")
        # 再找全局级
        global_path = self.global_dir / layer.value / f"{name}.md"
        if global_path.exists():
            return self._parse(global_path, scope="global")
        return None
    
    def _parse(self, path: Path, scope: str) -> MemoryItem:
        """解析 Markdown 文件 → MemoryItem。"""
        text = path.read_text(encoding="utf-8")
        # 分离 frontmatter 和 body
        frontmatter, body = self._split_frontmatter(text)
        title = self._extract_title(body)
        
        from ai_rd_team.shared.token_counter import estimate_tokens
        tokens = frontmatter.get("estimated_tokens") or estimate_tokens(body)
        
        return MemoryItem(
            layer=MemoryLayer(frontmatter.get("layer", path.parent.name)),
            path=path,
            title=title,
            frontmatter=frontmatter,
            content_body=body,
            estimated_tokens=tokens,
            scope=scope,
        )
```

### 5.2 PromptRenderer 集成

`05-roles-skills.md §7.4` 的 PromptRenderer 调用 `MemoryManager.load_agent_d(role)` 并将结果注入 `{agent_d_memory_injected}` 变量。

```python
# PromptRenderer.render 内部
agent_d_items = memory_manager.load_agent_d(role)
agent_d_section = "\n\n".join(
    f"## {item.title}\n\n{item.content_body}"
    for item in agent_d_items
)
```

---

## 6. 记忆的写入时机

### 6.1 三种写入方式

**方式 A：成员主动写（推荐）**  
成员在工作过程中判断"这个值得记"，直接写 Markdown 到 `memory/` 目录。

例：
- architect 做完重要决策 → 写一个 ADR
- reviewer 发现某类 Bug 多次出现 → 更新 `bug-patterns/`
- analyst 识别到新术语 → 更新 `agent.d/domain-terms.md`

**方式 B：引擎在关键节点自动写**  
- `run_started` hook → 引擎初始化 `agent.d/team-roster.md`（写入当前团队名单）
- `run_stopped` hook → 引擎更新 `agent.d/key-decisions.md`（汇总本次新增 ADR）
- `phase_complete` hook → PM 产出的 `report-phase-*.md` 自动提炼要点到 `memory.d/past-cases/`

**方式 C：用户手工整理**  
用户通过 Web 面板或直接编辑 Markdown 文件补充/纠正记忆。

### 6.2 ADR 触发时机

architect（或其他核心角色）**必须**在以下场景产出 ADR：

| 场景 | 是否必须 |
|------|--------|
| 技术栈选择（语言/框架） | ✅ 必须 |
| 数据库选型 / 缓存策略 | ✅ 必须 |
| 核心算法选择（差异大） | ✅ 必须 |
| API 规范（REST vs GraphQL） | ✅ 必须 |
| 部署拓扑（单体 vs 微服务） | ✅ 必须 |
| 库版本选择 | ⚠️ 重大版本才写 |
| 命名约定 | ❌ 写到 Skills 即可 |

### 6.3 记忆污染防护

避免成员错误地往 memory 里塞日常消息。约定：

| 内容 | 位置 |
|------|------|
| 本次运行的消息流 | `runtime/messages/` |
| 本次运行的进度 | `runtime/state/` |
| 本次运行的制品 | `runtime/artifacts/` |
| 关键决策（跨次运行有价值） | `memory/decisions/` |
| 经验沉淀（跨次运行有价值） | `memory/memory.d/` |
| 团队常识（每次必读） | `memory/agent.d/` |

**写入前强制校验**：`MemoryManager.write_*` 检查内容是否包含 timestamp / run_id 等"临时性"标记，若是则警告"这可能属于 runtime 而非 memory"。

---

## 7. 记忆读取时机

### 7.1 agent.d：启动即加载

- 成员 spawn 时，由 PromptRenderer 通过 MemoryManager 加载并注入 prompt
- 每个角色在 config 中声明需要哪些 agent.d 文件（`role.memory_scope.agent_d`）
- 总预算 8K tokens（硬限）

### 7.2 memory.d：按需检索

成员运行中判断需要某类信息时：

1. 通过 Read 工具读取具体文件（如 `memory.d/bug-patterns/race-condition-cases.md`）
2. 或通过 grep / 全文检索（第一期无 RAG，用简单 grep）

**Prompt 引导**：成员 prompt 中告知 memory.d/ 路径 + 简要目录，不注入全文。

```
# 成员 prompt 模板片段
## 需要时可查阅的详细资料：
- `memory/memory.d/domain/`：业务规则
- `memory/memory.d/past-cases/`：历史实现参考
- `memory/memory.d/bug-patterns/`：Bug 模式库
- `memory/decisions/`：架构决策追溯
```

### 7.3 decisions：按需引用

同 memory.d，成员在需要"为什么这么选"时读取 ADR。

agent.d/key-decisions.md 只放**摘要 + 链接**，完整 ADR 在 decisions/。

---

## 8. 跨项目记忆（全局层）

### 8.1 适用场景
- 个人工程风格（"我命名偏好驼峰还是下划线"）
- 常用技术栈偏好
- 通用 anti-patterns 经验

### 8.2 加载规则
- 同名文件：项目级覆盖全局级
- 项目级不存在的文件：全局级兜底
- 全局级变化不触发项目级更新（隔离）

### 8.3 隐私约束

全局记忆**不能**包含：
- 公司内部敏感信息
- 项目代码 / API key
- 客户数据

**实现层**：MemoryManager.write_* 若 scope=global，检查内容是否含 security.sensitive_data.patterns（见 `10-config-schema §3.5`），命中则拒绝写入。

---

## 9. 记忆与 Git

### 9.1 推荐 .gitignore

```gitignore
# 项目级 memory 应跟 git 管理（团队共享记忆）
# 但 agent.d/team-roster.md 每次运行会被引擎覆写，可选忽略
# <workspace>/.ai-rd-team/memory/agent.d/team-roster.md

# runtime 不提交（见 07-artifacts）
<workspace>/.ai-rd-team/runtime/

# 全局 memory 不属于项目（在用户家目录）
```

### 9.2 提交节奏
- 每次 ADR 产出 → 单独提交（便于追溯）
- memory.d 新增 / 大改 → 单独提交
- agent.d/key-decisions.md 自动更新 → 跟 ADR 一起提交

### 9.3 合并冲突
- ADR 基本不会冲突（ID 递增）
- agent.d 可能有并发更新冲突，优先手工合并
- memory.d 按话题分文件，冲突概率低

---

## 10. Web 面板展示

Web 面板的"项目记忆"Tab 展示：

1. **ADR 列表**（按时间/状态排序）
2. **agent.d 文件预览**（每个文件显示 token 预算）
3. **memory.d 树形浏览**
4. **搜索框**（支持 tag / 全文 / author）
5. **编辑按钮**（富文本编辑，保存即 atomic_write）

详见 `04-web-panel.md`。

---

## 11. 验收标准

- ✅ 三层目录结构按 §3.1 自动创建
- ✅ 所有 memory 文件符合 §4.1 的 frontmatter 格式
- ✅ agent.d 加载总 token ≤ 8K（有硬限制）
- ✅ MemoryManager 的 load_agent_d / load_memory_d / load_decision / write_* 方法可用
- ✅ next_adr_id 自动递增且无冲突
- ✅ 项目级记忆覆盖全局级（同名时）
- ✅ 全局记忆写入时做敏感信息校验
- ✅ ADR 状态流转（proposed → accepted → deprecated / superseded）可用
- ✅ PromptRenderer 正确注入 agent.d 到成员 prompt
- ✅ Web 面板可编辑 memory 文件
- ✅ 单元测试覆盖 ≥ 80%（解析 frontmatter / token 预算 / 优先级 / 自动 ID）

---

## 12. 对其他文档的接口

| 使用方 | 接口 |
|-------|-----|
| `01-engine.md` | MemoryManager 作为子管理器 |
| `05-roles-skills.md` | 成员 prompt 的 `{agent_d_memory_injected}` 变量；成员 Persona 引用 memory_scope |
| `07-artifacts.md` | `artifacts/design/adr/README.md` 指向 `memory/decisions/` |
| `04-web-panel.md` | Web 面板读写 memory/ |
| `09-hooks-security.md` | global 写入的敏感信息校验；`adr_written` Hook |
| `10-config-schema.md` | `roles.{role}.memory_scope` 定义加载哪些 agent.d |

---

## 13. 附录：最简记忆示例（新项目启动）

新项目启动时，以下是引擎自动产生的最小 memory 集合：

```
.ai-rd-team/memory/
├── agent.d/
│   ├── team-roster.md              # 引擎 auto 写入
│   ├── current-phase.md            # pm 写入（或引擎初始化为 "requirements"）
│   ├── tech-stack-selected.md      # 首次启动时 auto 从 config.yaml 写入
│   └── key-decisions.md            # 空文件，首个 ADR 后填充
├── memory.d/
│   └── README.md                   # 占位：说明目录用途
└── decisions/
    └── README.md                   # 占位：说明 ADR 命名规则
```

随着项目推进，agent.d 和 decisions 逐渐丰富。第二次运行相同项目时，记忆就开始发挥作用。
