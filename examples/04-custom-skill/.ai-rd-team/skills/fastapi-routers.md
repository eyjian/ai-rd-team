# fastapi-routers

## 适用场景

所有 FastAPI 项目的路由组织。在本项目中，**所有角色**（architect / developer / reviewer / tester）都需要理解这条约束。

## 核心原则

1. **每个业务域独立一个 `APIRouter`**，不把路由直接挂到 `FastAPI` 实例上
2. **Router 文件放在 `app/routers/<domain>.py`**，由 `app/main.py` 统一 `include_router`
3. **每个路由函数声明返回类型**（Pydantic model 或明确的 `dict[str, V]`）
4. **状态码显式写**：创建用 `status.HTTP_201_CREATED`，删除用 `status.HTTP_204_NO_CONTENT`

## 常用模式

### 推荐：APIRouter 模式

```python
# app/routers/todos.py
from fastapi import APIRouter, HTTPException, status

from app.schemas.todo import TodoIn, TodoOut
from app.services import todo_service

router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("", response_model=list[TodoOut])
async def list_todos() -> list[TodoOut]:
    return todo_service.list_all()


@router.post("", response_model=TodoOut, status_code=status.HTTP_201_CREATED)
async def create_todo(body: TodoIn) -> TodoOut:
    return todo_service.create(body)


@router.get("/{todo_id}", response_model=TodoOut)
async def get_todo(todo_id: int) -> TodoOut:
    todo = todo_service.find(todo_id)
    if todo is None:
        raise HTTPException(status_code=404, detail="todo not found")
    return todo
```

### 推荐：main.py 只负责注册

```python
# app/main.py
from fastapi import FastAPI

from app.routers import todos

app = FastAPI(title="Todo API")
app.include_router(todos.router)
```

## 禁止

- ❌ 在 `main.py` 里直接写 `@app.get("/todos")` 这样的路由
- ❌ 一个 router 文件塞多个业务域（例如 users + orders 混在同一个文件）
- ❌ 返回 `dict` 不声明 `response_model`（前端无法生成类型；OpenAPI schema 也不准确）
- ❌ 把 HTTPException 的 `status_code` 写成裸数字（应用 `status.HTTP_xxx`）

## 参考

- https://fastapi.tiangolo.com/tutorial/bigger-applications/
- https://fastapi.tiangolo.com/reference/status/
