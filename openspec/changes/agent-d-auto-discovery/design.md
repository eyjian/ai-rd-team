# Design: agent-d-auto-discovery

> 议题目的：把 `agent.d/` 的"启动加载"语义从"白名单准入"修正为"目录全员注入 + 白名单/priority 控顺序"，配套提升加载日志可见性。
>
> 范围边界：仅改 `src/ai_rd_team/memory/manager.py` 的 `load_agent_d()` + 新增 `find_agent_d()` 公开方法 + 设计文档 `06-memory-system.md` §3.2/§4.2 + 单测。其它一概不动。
>
> 关联议题：与 `relocate-artifacts-to-root` 零耦合，可并行 implement。

## 关键设计决策

### D1：是否在框架代码里硬编码 `onboarding-entrypoint`？

**最终：不硬编码**。

候选方案：
- A. 在 `roles/prompt.py` 写死 `ONBOARDING_NAMES = ("onboarding-entrypoint", "project-overview")` 框架级置顶
- B. 不在框架代码动具体名，靠"目录全员注入 + frontmatter `priority`"通用机制让 Skill 自己声明
- C. 在 `defaults.yaml` 配置文件里列硬编码名（半软）

选 **B**。理由：

1. **职责边界清晰**：`onboarding-entrypoint.md` 是 launcher Skill 的约定文件，不是框架内核能力。把名字硬编码进 Python 等于把 Skill 的命名习惯绑进框架，未来换 launcher 实现/Skill 更名都要改 Python，违反"Skill 可拔插"原则
2. **机制完备**：方案 B 提供的 `priority: 1` 完全覆盖方案 A 的所有需求——任何想置顶的文件，frontmatter 里加一行就行；不限于 onboarding，未来其它 Skill 也能用同套机制
3. **可观测性等价**：方案 A 的"框架硬注入" vs 方案 B 的"目录全员加载 + priority 排序"，最终用户感知一致——onboarding 都在 prompt 最前；但 B 让"为什么它在最前"的原因可追溯（看文件 frontmatter 即可），A 的原因藏在 Python 常量里
4. **本议题已经在做"全员注入"**：方案 B 等于复用本议题主体改造的副产物，零额外代码；方案 A 反而要在 prompt.py 加"两阶段合并 + 去重"逻辑，复杂度反升

被拒方案的反驳：

- 方案 A 的"`onboarding-entrypoint` 是事实标准"——这是当前一个 Skill 的约定，不能反推为框架级标准。框架不能假设所有 Skill 都用这个名字
- 方案 C 的"半软"不可取——`defaults.yaml` 仍然是框架仓库下的配置，下游项目不能改；与方案 A 本质相同

### D2：白名单语义降级，还是直接废弃？

**最终：降级为"建议置顶顺序"，不废弃**。

候选方案：
- A. 直接废弃 `memory_scope.agent_d` 字段，全靠目录扫描 + priority
- B. 白名单语义从"准入"降级为"置顶 hint"，与 priority 字段叠加排序
- C. 双轨制：白名单决定"哪些加载"，priority 决定"加载内的顺序"（不变）

选 **B**。理由：

1. **向后兼容**：当前所有内置角色（pm/analyst/architect/...）都在 `_DEFAULT_ROLE_MEMORY_SCOPE` 里有非空白名单；用户 config 也可能 override。废弃会导致**老配置直接失效或语义逆转**（白名单内文件不再优先）
2. **白名单仍有独立价值**：priority 是文件级标注（写到 .md frontmatter 里），白名单是角色级标注（哪些 .md 对哪个 role 重要）。两者维度不同，叠加才是完整表达力
   - 例：`tech-stack-selected.md` 不写 priority（保持中性），但在 architect 的白名单里——表达"它对架构师重要，但不一定对全队都最优先"
   - 这种"角色相关性"不应该写到文件 frontmatter 里（违反"agent.d 是共享背景"的语义）
3. **降级成本低**：仅改一处 `load_agent_d()` 的循环逻辑（白名单 → 排序键），不改字段、不改 schema、不改用户文档主结构

排序优先级（priority 内 ties 时）：

```
sort_key = (priority, NOT pinned, name)
```

- `priority` ASC（数字小优先）
- `NOT pinned` ASC（白名单内的 `False=0` 优先于白名单外的 `True=1`）
- `name` ASC（文件名字典序）

举例：

