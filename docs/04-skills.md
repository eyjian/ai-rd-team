# Skills 指南

Skills 是 **Markdown 格式的知识卡片**，在成员 spawn 时注入到 Prompt 的 `# Skills` 段，让成员拥有专业技能。

> **与 Anthropic Skills 的关系**
>
> 本项目的 Skill 概念受 [Anthropic Skills](https://github.com/anthropics/skills) 启发，但**两者不同**：
>
> | 维度 | 本项目 Skill | Anthropic Skill |
> |---|---|---|
> | 加载时机 | 角色 spawn 时**主动注入** prompt | LLM 运行中根据 description **自主触发** |
> | 是否需 frontmatter | 可选（向后兼容） | 必须 |
> | 是否可含脚本 | 不含（纯知识卡片） | 可含 `scripts/` / `references/` / `assets/` |
>
> Skill 文件可选加上 YAML frontmatter（见下文），让它同时保留向 Anthropic 标准靠拢的能力。

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

或者通过 CLI 列出三层全部 Skill（含 description / default_for）：
```bash
ai-rd-team roles-skill list                  # 三层全列
ai-rd-team roles-skill list --scope builtin  # 只看某层
ai-rd-team roles-skill list --json           # JSON 输出，便于脚本消费
ai-rd-team roles-skill show pytest-guide     # 查看单个 Skill 的元数据
ai-rd-team roles-skill show pytest-guide --content   # 顺便打印正文
```

> 注意：`ai-rd-team roles-skill *` 是项目内 Skill 体系的命令，对应注入数字员工 prompt 的三层加载（builtin / global / workspace）；不要和 `ai-rd-team skills`（CodeBuddy plugin marketplace 安装信息）混淆。

## 编写自定义 Skill

Skill 是一个 Markdown 文件，推荐包含：

```markdown
---
name: <skill-name>
description: 一句话说明这个 Skill 是干什么的、何时使用。
default_for: []
---

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

> **frontmatter 是可选的**。旧文件只有正文也能正常加载，不会报错。字段说明见下一节。

## YAML frontmatter（可选）

Skill 文件可以在顶部加上一段 YAML frontmatter，提供结构化元数据。

```yaml
---
name: code-review-checklist
description: 代码评审清单。在评审 PR / 代码质量检查时使用。
default_for: [architect, reviewer]
---
```

### 字段说明

| 字段 | 是否必填 | 含义 |
|---|---|---|
| `name` | 推荐 | 标识符，需与文件名 `<name>.md` 一致（仅作文档价值，不影响加载） |
| `description` | 推荐 | 一句话描述。**本项目不用于触发**，仅用于文档生成、CLI 列表、以及未来对外分发为标准 Skill |
| `default_for` | 可选 | 本项目自定义扩展，标记该 Skill 默认装配给哪些角色。**与 `_DEFAULT_ROLE_SKILLS` 镜像一致**，本身不决定装配行为 |

### 加载行为

- **有 frontmatter**：加载后正文会被提取出来注入 prompt，`---` 块不会进入 prompt；metadata 以只读 Mapping 的形式暴露在 `LoadedSkill.metadata`
- **无 frontmatter**：文件原样被当作正文注入 prompt，`metadata` 为 `None`（完全向后兼容）
- **坏的 YAML**：不报错。容错处理为"无 metadata"，但 `---` 块仍会被剥离（避免污染 prompt）

### 什么时候需要写 frontmatter？

- **builtin Skill（贡献回内置）**：必须写。项目有守门测试检查所有 builtin 必须带 frontmatter 且 `default_for` 与代码中默认装配镜像一致
- **workspace / global Skill**：完全可选。只是可以让 `description` 出现在 CLI / Web 面板里，以后也能够从本项目中导出为 Anthropic 标准 Skill

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

## 完整示例：给项目加一个自定义 Skill

下面是一个端到端 walkthrough，**抄这一段就能跑起来**。假设你在开发一个 FastAPI 项目，想约束成员统一用 `APIRouter` 分组路由。

### 第 1 步：创建 Skill 文件

在**工作区** `<workspace>/.ai-rd-team/skills/` 下建 `fastapi-routers.md`：

```markdown
# fastapi-routers

## 适用场景

所有 FastAPI 项目的路由组织。

## 核心原则

1. 每个业务模块独立 `APIRouter`，不把路由直接挂到 `FastAPI` 实例上
2. Router 文件放在 `app/routers/<domain>.py`，由 `app/main.py` 统一 `include_router`
3. 路由函数签名必须声明返回类型（Pydantic model 或 `dict[str, Any]`）

## 常用模式

**推荐**：

\`\`\`python
# app/routers/users.py
from fastapi import APIRouter, status
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/{user_id}", response_model=UserOut, status_code=status.HTTP_200_OK)
async def get_user(user_id: int) -> UserOut:
    ...
\`\`\`

**`main.py` 统一注册**：

\`\`\`python
from fastapi import FastAPI
from app.routers import users, orders

app = FastAPI()
app.include_router(users.router)
app.include_router(orders.router)
\`\`\`

## 禁止

- ❌ 在 `main.py` 里直接写 `@app.get("/users/{id}")`
- ❌ 一个 router 文件塞多个业务域（users + orders 混在一起）
- ❌ 省略 `response_model` 直接返回 dict（前端无法生成类型）

## 参考

- https://fastapi.tiangolo.com/tutorial/bigger-applications/
```

> 💡 写 Skill 的黄金法则：**正面模式 + 反面禁止**。只说"要 X"没用，必须配 "不要 Y"。

### 第 2 步：在 config.advanced.yaml 引用

```yaml
# <workspace>/.ai-rd-team/config.advanced.yaml

adapter:
  bridge_timeout_seconds: 300

roles:
  developer:
    skills:
      - "builtin:python-best-practices"    # 继续用 builtin
      - "builtin:pytest-guide"
      - "fastapi-routers"                  # ← 新加的自定义 Skill

  reviewer:
    skills:
      - "builtin:code-review-checklist"
      - "fastapi-routers"                  # ← reviewer 也用同一份规范
```

`fastapi-routers` 没有 `builtin:` 前缀，会走三层优先级：先查 workspace → global → builtin。这里因为只有 workspace 有，就用 workspace 那份。

### 第 3 步：启动 run 并验证 Skill 真被加载

```bash
# 启动后在 runtime/adapter-intents/ 里就能看到给成员的 Prompt
ai-rd-team run "实现 /users 和 /orders 两个 CRUD 端点"

# 另开一个终端
cat .ai-rd-team/runtime/adapter-intents/*.json \
  | python3 -c "import sys, json; print(json.load(sys.stdin).get('prompt', ''))" \
  | sed -n '/# Skills/,/# 记忆/p'
```

应看到 Prompt 的 `# Skills` 段里有你写的 `fastapi-routers` 内容。如果**没看到**：

| 问题 | 检查 |
|------|------|
| Skill 文件名和引用不一致 | 文件 `fastapi-routers.md`，引用就是 `"fastapi-routers"`（去 `.md`） |
| 配置写错级别 | `roles.developer.skills` 是数组；不是 `roles.skills.developer` |
| 文件没被 workspace 发现 | 必须在 `.ai-rd-team/skills/` 目录下（注意前面的点号） |
| 没重启 | 配置改动不热加载，需要重启 `ai-rd-team run` |

### 第 4 步：观察成员的行为

成员完成后，检查产出：

- ✅ `app/routers/users.py` 存在且有 `APIRouter(prefix="/users", tags=["users"])`
- ✅ `app/main.py` 用了 `app.include_router(...)`，没有直接 `@app.get`
- ✅ 所有路由函数都声明了 `response_model`

如果 Skill 写得够具体，**这些细节成员会自觉遵守**。如果 Skill 写得空洞（比如只写"用 APIRouter"没写示例和禁止），成员可能忽略。

---

## 真实能跑的示例

看 [examples/04-custom-skill/](../examples/04-custom-skill/)：Standard 档 + FastAPI + 2 份自定义 Skill（`fastapi-routers` + `team-python-style`），成员 spawn 后可以观察到自定义规则被遵守。

---

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
