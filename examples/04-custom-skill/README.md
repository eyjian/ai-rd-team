# 示例 04：自定义 Skill 示例（FastAPI + 团队 Python 规范）

**档位**：Standard
**技术栈**：Python 3.10+ / FastAPI 0.110+ / Pydantic v2 / pytest
**预计 RP**：~300
**预计时长**：10-15 分钟

## 这个 example 的特殊之处

前 3 个 example（01/02/03）都只用 **builtin Skills**（python-best-practices / pytest-guide / go-kratos-basics 等），展示"装包 → 引用 → 跑"的最小链路。

**本 example 的目标不同**：演示**如何写 + 引用 + 验证自定义 Skill**。

你会看到：

- 两份自定义 Skill 放在 `.ai-rd-team/skills/` 目录下
- `config.advanced.yaml` 里 `roles.<name>.skills` 混合引用 `builtin:xxx` 和自定义名字
- 成员产出的代码**确实遵守**自定义 Skill 里写的规则（自定义约束被强制落地）

这是你**为公司编码规范 / 项目专有约束落地到 AI 团队的参考模板**。

## 目标产出

一个 FastAPI 项目 `todo-api`，支持：

- `GET /todos` — 列出所有 todo
- `POST /todos` — 新建（body: `{"title": "...", "done": false}`）
- `GET /todos/{id}` — 查单个
- `PUT /todos/{id}` — 更新
- `DELETE /todos/{id}` — 删除

数据存内存即可（dict），**不要求持久化**，重点在代码结构。

## 预期文件树（成员产出后）

```
.ai-rd-team/runtime/artifacts/
├── code/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # 只做 FastAPI + include_router，不直接 @app.get
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   └── todos.py         # APIRouter(prefix="/todos", tags=["todos"])
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── todo.py          # Pydantic v2 BaseModel
│   │   └── services/
│   │       ├── __init__.py
│   │       └── todo_service.py  # 业务逻辑（纯函数优先）
│   ├── tests/
│   │   ├── test_routers_todos.py  # 使用 TestClient
│   │   └── test_services.py       # 单测业务逻辑
│   └── pyproject.toml
└── reports/
    └── report-developer.md
```

## 两份自定义 Skill 各约束什么

| Skill 文件 | 约束内容 | 预期在产出中看到 |
|-----------|---------|----------------|
| `skills/fastapi-routers.md` | 每个域一个 `APIRouter`，不直接挂 `FastAPI` | `app/routers/todos.py` 用 `APIRouter`；`main.py` 用 `include_router` |
| `skills/team-python-style.md` | 单函数 ≤ 30 行；禁 `from x import *`；必须 type hints；测试命名 | 每个函数短小；所有 import 列名；所有 public 函数有类型注解 |

## 如何运行

```bash
cp -r examples/04-custom-skill ~/demo-custom-skill
cd ~/demo-custom-skill

# 启动 Web 面板（可选）
ai-rd-team serve --port 8765 &

# 在 CodeBuddy 会话中运行
ai-rd-team run "$(cat REQUIREMENT.md)"
```

## 成功验收

运行完成后：

```bash
cd .ai-rd-team/runtime/artifacts/code
pip install -e .
pytest
```

**pytest 全过**是基础。**重点观察自定义 Skill 是否起作用**：

### 验收清单

1. **fastapi-routers.md 生效**
   - [ ] `app/main.py` 里 **没有** `@app.get(...)` 这样的直接路由
   - [ ] `app/routers/todos.py` 用 `APIRouter(prefix="/todos", tags=["todos"])`
   - [ ] 所有路由函数声明了 `response_model`

2. **team-python-style.md 生效**
   - [ ] 所有 import 都列名（**没有** `from x import *`）
   - [ ] 所有 public 函数有类型注解（参数 + 返回值）
   - [ ] 没有单个函数超过 30 行

3. **Skill 被真实加载**（自证）

   ```bash
   cat .ai-rd-team/runtime/adapter-intents/*.json \
     | python3 -c "import sys, json, glob; \
                   [print(f, json.load(open(f)).get('prompt', '')[:500]) for f in glob.glob('.ai-rd-team/runtime/adapter-intents/*.json')]"
   ```

   在 developer 或 reviewer 的 Prompt 里应看到 `# Skills` 段包含你的自定义 Skill 内容。

## 可能遇到的问题

### 自定义 Skill 没被加载

**症状**：产出的代码没遵守自定义约束。

**排查**：

| 检查 | 怎么验证 |
|------|---------|
| Skill 文件名和 config 引用是否一致？ | 文件 `skills/fastapi-routers.md`，config 写 `"fastapi-routers"`（不带 `.md`） |
| Skill 目录位置对不对？ | 必须在 `<workspace>/.ai-rd-team/skills/`（前面有点号） |
| config.advanced.yaml 语法对不对？ | 跑 `ai-rd-team config validate` 看是否报错 |
| 有没有重启 run？ | 配置改动不热加载，需要重启 `ai-rd-team run` |

### Skill 被加载但成员不遵守

**可能原因**：Skill 写得不够具体。

- 只写"要用 APIRouter"没用 → 要写**正面示例代码**
- 没有"禁止"清单 → 要显式列出 `❌ 不要在 main.py 里 @app.get`

详见 `docs/04-skills.md` 的「让 Skill 真正影响成员」节。

## 相关文档

- [docs/04-skills.md](../../docs/04-skills.md) — Skills 体系完整指南 + 内联 walkthrough
- [docs/02-configuration.md](../../docs/02-configuration.md) — config.advanced.yaml 完整字段
- [docs/03-roles-and-team.md](../../docs/03-roles-and-team.md) — 角色和 Skills 的关系
