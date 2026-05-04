# 接口契约

## REST 端点

### `GET /todos`

- 请求：无 body，无 query
- 响应：`200 OK`，`list[TodoOut]`
- 空列表时返回 `[]`（不是 404）

### `POST /todos`

- 请求 body：`TodoIn { title: str, done: bool = false }`
- 响应：`201 Created`，`TodoOut`
- `title` 为空字符串时返回 `422`（Pydantic 默认行为即可）

### `GET /todos/{id}`

- 路径参数 `id: int`
- 响应：`200 OK` + `TodoOut`，或 `404 Not Found` + `{"detail": "todo not found"}`

### `PUT /todos/{id}`

- 路径参数 `id: int`；body 同 POST
- 响应：`200 OK` + `TodoOut`（全量替换），或 `404`
- PUT 语义是替换，不是部分更新（部分更新需要 PATCH，但本 API 不实现）

### `DELETE /todos/{id}`

- 响应：`204 No Content`（body 为空），或 `404`

## 数据模型

```python
class TodoIn(BaseModel):
    title: str
    done: bool = False

class TodoOut(BaseModel):
    id: int         # 自增整数
    title: str
    done: bool
```

## 错误响应格式

统一用 FastAPI 默认的 `HTTPException`：

```json
{"detail": "错误描述"}
```

## 业务约束

- **ID 生成**：自增整数（`max(store.keys(), default=0) + 1`），不用 UUID
- **并发**：单进程内存 dict，不考虑多进程/多线程并发
- **容量**：不限制 todo 数量（测试用 < 100 条即可）
