# P2：Skills 加载实验

## 验证假设
成员能读取 `.codebuddy/skills/` 或项目 `.ai-rd-team/skills/` 目录中的 Skills，并在工作中应用这些规范。

**核心疑问**：Skills 是**自动生效**的，还是需要在 prompt 中**显式引用**才会被应用？

## 实验设计

### 测试 Skills
放置 2 个对比明显的规范到 `skills/` 目录：

- `python-coding-style.md`：强制使用 `snake_case`、类型注解、`black` 风格
- `pytest-guide.md`：强制使用 `pytest.fixture`（而非 `unittest.setUp`）、参数化测试

### 对照组
分两组派发，观察 Skills 是否被遵守：

| 组别 | 是否在 prompt 中引用 skills | 预期行为 |
|------|----------------------------|---------|
| **组 A** | 不引用 | 如果 Skills 自动生效，代码符合规范 |
| **组 B** | 显式引用 skills 目录 | 代码必然符合规范 |

观察两组差异，判断 Skills 加载机制。

## 真实实验步骤

1. 把准备好的 skills 文件放到 `02-skills-loading/skills/` 和 `.codebuddy/skills/`
2. 派发 2 个 developer：
   - `dev_a`：prompt 仅"实现一个 Python 加法函数"，不提 skills
   - `dev_b`：prompt"实现一个 Python 加法函数，请遵循 `.codebuddy/skills/` 中的规范"
3. 收集产物到 `results/artifacts/`，对比分析
4. 记录到 `results/skills-behavior.md`

## 成功标准

| # | 指标 | 判定 |
|---|------|------|
| 1 | 组 A 自动应用 Skills？ | ✅ 自动 / ⚠️ 部分应用 / ❌ 不应用 |
| 2 | 组 B 显式应用 Skills？ | ✅ 应用 / ❌ 未应用 |
| 3 | Skills 内容是否完整读取？ | 从代码中看是否体现规范细节 |

## 结论的影响

| 情况 | 对 ai-rd-team 设计的影响 |
|------|-------------------------|
| 自动生效 | 架构简单，Skills 目录约定即可 |
| 需显式引用 | 需要在每个成员 prompt 模板中 inject skills 路径/内容 |
| 混合（部分自动） | 关键 Skills 显式注入，辅助 Skills 自动 |

## 产物清单
- `skills/python-coding-style.md`
- `skills/pytest-guide.md`
- `results/artifacts/dev_a/*`
- `results/artifacts/dev_b/*`
- `results/skills-behavior.md`：对比分析
- `results/conclusion.md`：结论
