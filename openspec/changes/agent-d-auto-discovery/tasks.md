# Tasks: agent-d-auto-discovery

> 总预算：~0.5-1 天（4-8 小时）。每项 ≤ 2 小时，含实现 + 测试 + 文档。
> 实现顺序：先重写 `load_agent_d`（核心），再补 `find_agent_d`（API 占位），然后单测、最后文档 / CHANGELOG。
> 非 BREAKING：白名单语义降级是向后兼容扩展，不需要 bump major。
>
> 与活跃议题 `relocate-artifacts-to-root` **零耦合**，可并行 implement。
>
> **proposal 阶段已完成**（不计入 implement 工作量）：
> - `proposal.md` / `design.md` / `specs/agent-d-auto-loading/spec.md`（4 个 Requirement，13 个 Scenario）
> - `openspec validate agent-d-auto-discovery --strict` 已通过

## 1. MemoryManager 核心重写

- [ ] 1.1 在 `src/ai_rd_team/memory/manager.py` 新增内部辅助 `_load_priority(meta: dict[str, Any]) -> int`
  - 从 frontmatter 读 `priority` 字段，未声明返回 `100`
  - 非整数（如字符串 / None）打 WARNING 后返回 `100`
  - **验收**：单测 `test_load_priority_default_when_missing`、`test_load_priority_invalid_value_warns`

- [ ] 1.2 重写 `MemoryManager.load_agent_d(role, include_global=True)`：
  - 扫描所有 scope 下 `agent.d/*.md`，project 优先于 global（同 stem 取 project）
  - 白名单 pinned 但磁盘缺失：从 DEBUG 提到 INFO，日志改为 `agent.d pinned but not found: <name>`
  - 排序键：`(priority, 0 if pinned else 1, pinned_index_or_inf, name)`
  - 应用 token 预算：累计超出 `AGENT_D_TOTAL_TOKEN_LIMIT` 时截断（保持现有 WARNING 文案，但补充"after N files"信息）
  - 单文件超 `AGENT_D_PER_FILE_TOKEN_LIMIT` 仍打 WARNING（不变）
  - 函数返回前打 INFO 汇总日志：`agent.d injected for role=<name>: [<list of stems>]`
  - **验收**：lint 过；既有 `tests/unit/test_memory_manager.py` 中关于 load_agent_d 的用例迁移后全绿

- [ ] 1.3 新增 `MemoryManager.find_agent_d(name: str, include_global: bool = True) -> MemoryItem | None`
  - 内部委托 `_find_in_layer(MemoryLayer.AGENT_D, name, include_global=include_global)`
  - 不应用 token 预算（区别于 `load_agent_d`）
  - **验收**：单测 `test_find_agent_d_hits_project_scope`、`test_find_agent_d_falls_back_to_global`、`test_find_agent_d_returns_none_when_missing`

## 2. 单测补齐

- [ ] 2.1 在 `tests/unit/test_memory_manager.py` 新增用例：
  - `test_load_agent_d_includes_unpinned_files`
    - fixture：`agent.d/` 下 3 份 .md（`a.md` / `b.md` / `c.md`），白名单只列 `["b"]`
    - 期望：返回 3 份，顺序 `[b, a, c]`（白名单内优先；其余按文件名 ASC）
  - `test_load_agent_d_respects_priority_frontmatter`
    - fixture：`high.md` 含 `priority: 1`、`mid.md` 含 `priority: 100`、`low.md` 含 `priority: 999`
    - 白名单为空
    - 期望：顺序 `[high, mid, low]`
  - `test_load_agent_d_priority_overrides_pinned`
    - fixture：`pinned-mid.md`（白名单首位，无 priority = 100）、`unpinned-high.md`（不在白名单，priority: 1）
    - 期望：`unpinned-high` 在前，`pinned-mid` 在后（priority 维度强于 pinned）
  - `test_load_agent_d_priority_ties_break_by_pinned_then_name`
    - fixture：4 份 .md priority 全 100；白名单 `["c", "a"]`
    - 期望顺序：`[c, a, b, d]`（白名单按白名单顺序在前；剩余按文件名 ASC）
  - `test_load_agent_d_pinned_missing_logs_info`
    - fixture：白名单 `["nonexistent"]`，目录里没有
    - 用 `caplog.at_level(logging.INFO)` 断言含 `pinned but not found: nonexistent`
  - `test_load_agent_d_logs_summary`
    - fixture：白名单 `["a"]`，目录里有 `a.md` / `b.md`
    - 用 `caplog.at_level(logging.INFO)` 断言含 `agent.d injected for role=` 且参数是 `['a', 'b']`
  - `test_load_agent_d_budget_truncates_in_priority_order`
    - fixture：3 份 .md，第 1 份 priority=1 体积 5K，第 2 份 priority=10 体积 5K（合计 10K 超 8K 上限）
    - 期望：仅第 1 份注入；WARNING 日志含 `truncating at`
  - `test_load_agent_d_invalid_priority_defaults_to_100`
    - fixture：`weird.md` 含 `priority: "high"`（字符串）
    - 期望：被当作 priority=100 排序；WARNING 日志含 `invalid priority value`
  - **验收**：以上 ≥ 8 个用例全绿；既有用例（如有"白名单外不加载"的旧断言）改为符合新语义的断言

