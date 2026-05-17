# Spec: agent-d-auto-loading

> Capability：明确 `agent.d/` 目录下记忆文件的"启动加载"契约——默认全员注入、白名单仅控顺序、frontmatter `priority` 字段精细化排序、token 预算溢出截断顺序、加载日志可见性。
> 关联变更：`openspec/changes/agent-d-auto-discovery/`
> 关联设计：`openspec/specs/design/06-memory-system.md §3.2 / §4.2`

## ADDED Requirements

### Requirement: agent.d/*.md SHALL 默认全员注入到角色启动 prompt

`MemoryManager.load_agent_d(role)` SHALL 扫描 `<workspace>/.ai-rd-team/memory/agent.d/` 与 `<global>/agent.d/` 下所有 `*.md` 文件，并默认全部纳入排序候选。`role.memory_scope["agent_d"]` 列表 SHALL NOT 用作"准入白名单"（即列表外的文件不能被它阻止注入）；该列表的语义 SHALL 降级为"建议置顶顺序"。同 stem 名时 project scope SHALL 覆盖 global scope。

#### Scenario: 白名单外的文件也被加载

- **WHEN** `agent.d/` 目录下存在 `a.md` / `b.md` / `c.md` 三份文件，`role.memory_scope == {"agent_d": ["b"]}`
- **THEN** `load_agent_d(role)` 返回的 `MemoryItem` 列表 SHALL 含 3 份；`a` 与 `c` 不能因为不在白名单而被排除

#### Scenario: 白名单为空时全员加载

- **WHEN** `agent.d/` 下有 `x.md` / `y.md`，`role.memory_scope == {}`（白名单为空）
- **THEN** `load_agent_d(role)` SHALL 返回 2 份 `MemoryItem`，按文件名字典序排列为 `[x, y]`

#### Scenario: project 覆盖 global 同名文件

- **WHEN** `<workspace>/agent.d/shared.md` 与 `<global>/agent.d/shared.md` 都存在
- **THEN** 返回的 `shared` 条目 `scope` 字段 MUST 为 `MemoryScope.PROJECT`；global 那份 SHALL NOT 被加载

### Requirement: 加载顺序 SHALL 为 (priority, pinned-first, pinned-index, name) 四级排序

加载顺序的排序键 SHALL 为：

1. **priority**（升序，整数，缺省 100）
2. **是否在白名单**（白名单内文件优先于白名单外）
3. **白名单内位置**（按 `memory_scope.agent_d` 列表中的下标升序；白名单外此项为 `+∞` 等价值）
4. **文件名 stem**（升序，字典序）

`priority` 来自文件 frontmatter 的 `priority` 字段；类型 SHALL 为 int；非 int 值（含字符串、None、float）SHALL 以默认 100 处理并打 WARNING 日志。

#### Scenario: priority 维度强于白名单

- **WHEN** `unpinned-high.md` frontmatter 含 `priority: 1`（不在白名单），`pinned-mid.md` 无 priority 声明（白名单首位）
- **THEN** `load_agent_d` 返回顺序 SHALL 为 `[unpinned-high, pinned-mid]`

#### Scenario: 同 priority 时白名单优先

- **WHEN** 4 份文件 priority 全为默认 100，`role.memory_scope == {"agent_d": ["c", "a"]}`
- **THEN** 返回顺序 SHALL 为 `[c, a, b, d]`：白名单按白名单顺序在前，剩余按文件名字典序追加

#### Scenario: priority 缺省值为 100

- **WHEN** 文件 frontmatter 不含 `priority` 字段
- **THEN** 排序时 SHALL 使用 `priority = 100`

#### Scenario: priority 非法值降级为 100 并 WARN

- **WHEN** 文件 frontmatter 含 `priority: "high"`（字符串）或 `priority: null`
- **THEN** 排序时 SHALL 使用 `priority = 100`；logger 级别 WARNING SHALL 输出消息含 `invalid priority value` 与原始值

### Requirement: token 预算溢出 SHALL 按排序顺序截断

