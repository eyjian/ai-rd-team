# team-python-style

## 适用场景

本团队所有 Python 代码（含测试），覆盖命名 / import / 函数粒度 / 类型注解四个维度。

## 核心原则

1. **函数短小**：单个函数 ≤ 30 行，超过就拆分
2. **类型注解完备**：所有 public 函数声明参数和返回值类型
3. **import 明确**：列名导入，禁止 wildcard
4. **测试命名有格式**：`test_<对象>_<场景>_<期望>`

## 常用模式

### 类型注解

```python
def find_todo(todo_id: int) -> TodoOut | None:
    return _store.get(todo_id)


def create_todo(body: TodoIn, store: dict[int, TodoOut]) -> TodoOut:
    new_id = max(store.keys(), default=0) + 1
    todo = TodoOut(id=new_id, title=body.title, done=body.done)
    store[new_id] = todo
    return todo
```

### 测试命名

```python
# 推荐
def test_create_todo_with_valid_body_returns_201() -> None: ...
def test_get_todo_when_not_found_returns_404() -> None: ...
def test_list_todos_when_empty_returns_empty_list() -> None: ...

# ❌ 不推荐
def test_create() -> None: ...        # 没场景
def test_it_works() -> None: ...      # 没语义
def test_1() -> None: ...             # 没信息量
```

### 拆分长函数

```python
# ❌ 坏：50 行塞在一个函数里
async def create_todo(body: TodoIn) -> TodoOut:
    # 验证
    if not body.title.strip(): ...
    # 生成 ID
    ...
    # 持久化
    ...
    # 记日志
    ...
    return todo

# ✅ 好：拆成短小的责任明确的函数
async def create_todo(body: TodoIn) -> TodoOut:
    _validate(body)
    new_id = _next_id()
    todo = _build_todo(new_id, body)
    _persist(todo)
    return todo
```

## 禁止

- ❌ `from some_module import *`（永远列名导入）
- ❌ 省略返回类型（`def foo():` 至少写 `-> None`）
- ❌ 测试用 `def test_1()` / `def test_it()` 这种无信息名字
- ❌ 单个函数超过 30 行（Hard limit：超了就 refactor）
- ❌ 在公共函数里用 `*args, **kwargs` 代替显式参数（除非确实需要透传）

## 参考

- [PEP 8](https://peps.python.org/pep-0008/)
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
