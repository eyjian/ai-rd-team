## Why

当前 `agent.d/` 的设计意图是"项目级共享背景知识，启动时按角色加载到 prompt 里"，但实际实现存在三个语义裂缝，已在某下游项目的真实启动场景中暴露：

- **白名单即准入名单**：`memory/manager.py:200 load_agent_d()` 严格按 `role.memory_scope["agent_d"]` 列表去匹配文件名，目录里其它 `*.md` 不会被加载。这违反"agent.d 是项目共享背景知识"的语义——既然命名叫 agent.d，目录里的文件就该默认全员可见，白名单只该用来**排序/优先级控制**，而不是"准入名单"
- **launcher Skill 与框架的契约真空**：launcher Skill 自我宣称"任何角色入项的第一份强制材料叫 `onboarding-entrypoint.md`"，但 `roles/prompt.py:_DEFAULT_ROLE_MEMORY_SCOPE` 7 个角色没一个包含此条目；用户在 `agent.d/` 下规规矩矩放了 `onboarding-entrypoint.md`，框架完全感知不到，导致 architect 拿到的 prompt 里带着"旧 tech-stack-selected"，看不到 onboarding 中的关键约束
- **静默失败**：当 `memory_scope` 列出的文件在磁盘上不存在时，仅 `logger.debug("agent.d not found: %s", name)`——默认日志级别下完全沉默；用户从 `runtime/logs/run.stdout.log` 看不到"我以为会注入的文件，到底注没注入"

三个问题叠加的现象是：**用户认真按目录语义放了一堆 .md，框架默不作声地丢掉一大半**。这违反"agent.d 即项目共享背景"的最小预期，且这种沉默是反 PoLA（Principle of Least Astonishment）的——比报错还难发现。

第一期处于 `0.2.0aN` alpha 期，是修正 agent.d 加载语义最低成本的窗口。再晚改，已有项目（包括内置 launcher Skill 的文档）会与"白名单即准入"的旧行为耦合更深。

## What Changes

- **agent.d 默认全员注入**（核心）：
  - `memory/manager.py::MemoryManager.load_agent_d()` 改为：扫描 `agent.d/*.md` 目录下所有文件，**默认全部加载**
  - `role.memory_scope["agent_d"]` 列表语义从"准入白名单"降级为"优先级置顶 hint"——列在白名单里的文件按白名单顺序在前；未列出的按文件名升序追加
  - Token 预算（`AGENT_D_TOTAL_TOKEN_LIMIT = 8000`）控制不变，但触发顺序从"白名单顺序"改为"白名单内→白名单外"两阶段
- **支持 frontmatter `priority` 字段**（精细化控制）：
  - 文件可在 frontmatter 声明 `priority: <integer>`（默认 `100`，越小越靠前）
  - 同优先级时按"是否在白名单"和"文件名字典序"次级排序
  - 让用户可在不改 Python 代码的前提下调整某份 .md 的相对位置（典型场景：onboarding-entrypoint 设 `priority: 1` 就能强制置顶）
- **保留白名单作为"建议次序"**：白名单未被废弃，仅语义降级。这给老用户最小破坏：他们 config 里的 `memory_scope.agent_d` 还能用，只是不再阻止其它文件注入
- **日志可见性提升**：
  - `agent.d not found` 从 `logger.debug` 改为 `logger.info`（白名单 pinned 但磁盘不存在的文件，默认日志级别可见）
  - 在 `load_agent_d()` 返回前增加一条汇总 INFO：`agent.d injected for role=<name>: [list of names]`，让用户从默认日志一眼确认"我以为会注入的文件，到底注没注入"
- **明确不做 framework-level 硬注入**：不在框架代码里硬编码 `onboarding-entrypoint` 等具体文件名（它属于 launcher Skill 的约定，不属于框架核心；通过 priority 机制让 Skill 自己声明置顶即可）

## Capabilities

### New Capabilities

- `agent-d-auto-loading`：明确 ai-rd-team 框架对 `agent.d/` 目录的加载契约：默认全员注入、white-list 仅控顺序、frontmatter `priority` 字段精细化排序、token 预算溢出截断顺序、加载日志可见性。

### Modified Capabilities

- `openspec/specs/design/06-memory-system.md`：§4.2 章节描述需更新——从"白名单决定加载范围"改为"agent.d 目录下所有 .md 默认加载，白名单仅控置顶顺序"；新增 frontmatter `priority` 字段说明。属于设计文档演进，不引入新 spec delta（新 spec delta 在 `specs/agent-d-auto-loading/spec.md`）。

## 非目标

- ❌ **不在框架代码里硬编码任何具体文件名**（包括 `onboarding-entrypoint`）——它是 launcher Skill 的约定，不是框架内核约束；通过 priority 字段表达即可
- ❌ **不改 memory.d / decisions 的加载语义**——它们一个是按需检索、一个是 ADR 列表，与 agent.d 的"启动加载"语义不同，不在本议题范围
- ❌ **不引入"按 role 维度的额外过滤"**（如 `visible_to: [architect, developer]` frontmatter 字段）——若未来真有强需求，再立 follow-up change；本议题的"全员注入"假设和 agent.d 共享背景的语义一致
- ❌ **不动 `_DEFAULT_ROLE_MEMORY_SCOPE` 的 7 个角色默认值**——它们仍作为"建议置顶"列表；不在本议题清空或重写
- ❌ **不动 `AGENT_D_TOTAL_TOKEN_LIMIT` / `AGENT_D_PER_FILE_TOKEN_LIMIT` 常量值**——8000/2000 的预算策略本身没问题，本议题只改"按什么顺序消费预算"
- ❌ **不在本议题里对接活跃 OpenSpec 议题（议题入口自动注入）**——这是上层另一个独立增强（"engine 自动检测活跃 change 并注入议题摘要到 prompt"），与 agent.d 的目录加载语义解耦，留作 follow-up
- ❌ **不在本议题里给 architect persona 加"冲突仲裁规则"**——它是 Skill / Role 文本层面的工程化建议，与本议题的代码改动解耦
- ❌ **不提供迁移工具**——白名单语义降级是**向后兼容**的扩展（旧白名单仍按顺序生效），不需要迁移