`load_agent_d` SHALL 严格按上一 Requirement 的排序顺序消费 token 预算。一旦累计估算 token 数加上下一条目超过 `AGENT_D_TOTAL_TOKEN_LIMIT`（默认 8000），SHALL 停止注入剩余条目，并打 WARNING 日志。单文件超过 `AGENT_D_PER_FILE_TOKEN_LIMIT`（默认 2000）时 SHALL 打 WARNING 但仍注入（不阻止）。

#### Scenario: 总预算溢出按优先级保留靠前

- **WHEN** 三份文件分别 priority=1 / 10 / 100，估算 token 各 5000；预算上限 8000
- **THEN** 仅 priority=1 那份 SHALL 被注入；priority=10 与 100 SHALL 被截断；WARNING 日志 MUST 含 `truncating at` 与已注入文件数

#### Scenario: 单文件超 per-file 上限不阻止注入

- **WHEN** 某文件估算 token 为 2500（超 2000 软限），但累计未超总预算
- **THEN** 该文件 SHALL 仍被注入；WARNING 日志 MUST 含 `exceeds soft limit` 与该文件名

### Requirement: 框架 SHALL 提供 INFO 级别加载汇总日志

`load_agent_d` SHALL 在返回前输出一条 INFO 级别日志，记录最终注入的 stem 列表与 role 名。当白名单声明的 stem 在磁盘上不存在时，SHALL 以 INFO 级别（非 DEBUG）输出 `agent.d pinned but not found: <name>`，使默认日志级别下用户可观测到配置漂移。

#### Scenario: 注入汇总以 INFO 级别输出

- **WHEN** `load_agent_d(role)` 完成注入，role.name 为 `architect`，最终注入 stem 列表为 `["onboarding-entrypoint", "tech-stack-selected"]`
- **THEN** logger 级别 INFO 的输出 SHALL 含 `agent.d injected for role=architect:` 且参数列表 MUST 为 `['onboarding-entrypoint', 'tech-stack-selected']`

#### Scenario: 白名单 pinned-but-missing 以 INFO 级别输出

- **WHEN** `role.memory_scope == {"agent_d": ["nonexistent"]}`，`agent.d/` 下不存在 `nonexistent.md`
- **THEN** logger 级别 INFO 的输出 SHALL 含 `agent.d pinned but not found: nonexistent`；MUST NOT 抛异常；MUST NOT 阻止其它文件注入

### Requirement: MemoryManager SHALL 暴露 find_agent_d 公开方法

`MemoryManager` SHALL 提供 `find_agent_d(name: str, include_global: bool = True) -> MemoryItem | None` 公开方法，按 stem 名查找单个 `agent.d` 条目。该方法 SHALL NOT 应用 token 预算（区别于 `load_agent_d`）。同 stem 名时 project scope SHALL 覆盖 global scope。文件不存在时 SHALL 返回 `None`，不抛异常。

#### Scenario: project scope 命中

- **WHEN** `<workspace>/.ai-rd-team/memory/agent.d/foo.md` 存在
- **THEN** `find_agent_d("foo")` SHALL 返回 `MemoryItem`，`scope == MemoryScope.PROJECT`

#### Scenario: 回退到 global scope

- **WHEN** project 下无 `bar.md`，`<global>/agent.d/bar.md` 存在，`include_global=True`
- **THEN** `find_agent_d("bar")` SHALL 返回 `MemoryItem`，`scope == MemoryScope.GLOBAL`

#### Scenario: 文件不存在返回 None

- **WHEN** project 与 global 下均无 `missing.md`
- **THEN** `find_agent_d("missing")` SHALL 返回 `None`；MUST NOT 抛异常

#### Scenario: 不应用 token 预算

- **WHEN** `agent.d/big.md` 估算 token 为 9000（超过 `AGENT_D_TOTAL_TOKEN_LIMIT` 8000）
- **THEN** `find_agent_d("big")` SHALL 仍正常返回 `MemoryItem`（`load_agent_d` 才会受预算约束）