| 文件 | priority | 在白名单 | sort_key |
|---|---|---|---|
| onboarding-entrypoint.md | 1 | 否 | (1, True, ...) |
| tech-stack-selected.md | 100 | 是（第 0 位） | (100, False, ...) |
| key-decisions.md | 100 | 是（第 2 位） | (100, False, ...) |
| domain-glossary.md | 100 | 否 | (100, True, ...) |

但 sort 不能直接对"白名单第 0 位 vs 第 2 位"排序——这要求**白名单内文件按白名单顺序保持**。所以最终采用"两阶段排序"：

```python
# 阶段 1：先按 priority 分桶
# 阶段 2：每个 priority 桶内，白名单内文件按白名单顺序在前；白名单外按文件名 ASC
```

### D3：frontmatter `priority` 默认值是多少？

**最终：100**（语义为"中性"）。

理由：

- 用户置顶时常用 1/10 等小数字，符合 nice 风格直觉
- 100 留出大量负权 / 大权空间，未来扩展（如负数表示"压到最后但保留"）有余地
- 与 Linux nice 值（默认 0，正大负小）反向是有意为之——本议题的 priority 用"小=优先"，符合"优先级队列"惯例（heapq）

### D4：`find_agent_d()` 是否本议题强需求？

**最终：本议题落盘 API，但不强依赖**。

理由：

- 目的：未来"engine 自动注入活跃议题入口"等增强需要按 stem 查找 agent.d 单条目；提前把 API 占位，避免后续 follow-up 议题时还要回头改 manager
- 实现成本：仅 ~10 行（复用既有 `_find_in_layer`）
- 测试成本：≤ 2 个用例
- 不强依赖意味着：本议题主体（load_agent_d 重写）即使没有 find_agent_d 也能独立闭环

### D5：日志级别提升的细节

| 事件 | 旧级别 | 新级别 | 理由 |
|---|---|---|---|
| `agent.d not found: <name>`（白名单 pinned 但磁盘缺失） | DEBUG | **INFO** | 白名单声明 = 用户预期会有；实际没有 = 配置漂移信号，应可见 |
| `agent.d budget exceeded; truncating ...` | WARNING | WARNING（不变） | 既有，已可见 |
| `agent.d file <name> exceeds soft limit` | WARNING | WARNING（不变） | 既有，已可见 |
| **新增**：`agent.d injected for role=<name>: [<list>]` | — | **INFO** | 让用户从默认日志一眼确认实际注入清单 |

不把 not-found 提到 WARNING 的理由：未来"自动发现"+"白名单宽松"组合下，白名单里写但目录里没有的情况会很常见（用户可能临时移走文件），WARNING 噪声大；INFO 足够覆盖可观测性。

### D6：本议题与 `relocate-artifacts-to-root` 的隔离

| 维度 | 本议题 | relocate-artifacts-to-root |
|---|---|---|
| 改的核心文件 | `memory/manager.py` | `artifacts/recorder.py`、`artifacts/layout.py`（新）、`runtime/state.py` |
| 触及的 prompt.py | **无改动** | `ROLE_TO_DIR` 删除、`ROLE_TO_WRITE_METHOD` 新增 |
| 触及的 manager.py | **load_agent_d 重写**、`find_agent_d` 新增 | 无 |
| 测试文件 | `tests/unit/test_memory_manager.py` | `tests/unit/test_recorder_layout.py` 等 |
| 文档 | `06-memory-system.md` | `07-artifacts.md` / `11-runtime-protocol.md` |
| 配置 schema | 无变化 | 新增 `artifacts.layout` 段 |

两个议题在 git 层面也不会冲突（不改同一行）。可并行 implement，发布时合并到同一个 alpha 节奏（0.2.0aN）。

## 实现要点

### load_agent_d 新流程