## Impact

### 代码

- `src/ai_rd_team/memory/manager.py`：
  - `load_agent_d()` 重写：从"按白名单查找"改为"扫描目录 + 排序 + 预算截断"
  - 新增 `_load_priority(meta: dict) -> int` 内部辅助：解析 frontmatter `priority`，无声明返回 `100`
  - 新增 `find_agent_d(name: str) -> MemoryItem | None` 公开方法：按 stem 名查找单个 agent.d 条目（供未来 Skills/工具调用，本议题暂不强依赖）
  - `agent.d not found` 日志级别从 debug → info；新增 "agent.d injected for role=X: [...]" 汇总 INFO 日志
- `src/ai_rd_team/roles/prompt.py`：**无代码改动**——`load_agent_d()` 返回的 `MemoryItem` 列表语义不变（仍是按顺序），prompt 渲染流程透明地受益
- `src/ai_rd_team/config/models.py`：**无字段变化**——`memory_scope.agent_d` 仍是 `list[str]`，仅文档说明变化（"准入白名单" → "建议置顶顺序"）

### 文档

- `openspec/specs/design/06-memory-system.md`：§4.2 重写"加载策略"段，反映新语义；§3.2 frontmatter schema 表格新增 `priority` 字段行
- `openspec/changes/agent-d-auto-discovery/specs/agent-d-auto-loading/spec.md`：implement 阶段产出（决策 4 = C，proposal 阶段不写 specs delta）
- `CHANGELOG.md`：在 `[Unreleased]` 节追加：
  - **Changed**：`agent.d` 加载策略——白名单语义从"准入"降级为"置顶 hint"；目录下所有 `.md` 默认注入
  - **Added**：frontmatter `priority` 字段；`MemoryManager.find_agent_d()` 公开方法
  - **Changed**：`agent.d not found` 日志级别提升到 INFO；新增加载汇总日志
- 不更新 `docs/02-configuration.md`，因为 `memory_scope.agent_d` 配置字段语义对用户的"如何写"没变（多写少写都行，只是"少写"现在不再阻止其它文件加载）

### 测试

- `tests/unit/test_memory_manager.py`（更新）：
  - 既有断言"白名单外文件不被加载" → 改为"白名单外文件按文件名追加加载"
  - 既有断言"白名单顺序保持" → 保留并强化（新增"白名单 + 白名单外混合排序"用例）
  - 新增 ≥ 4 个用例：
    - `test_load_agent_d_includes_unpinned_files`：目录下放 3 份 .md，白名单只列 1 份，期望 3 份都注入，白名单那份在最前
    - `test_load_agent_d_respects_priority_frontmatter`：frontmatter `priority: 1` 的文件强制置顶（即使不在白名单）
    - `test_load_agent_d_priority_ties_break_by_pinned_then_name`：同优先级时白名单内优先，剩余按文件名升序
    - `test_load_agent_d_logs_summary`：用 `caplog` 断言 INFO 级别有 `agent.d injected for role=X` 输出
- `tests/unit/test_prompt_renderer.py`：无需改动（prompt 渲染对 load_agent_d 返回值是透明消费）

### 向后兼容

- **向后兼容**（非 BREAKING）。原因：
  - 白名单仍生效，仅"准入"语义降级为"置顶 hint"；用户旧 config 不需要改动
  - 新增的 `priority` frontmatter 字段是可选的，不声明等同 `priority: 100`
  - `find_agent_d()` 是新增 API，不影响存量调用
  - 日志级别提升只增加可见性，不改变错误码/抛出
- 行为差异点（**非破坏，但需 CHANGELOG 记录**）：
  - 旧版本：`agent.d/extra-note.md` 不在白名单 → 不注入
  - 新版本：`agent.d/extra-note.md` 不在白名单 → **会注入**（按文件名追加在白名单内文件之后）
  - 若用户依赖"放在 `agent.d/` 但不想被加载"，需手动移到 `memory.d/` 或在 frontmatter 加 `priority: 9999` 让它在 token 预算用尽时自然被截断（推荐前者）
- 发布时不需要 bump major：作为同一个 alpha 周期内的语义增强发布即可（与 `relocate-artifacts-to-root` 同 0.2.0aN 范围内）

### 成本预估

- 工作量：~0.5-1 天（4-8 小时）
  - `load_agent_d()` 重写 + `_load_priority` 辅助：1.5h
  - 新增 `find_agent_d()` 公开方法 + 单测：0.5h
  - 测试用例补齐（≥ 4 个新用例 + 既有用例修订）：1.5h
  - 设计文档 06-memory-system.md §4.2 重写：1h
  - CHANGELOG / NEXT.md 标注：0.5h
  - implement 阶段补 `specs/agent-d-auto-loading/spec.md` + 验证：1h
- 风险：低
  - 改动局限在 `memory/manager.py` 单一文件
  - 既有单测能覆盖"加载顺序"的核心契约，重写时回归风险可控
  - 无新依赖、无新 CLI 参数、无新配置字段
- 与活跃议题 `relocate-artifacts-to-root` 的耦合：**零耦合**。两者改的代码区域完全不重叠（一个改 artifacts/recorder.py + roles/prompt.py 的 ROLE_TO_DIR，一个改 memory/manager.py 的 load_agent_d）。可并行推进。