- [ ] 2.2 既有 `tests/unit/test_memory_manager.py` 中关于"白名单准入"的反向断言审查
  - **检查**：`grep -n "agent.d not found\|agent_d.*not.*load" tests/unit/test_memory_manager.py`
  - 把"断言文件不被加载"的用例改为"断言文件被加载且位置符合新排序"
  - **验收**：审查结果记入本任务 commit message

## 3. 文档同步

- [ ] 3.1 更新 `openspec/specs/design/06-memory-system.md` §3.2（frontmatter Schema）
  - 在表格里新增 `priority` 行：`int (optional)`，默认 100，描述"agent.d 加载排序优先级，越小越靠前"
  - **验收**：表格格式与既有字段一致；与 design.md D3 的描述对齐

- [ ] 3.2 更新 `openspec/specs/design/06-memory-system.md` §4.2（agent.d 加载策略）
  - 删除"严格按 memory_scope.agent_d 列表加载"的描述
  - 新增三段：
    1. 默认行为：`agent.d/` 下所有 `.md` 默认全部加载
    2. 排序规则：`(priority, pinned_first, pinned_index, name)` 四级
    3. token 预算：累计 ≤ 8000，按排序顺序消费，超出则截断
  - **验收**：人工读一遍通顺；与 design.md 的实现要点描述完全一致

- [ ] 3.3 更新 `CHANGELOG.md` 的 `[Unreleased]` 节
  - **Changed**：`agent.d/` 加载策略——目录下所有 `.md` 默认注入；`memory_scope.agent_d` 白名单语义从"准入"降级为"建议置顶顺序"
  - **Added**：frontmatter `priority` 字段（int，默认 100，越小越靠前）
  - **Added**：`MemoryManager.find_agent_d(name)` 公开方法
  - **Changed**：`agent.d` pinned-but-missing 日志从 DEBUG 升至 INFO；新增 `agent.d injected for role=...` 加载汇总 INFO 日志
  - **验收**：Keep a Changelog 风格；不引入"BREAKING"标记

## 4. specs delta（已在 proposal 阶段完成）

- [x] 4.1 `openspec/changes/agent-d-auto-discovery/specs/agent-d-auto-loading/spec.md` 已落盘
  - 含 4 个 Requirement、13 个 Scenario
  - `openspec validate agent-d-auto-discovery --strict` 通过
  - implement 阶段若发现契约需调整，修改本文件即可（OpenSpec 允许 spec delta 在 implement 中演进）

## 5. 验证

- [ ] 5.1 `pytest -q` 整体全绿
  - **验收**：exit=0；新增 ≥ 8 + 既有用例总数与 implement 前持平或上升

- [ ] 5.2 `ruff check .` / `ruff format --check .` 全绿
  - **验收**：exit=0

- [ ] 5.3 在 `examples/` 下任选一个能跑通的 example（建议待 `relocate-artifacts-to-root` 完成 6.x E2E 后用 02-blog-api），跑一次完整 run
  - **验收**：`runtime/logs/run.stdout.log` 含 `agent.d injected for role=architect: [...]` INFO 行；列表里包含 agent.d 目录下所有 .md 的 stem（除非超 token 预算被截）

- [ ] 5.4 向后兼容验证
  - **方法**：找一个既有 workspace（如 examples/01 或 02 的 fixture），分别用旧版（git checkout 至 implement 前）和新版各跑一次 dry-run，对比 prompt 渲染结果中 agent.d 段
  - **验收**：白名单内文件的相对顺序两版一致；新版多出"白名单外但目录内"的文件，挂在白名单文件之后

## 6. 归档 / 提交

- [ ] 6.1 确认 1-5 全部 `[x]`
  - **验收**：本文件所有任务勾选

- [ ] 6.2 commit：`git commit -m "agent-d-auto-discovery: scan all agent.d/*.md by default, white-list as ordering hint"`

- [ ] 6.3 执行 `openspec archive agent-d-auto-discovery`
  - **验收**：`openspec/changes/archive/<date>-agent-d-auto-discovery/` 存在；`specs/agent-d-auto-loading/spec.md` 成为正式 spec

- [ ] 6.4 更新 `NEXT.md`：标记本议题完成；候选 follow-up 议题记一笔
  - 候选 follow-up：
    1. `inject-active-openspec-change`（engine 自动检测活跃 change 并注入议题摘要到 prompt + `run --change`/`--task-filter`）
    2. `role-memory-scope-to-defaults`（`_DEFAULT_ROLE_MEMORY_SCOPE` 搬到 `defaults.yaml`）
    3. `architect-persona-conflict-arbitration`（architect 角色 persona 加"多源冲突仲裁规则"）
