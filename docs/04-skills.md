# Skills 指南

Skills 是 **Markdown 格式的知识卡片**，在成员 spawn 时注入到 Prompt 的 `# Skills` 段，让成员拥有专业技能。

## 三层加载优先级

```
Skill 'pytest-guide' 加载顺序（从高到低）：
  1. workspace  → <ws>/.ai-rd-team/skills/pytest-guide.md
  2. global     → ~/.ai-rd-team/skills/pytest-guide.md
  3. builtin    → ai_rd_team/skills/builtin/pytest-guide.md
```

同名 Skill 高优先级覆盖低优先级（workspace > global > builtin）。

## 引用语法

在 `config.advanced.yaml` 的 `roles.<name>.skills` 列表里：

```yaml
roles:
  developer:
    skills:
      - "pytest-guide"              # 走三层优先级
      - "builtin:pytest-guide"      # 强制用 builtin（即便 workspace 有同名）
```

## 内置 Skills（6 个）

| 名称 | 适用 | 默认给谁 |
|------|------|---------|
| `python-best-practices` | 所有 Python 编码 | developer, reviewer |
| `pytest-guide` | pytest 测试 | developer, tester |
| `code-review-checklist` | 代码检视 | architect, reviewer |
| `go-kratos-basics` | Go + Kratos 后端 | 用户在 config.advanced.yaml 显式引用 |
| `vue3-basics` | Vue 3 + Vite + TS | 用户在 config.advanced.yaml 显式引用 |
| `wxmini-basics` | 微信小程序（原生） | 用户在 config.advanced.yaml 显式引用 |

查看位置：
```bash
python -c "from ai_rd_team import builtin_skills_dir; print(builtin_skills_dir())"
```

## 编写自定义 Skill

Skill 是一个 Markdown 文件，推荐包含：

```markdown
# <Skill 名字>

## 适用场景
什么时候用这个 Skill。

## 核心原则
3-5 条最关键的规则。

## 常用模式
2-4 个典型用法，带代码示例。

## 禁止
明确列出不应该做的事（负面清单很关键）。

## 参考
外部链接。
```

### 放到哪里？

| 范围 | 路径 | 场景 |
|------|------|------|
| 项目级 | `<ws>/.ai-rd-team/skills/my-skill.md` | 只适用本项目 |
| 全局级 | `~/.ai-rd-team/skills/my-skill.md` | 跨项目通用（如公司规范） |
| 贡献回内置 | `src/ai_rd_team/skills/builtin/my-skill.md` | 所有用户能用（提 PR） |

## 让 Skill 真正影响成员

Skills 能影响行为，但**有几个前置条件**：

1. **被引用**：确保 `roles.<role>.skills` 包含这个 Skill
2. **内容够具体**：「用 pytest」没用，「用 `@pytest.mark.parametrize` 覆盖边界/异常/正常三类」才有用
3. **禁止清单明确**：「不要 X」比「要 Y」更有效
4. **带代码示例**：成员会模仿示例风格

### 真实案例（M3 E2E）

开发者只收到 `python-best-practices` + `pytest-guide` 两个 Skill，就主动做到了：

- 识别 `isinstance(True, int) == True` 的 Python 陷阱并加专项测试
- 加 `TypeError` 检查非 int 输入（超出最小契约）
- 函数名用 `test_<对象>_<场景>_<期望>` 命名法
- 加入递推关系交叉验证 `fib(50) == fib(49) + fib(48)`

因为 `python-best-practices` 写了：
> - ❌ 用 `is` 比较字符串（应用 `==`）
> - ❌ 把 mutable default arg

而 `pytest-guide` 写了：
> - `@pytest.mark.parametrize` 覆盖多用例
> - 函数命名 `test_<对象>_<场景>_<期望>`

## Token 预算

Skills 默认不限制 token 数（只有 Memory 有预算）。但：

- 单个 Skill 文件建议 ≤ 2000 字（过长影响 Prompt 比重）
- 一个角色建议最多 2-3 个 Skill（更多会稀释注意力）

## 查看成员实际看到的 Skills

```bash
# 启动 run 后，Prompt 会写到 adapter-intents/*.json
cat .ai-rd-team/runtime/adapter-intents/*.json | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['prompt'])" | \
  sed -n '/# Skills/,/# 记忆/p'
```

## 相关设计文档

- `openspec/specs/design/05-roles-skills.md` — Skills 体系完整设计
- `src/ai_rd_team/roles/skills_loader.py` — 实现与 API