```python
def load_agent_d(self, role: object, include_global: bool = True) -> list[MemoryItem]:
    memory_scope = getattr(role, "memory_scope", None) or {}
    pinned: list[str] = list(memory_scope.get("agent_d") or [])
    pinned_set = set(pinned)
    pinned_index = {name: i for i, name in enumerate(pinned)}

    # 1) 扫描所有 scope 下 agent.d/*.md，project 覆盖 global（同 stem 取 project）
    discovered: dict[str, MemoryItem] = {}
    for scope_dir, scope in self._iter_scope_dirs(include_global):
        base = scope_dir / MemoryLayer.AGENT_D.value
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*.md")):
            stem = path.stem
            if stem in discovered:
                continue  # project 优先于 global
            discovered[stem] = self._parse_file(MemoryLayer.AGENT_D, path, scope)

    # 2) 警告白名单 pinned 但磁盘缺失（INFO 级别）
    for name in pinned:
        if name not in discovered:
            logger.info("agent.d pinned but not found: %s", name)

    # 3) 排序：(priority, NOT pinned, pinned_index_or_inf, name)
    def sort_key(item: MemoryItem) -> tuple[int, int, int, str]:
        priority = self._load_priority(item.frontmatter)
        is_pinned = item.name in pinned_set
        idx = pinned_index.get(item.name, len(pinned))
        return (priority, 0 if is_pinned else 1, idx, item.name)

    ordered = sorted(discovered.values(), key=sort_key)

    # 4) 应用 token 预算
    items: list[MemoryItem] = []
    total = 0
    for item in ordered:
        if total + item.estimated_tokens > AGENT_D_TOTAL_TOKEN_LIMIT:
            logger.warning(
                "agent.d budget exceeded; truncating at %s tokens after %s files (limit %s)",
                total, len(items), AGENT_D_TOTAL_TOKEN_LIMIT,
            )
            break
        if item.estimated_tokens > AGENT_D_PER_FILE_TOKEN_LIMIT:
            logger.warning(
                "agent.d file %s exceeds soft limit (%s > %s tokens)",
                item.name, item.estimated_tokens, AGENT_D_PER_FILE_TOKEN_LIMIT,
            )
        items.append(item)
        total += item.estimated_tokens

    # 5) 汇总日志（INFO）
    role_name = getattr(role, "name", "<unknown>")
    logger.info(
        "agent.d injected for role=%s: %s",
        role_name, [it.name for it in items],
    )
    return items
```

### `_load_priority` 辅助

```python
def _load_priority(self, meta: dict[str, Any]) -> int:
    raw = meta.get("priority", 100)
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning("invalid priority value %r in agent.d frontmatter; defaulting to 100", raw)
        return 100
```

### `find_agent_d` 公开方法

```python
def find_agent_d(self, name: str, include_global: bool = True) -> MemoryItem | None:
    """按 stem 名查找单个 agent.d 条目（不应用 token 预算）。"""
    return self._find_in_layer(MemoryLayer.AGENT_D, name, include_global=include_global)
```

注：`_find_in_layer` 已存在（manager.py:436），`find_agent_d` 等同于"加层薄壳"对外暴露，符合 Python 公开 API 命名约定。

### frontmatter `priority` 字段示例

```markdown
---
type: memory
layer: agent.d
author: launcher-skill
created: 2026-05-17
priority: 1            # ← 新增字段；越小越靠前；缺省 100
tags: [onboarding, must-read]
---

# Onboarding Entrypoint

...
```

## 不在本议题做的事（与 proposal 非目标对应）

1. **engine 自动注入活跃 OpenSpec 议题摘要到 prompt** —— 留作 follow-up `inject-active-openspec-change` 议题
2. **CLI `run --change <id>` / `--task-filter <pattern>`** —— 与 #1 同议题
3. **`_DEFAULT_ROLE_MEMORY_SCOPE` 搬到 `defaults.yaml`** —— 仅"配置层化"重构，不改语义；留作 follow-up
4. **architect persona 加冲突仲裁规则** —— Skill / Role 文本编辑，不改 Python 代码；留作 follow-up

## 验收预期（implement 阶段对齐）

- [ ] `tests/unit/test_memory_manager.py` 全绿；新增用例 ≥ 4 个
- [ ] `pytest -q` 整体全绿（不引入回归）
- [ ] `ruff check .` / `ruff format --check .` 全绿
- [ ] `06-memory-system.md` §3.2 / §4.2 已更新；人工读一遍通顺
- [ ] CHANGELOG `[Unreleased]` 节记 Changed/Added 三条
- [ ] 跑一次 `examples/02-blog-api/`（在 relocate 议题已合的前提下），目测 `runtime/logs/run.stdout.log` 含 `agent.d injected for role=...` INFO 行
- [ ] 验证向后兼容：把现有 fixture（白名单内文件）跑一遍，注入顺序与旧版本一致（仅多注入"白名单外但目录内"的额外文件）
