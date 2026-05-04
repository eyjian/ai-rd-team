# 预期产出（验收用）

## 目录结构

```
.ai-rd-team/runtime/artifacts/
├── code/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # 只做 include_router
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   └── todos.py               # APIRouter + 5 个端点
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── todo.py                # TodoIn / TodoOut
│   │   └── services/
│   │       ├── __init__.py
│   │       └── todo_service.py        # 业务逻辑
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_routers_todos.py      # 5+ 用例（每个端点）
│   │   └── test_services.py           # 3+ 用例（业务函数）
│   ├── pyproject.toml
│   └── README.md（可选）
└── reports/
    └── report-developer.md（或 report-architect.md）
```

## 关键文件抽样

### `app/main.py`（应长什么样）

```python
from fastapi import FastAPI

from app.routers import todos

app = FastAPI(title="Todo API")
app.include_router(todos.router)
```

⚠️ **不应该**看到：
```python
# ❌ 违反 fastapi-routers.md
@app.get("/todos")
async def list_todos():
    ...
```

### `app/routers/todos.py`（应长什么样）

```python
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

# ... 其他端点
```

### `app/schemas/todo.py`（应长什么样）

```python
from pydantic import BaseModel


class TodoIn(BaseModel):
    title: str
    done: bool = False


class TodoOut(BaseModel):
    id: int
    title: str
    done: bool
```

## 验收命令

```bash
cd .ai-rd-team/runtime/artifacts/code

# 1. 装得上
pip install -e .

# 2. 测试全过
pytest -v

# 3. 能实际跑起来
uvicorn app.main:app --port 8000 &
curl -X POST http://localhost:8000/todos \
  -H "Content-Type: application/json" \
  -d '{"title": "write docs", "done": false}'
# 应返回 201 + TodoOut

curl http://localhost:8000/todos
# 应返回 [{"id": 1, "title": "write docs", "done": false}]

kill %1
```

## 自定义 Skill 落地验证

### ✅ fastapi-routers.md 生效

```bash
# main.py 里没有直接路由
grep -E "^@app\.(get|post|put|delete)" app/main.py
# → 应无输出

# routers/todos.py 用了 APIRouter
grep "APIRouter" app/routers/todos.py
# → router = APIRouter(prefix="/todos", tags=["todos"])

# 所有路由都有 response_model
grep -E "^@router\." app/routers/todos.py | grep -c "response_model"
# → 应 ≥ 4（DELETE 可能没有 response_model，返回 204）
```

### ✅ team-python-style.md 生效

```bash
# 没有 wildcard import
grep -rn "import \*" app/ tests/
# → 应无输出

# 所有 def 都有类型注解
grep -n "def " app/ -r | grep -v "->"
# → 应极少（只有少数 __init__ 等特殊情况）

# 单函数不超 30 行（粗略估算）
awk '/^def |^async def / { start=NR; name=$0 }
     /^$/ && start { if (NR-start > 30) print name" at line "start" is "NR-start" lines" }' \
  app/routers/todos.py app/services/todo_service.py
# → 应无输出
```

### ✅ Skill 被真实加载

```bash
# 在 Prompt 里能找到自定义 Skill 的内容关键词
cat .ai-rd-team/runtime/adapter-intents/*.json \
  | python3 -c "import sys, json; [print(json.loads(l).get('prompt', '')) for l in sys.stdin.read().split('\n') if l.strip()]" \
  | grep -c "APIRouter"
# → 应 ≥ 1（说明 fastapi-routers.md 内容进了 Prompt）

cat .ai-rd-team/runtime/adapter-intents/*.json \
  | python3 -c "import sys, json; [print(json.loads(l).get('prompt', '')) for l in sys.stdin.read().split('\n') if l.strip()]" \
  | grep -c "test_<对象>"
# → 应 ≥ 1（说明 team-python-style.md 内容进了 Prompt）
```

## 如果成员没遵守怎么办

这是 Skill 设计的常见迭代场景。调整方式：

1. **让约束更具体**：Skill 里加具体代码示例（正反对照）
2. **加禁止清单**：明确 `❌ 不要 X` 比 `✅ 要 Y` 更有效
3. **拆 Skill**：如果一个 Skill 管太多，拆成多个（每个 Skill 专注一件事）
4. **检查角色覆盖**：Skill 是否注入到了**所有产出代码的角色**？developer 有，reviewer 也要有
