# 需求：TodoList API（FastAPI + 团队编码规范）

## 目标

构建一个简单的 TodoList REST API 作为**演示自定义 Skill 落地**的载体。

## 功能清单

### 数据模型（Pydantic v2）

```python
class TodoIn(BaseModel):
    title: str
    done: bool = False

class TodoOut(BaseModel):
    id: int
    title: str
    done: bool
```

### 端点

| 方法 | 路径 | 行为 | 返回 |
|------|------|------|------|
| GET | `/todos` | 列出全部 | `list[TodoOut]` |
| POST | `/todos` | 新建（body: TodoIn） | `TodoOut`（201） |
| GET | `/todos/{id}` | 查单个 | `TodoOut`（404 如不存在） |
| PUT | `/todos/{id}` | 更新（body: TodoIn） | `TodoOut`（404 如不存在） |
| DELETE | `/todos/{id}` | 删除 | 204（404 如不存在） |

### 存储

**内存 dict 即可**：`dict[int, TodoOut]`。ID 用自增整数。**不要求持久化**（本 example 的重点是代码结构，不是持久化）。

## 非功能要求

### 必须遵守的约束（来自自定义 Skill）

**fastapi-routers.md 约束**：

- 所有路由定义在 `app/routers/todos.py` 里的 `APIRouter(prefix="/todos", tags=["todos"])` 上
- `app/main.py` 只做 `FastAPI()` + `app.include_router(todos.router)`，**禁止**在 main.py 直接写 `@app.get`
- 所有路由函数声明 `response_model`

**team-python-style.md 约束**：

- 所有 import **列名**（禁止 `from x import *`）
- public 函数/方法必须有类型注解（参数 + 返回值）
- 单个函数 ≤ 30 行（长就拆）
- 测试函数名：`test_<对象>_<场景>_<期望>`，如 `test_create_todo_with_valid_body_returns_201`

### 代码组织

- `app/main.py` — FastAPI 实例 + 路由注册
- `app/routers/todos.py` — todos 路由（仅 HTTP 层）
- `app/schemas/todo.py` — Pydantic models
- `app/services/todo_service.py` — 业务逻辑（纯函数优先，接收 store 参数而非 import 全局）
- `tests/test_routers_todos.py` — 用 FastAPI TestClient 测每个端点
- `tests/test_services.py` — 纯单测业务函数
- `pyproject.toml` — 可 `pip install -e .` 的配置

## 成功标准

1. `pip install -e .` 成功
2. `pytest` 全过，至少 8 个测试用例
3. 通过上述"必须遵守的约束"人工检查
