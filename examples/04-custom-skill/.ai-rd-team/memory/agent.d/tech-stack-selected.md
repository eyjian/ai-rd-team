# 技术栈

## 后端

- **Python 3.10+**（用 `list[int]` / `X | None` 新语法；禁用 `typing.List` 老写法）
- **FastAPI 0.110+**（路由 + 请求验证）
- **Pydantic v2**（所有 schema 用 `BaseModel`）
- **Uvicorn**（开发期启动：`uvicorn app.main:app --reload`）

## 测试

- **pytest 8.x**（基础框架）
- **httpx**（FastAPI TestClient 的依赖；已在 fastapi 装 "[test]" extras 时带入）

## 存储

**内存 dict**，不要求持久化。类型：`dict[int, TodoOut]`。

## 打包

- `pyproject.toml` + hatchling（与本项目主仓风格一致）
- `[project]` 声明 `name="todo-api"`, `version="0.1.0"`
- `[project.optional-dependencies].dev = ["pytest>=8.0"]`

## 不用的东西（明确排除）

- ❌ 不用数据库（SQLAlchemy / SQLModel / tortoise）
- ❌ 不用 auth（JWT / OAuth）
- ❌ 不用 async ORM（纯同步内存操作即可）
- ❌ 不用 Docker / K8s 配置
