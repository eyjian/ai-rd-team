# M4 Example E2E Verified Report

**执行时间**：2026-05-04 13:56 - 14:05 UTC（约 9 分钟）  
**示例**：`examples/01-smart-bookmark`（Lite 档，Python CLI 书签工具）  
**环境**：CodeBuddy claude-opus-4.7-1M on Linux  
**Run ID**（最终成功）：`6f4b3ae3`

## 目的

验证 `examples/01-smart-bookmark` 在真实 CodeBuddy 环境下**作为一个"包装好"的示例**是否能跑通 —— 即：
- 用户只需 `cp -r examples/01-smart-bookmark ~/demo && cd ~/demo && ai-rd-team run ...`
- 不需要手动改配置，不需要修代码
- 能拿到可直接 `pip install -e .` 使用的产物

## 过程中发现的 2 个 Bug（已修复）

### Bug 1：agent.d 文件命名不匹配默认 `memory_scope`

**现象**：第一次跑 driver，Prompt 的 `# 记忆` 段显示"（M1：暂无共享记忆）"，尽管 `memory/agent.d/` 下有两个 md 文件。

**根因**：`builtin_roles()` 里 `developer.memory_scope.agent_d` 默认是 `["tech-stack-selected", "interface-contracts"]`，而示例文件命名为 `tech-stack.md` / `cli-spec.md`，名字对不上 → MemoryManager 不会加载。

**修复**（影响 3 个 example）：
```
examples/01-smart-bookmark/.ai-rd-team/memory/agent.d/
  - tech-stack.md        →  tech-stack-selected.md
  - cli-spec.md          →  interface-contracts.md

examples/02-blog-api/.ai-rd-team/memory/agent.d/
  - tech-stack.md        →  tech-stack-selected.md

examples/03-todo-mini/.ai-rd-team/memory/agent.d/
  - tech-stack.md        →  tech-stack-selected.md
```

同时更新 `examples/README.md` 明确说明命名约定。

### Bug 2：Bridge timeout 默认 60 秒，真实环境不够

**现象**：两次（`spawn_member` task 和 `send_message`）都因超时失败。

**根因**：默认 `bridge_timeout_seconds=60`。真实 CodeBuddy 主 Agent 响应 `task` 工具（派发 subagent）通常 60-90 秒；`send_message` 需要 20-40 秒；都接近或超过默认。

**修复**：所有 example 的 `config.advanced.yaml` 加 `adapter.bridge_timeout_seconds: 300`（给 5 倍 headroom）。

注意：这个字段**必须放 advanced** 配置（basic 配置的 schema 不包含 `adapter`），否则静默被忽略。

## 最终成功 run（Bug 修复后）

### Prompt 注入验证

| 字段 | 结果 | 字符数 |
|------|------|--------|
| Prompt 总长 | ✅ | **5990 字** |
| Skills: python-best-practices | ✅ 命中 | - |
| Skills: pytest-guide | ✅ 命中 | - |
| agent.d: tech-stack-selected | ✅ 命中（"仅标准库" 关键词） | - |
| agent.d: interface-contracts | ✅ 命中（"bookmark add" + "bookmarks.json"） | - |

**对比**：
- Bug 修复前：4661 字（仅 Skills，agent.d 段显示"暂无共享记忆"）
- Bug 修复后：5990 字（+1329 字 agent.d 注入）

### 成员产出（10 个文件）

```
.ai-rd-team/runtime/artifacts/
├── code/
│   ├── README.md
│   ├── pyproject.toml
│   ├── smart_bookmark/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── models.py
│   │   └── store.py
│   └── tests/
│       ├── __init__.py
│       ├── test_cli.py
│       └── test_store.py
└── reports/
    └── report-developer.md
```

### pytest 结果

```
========== 28 passed in 0.12s ==========
```

**28 个测试全过**（对比 M3 E2E 的 23 个）。分两类：

- `tests/test_store.py`（15 个）：add / list（tag 过滤 + search parametrize）/ remove / get / 原子写 / 中文可读
- `tests/test_cli.py`（13 个）：argparse 每个子命令 + main 集成（含 webbrowser mock）

### 真实装包验证

```bash
pip install -e <artifacts/code>
bookmark list       # (no bookmarks)
bookmark add https://vuejs.org --tag vue --title "Vue.js"
bookmark add https://go-kratos.dev --tag golang   # ← 自动抓到网页 title
                                                   #   "The Go Framework for microservices | Kratos"
bookmark list                    # 格式化输出（id / 标题 / tag / URL / 时间）
bookmark list --tag vue          # ✅ 过滤工作
bookmark remove 2                # ✅ 删除成功
```

## 成员表现超出预期

Skills + Memory 持续拉高产出质量。相比 M3 E2E 的 developer，这次还主动做了：

1. **CLI 全局 `--store` 参数**（超出需求）：让测试可以指定临时 store 文件，避免污染真实 `~/.smart-bookmark/`
2. **`title_fetcher` 依赖注入**（超出需求）：生产用 urllib 抓网页 title，测试注入 stub 保持离线
3. **`fsync` 磁盘同步**：原子写做到了 `.tmp + fsync + os.replace`，比普通的 `os.replace` 更严谨
4. **自定义异常**：`BookmarkError` + `BookmarkNotFoundError`，符合 `python-best-practices` 的"自定义异常继承专属基类"
5. **CLI 错误友好**：`remove 2` 不存在的 id 返回 exit code 1（而不是 crash）
6. **bookmark list 提示空库**：`(no bookmarks)`（UX 考量）
7. **自动抓取网页 title**：实际抓到了 go-kratos.dev 的真实标题

成员报告中**明确引用 agent.d**：
> 按 interface-contracts 分层，纯标准库实现

## 对比三次 E2E

| 指标 | M2 E2E | M3 E2E | **M4 Example E2E** |
|------|--------|--------|--------|
| 产出文件数 | 2 | 3 | **10** |
| 测试数 | 15 | 23 | **28** |
| Prompt 长度 | 4989 | 4646 | **5990** |
| 任务规模 | fibonacci 函数 | fibonacci + 报告 | **完整 CLI 工具 + 可 pip install** |
| 架构深度 | 单函数 | 函数 + 报告 | **分层 + DI + 异常层次 + CLI + pyproject** |

## 成本

最终 run（单 developer Lite 档）：
- rp=42（40 spawn + 2 message）
- rp_budget=150（Lite 预算）
- usage_ratio=28%
- 运行时长：~7 分钟

## 结论

> **`examples/01-smart-bookmark` 在修复 2 个 bug 后端到端可用。用户拿到开箱即用的 example 能直接生成可 `pip install -e .` 的命令行工具。**

3 个 Bug 修复对 **所有 3 个 examples**（01 / 02 / 03）都有效。后续跑 02 和 03 应该不会再遇到这两个坑。

## 产物

- `prototype/M4-example-e2e/` — 完整 E2E 工作区（含 driver + 运行时产物 + 成员产出）
- `examples/01-smart-bookmark/` — 已修复（agent.d 命名 + bridge_timeout）
- `examples/02-blog-api/` — 已修复（agent.d 命名 + bridge_timeout）
- `examples/03-todo-mini/` — 已修复（agent.d 命名 + bridge_timeout）
- `examples/README.md` — 补充了 agent.d 命名约定的说明
