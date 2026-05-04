# ai-rd-team 详细设计 - 03 服务层（REST API）

> 文档版本：v1.0
> 日期：2026-05-04
> 颗粒度：架构级
> 依赖：`00-overview.md`、`01-engine.md`、`11-runtime-protocol.md`

---

## 1. 目的与范围

### 1.1 目的
定义 Web 面板（和未来其他表现层）与引擎交互的 **REST API + SSE** 接口。服务层是一个**薄壳**——不处理业务逻辑，只暴露引擎能力和 runtime 文件。

### 1.2 范围
- REST API 端点清单
- SSE 实时事件通道
- 身份认证（第一期可选）
- 错误码
- 接口版本管理

### 1.3 非目标
- ❌ 前端交互细节（见 `04-web-panel.md`）
- ❌ WebSocket 实现（第一期用 SSE 足够）

---

## 2. 技术选型

| 项 | 选型 | 理由 |
|----|------|------|
| Web 框架 | Flask 3.x | 轻量，Python 生态成熟 |
| 实时推送 | SSE（Server-Sent Events） | 比 WebSocket 简单，浏览器原生支持 |
| 序列化 | JSON | Web 标准 |
| API 风格 | REST + 资源导向 | 易理解 |
| 身份验证（第一期） | 本机访问（127.0.0.1）默认无需 token | 降低门槛 |
| 身份验证（可选） | Bearer Token（config.web.auth.token） | 远程访问场景 |

---

## 3. API 端点总览

### 3.1 运行控制

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/run/start` | 启动运行 |
| POST | `/api/run/pause` | 暂停 |
| POST | `/api/run/resume` | 恢复 |
| POST | `/api/run/stop` | 停止 |
| POST | `/api/run/escalate` | 升档 |
| GET | `/api/run/current` | 当前运行状态 |
| GET | `/api/run/history` | 历史运行列表 |
| GET | `/api/run/{run_id}` | 历史运行详情 |

### 3.2 团队与成员

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/team/state` | 团队整体状态 |
| GET | `/api/team/members` | 成员列表 |
| GET | `/api/team/members/{id}` | 某成员详情 |
| POST | `/api/team/members/{id}/message` | 向某成员发消息（用户视角） |
| GET | `/api/team/messages` | 消息流（分页） |
| GET | `/api/team/roster` | 名册 |

### 3.3 制品

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/artifacts` | 所有制品列表（含 manifest） |
| GET | `/api/artifacts/{category}` | 按类别列出（design/code/...） |
| GET | `/api/artifacts/file?path=...` | 获取文件内容（含 Markdown） |
| GET | `/api/artifacts/tree` | 树形目录结构 |
| GET | `/api/artifacts/manifest` | delivery manifest |

### 3.4 记忆

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/memory/agent-d` | agent.d 文件列表 |
| GET | `/api/memory/memory-d/tree` | memory.d 树形结构 |
| GET | `/api/memory/decisions` | ADR 列表 |
| GET | `/api/memory/file?path=...` | 读取某 memory 文件 |
| PUT | `/api/memory/file?path=...` | 更新 memory 文件 |

### 3.5 成本

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/cost/snapshot` | 当前 Resource Points 快照 |
| GET | `/api/cost/quota` | 当前日/周/月额度情况 |
| GET | `/api/cost/history` | 历史运行成本 |
| POST | `/api/cost/record-actual` | 用户填入真实消耗 |
| POST | `/api/cost/model-switched` | 用户确认已切换模型 |
| POST | `/api/cost/expand-budget` | 追加预算 |

### 3.6 配置

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/config/basic` | 获取 Basic 层配置 |
| PUT | `/api/config/basic` | 更新 Basic 层 |
| GET | `/api/config/advanced` | 获取 Advanced 层 |
| PUT | `/api/config/advanced` | 更新 Advanced 层 |
| GET | `/api/config/effective` | 获取 EffectiveConfig |
| GET | `/api/config/source?key=...` | 查询某字段来源 |
| POST | `/api/config/validate` | 校验配置（不保存） |

### 3.7 Hook & 安全

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/hooks` | 已注册 Hook 列表 |
| POST | `/api/hooks/{name}/test` | 测试触发某 Hook |

### 3.8 Skills

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/skills` | 所有可用 Skills（按 scope 分组） |
| GET | `/api/skills/file?scope=...&name=...` | 读取 Skill 内容 |
| PUT | `/api/skills/file?scope=workspace&name=...` | 保存 Skill（仅 workspace） |

### 3.9 实时流

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/stream/events` | SSE 事件流（全局） |
| GET | `/api/stream/member/{id}` | SSE 某成员状态流 |
| GET | `/api/stream/cost` | SSE 成本实时更新 |

### 3.10 元信息

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/version` | API 和系统版本 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/adapter/capabilities` | 当前 Adapter 能力 |

---

## 4. 典型请求响应示例

### 4.1 启动运行

**请求**：

```http
POST /api/run/start
Content-Type: application/json

{
  "requirement": "实现一个用户管理模块",
  "mode": "standard"
}
```

**响应**：

```json
{
  "run_id": "abc12345",
  "status": "running",
  "started_at": "2026-05-04T10:00:00Z",
  "mode": "standard",
  "members": [
    {"member_id": "architect", "role": "architect", "display_name": "陈架构"},
    {"member_id": "developer_1", "role": "developer", "display_name": "林1号"}
  ]
}
```

### 4.2 发消息给成员

```http
POST /api/team/members/architect/message
Content-Type: application/json

{
  "content": "请再考虑一下移动端兼容性",
  "summary": "补充需求"
}
```

响应：

```json
{"message_id": "msg-xyz789", "delivered": true}
```

实际：API 写入 `runtime/commands/pending/message-to-architect-{ts}.json`，引擎处理后通过 Adapter 发出。

### 4.3 获取实时成本

```http
GET /api/cost/snapshot
```

```json
{
  "run_id": "abc12345",
  "mode": "standard",
  "resource_points_used": 285,
  "resource_points_budget": 400,
  "progress": 0.71,
  "quota": {
    "day": {"used": 1200, "limit": 2000, "remaining": 800},
    "week": {"used": 4500, "limit": 10000, "remaining": 5500},
    "month": {"used": 18000, "limit": 30000, "remaining": 12000}
  },
  "breakdown": {
    "member_spawns": 5,
    "messages": 87,
    "broadcasts": 0,
    "runtime_minutes": 35.5,
    "iterations": 4
  },
  "estimated_cost": {
    "currency": "CNY",
    "value": 5.70,
    "note": "粗估"
  }
}
```

### 4.4 SSE 订阅事件

```http
GET /api/stream/events
Accept: text/event-stream
```

响应（持续推送）：

```
event: member_status_changed
data: {"member_id":"developer_1","from":"idle","to":"working"}

event: artifact_written
data: {"producer":"architect","path":"artifacts/design/spec-architecture.md"}

event: budget_threshold_reached
data: {"threshold":0.75,"rp":300}

event: cost_snapshot
data: {"resource_points_used":310,"progress":0.78}
```

---

## 5. 实现架构

### 5.1 Flask 应用结构

```
ai_rd_team/service/
├── app.py                   # Flask app factory
├── blueprints/
│   ├── run.py               # /api/run/*
│   ├── team.py              # /api/team/*
│   ├── artifacts.py         # /api/artifacts/*
│   ├── memory.py            # /api/memory/*
│   ├── cost.py              # /api/cost/*
│   ├── config.py            # /api/config/*
│   ├── skills.py            # /api/skills/*
│   ├── hooks.py             # /api/hooks/*
│   └── stream.py            # /api/stream/*
├── middleware/
│   ├── auth.py
│   ├── error_handler.py
│   └── cors.py
├── sse.py                    # SSE 抽象
└── engine_proxy.py           # 引擎访问代理（依赖注入）
```

### 5.2 引擎代理

所有业务接口通过 `EngineProxy` 访问引擎：

```python
class EngineProxy:
    """Web API 到 Engine 的代理层。
    
    职责：
    - 单例管理（一个 Web 应用对应一个 Engine）
    - 线程安全（Flask 多请求）
    - 统一错误转换
    """
    
    def __init__(self, engine: TeamEnvironmentManager):
        self.engine = engine
        self._lock = threading.RLock()
    
    def start_run(self, requirement: str, mode: str) -> dict:
        with self._lock:
            ctx = self.engine.start_run(requirement=requirement, run_mode=mode)
            return self._ctx_to_dict(ctx)
    
    # ... 其他方法
```

### 5.3 读取与命令分离

两类 API 的实现方式不同：

- **读取类**（GET）：直接读 `runtime/` 文件返回，**不经过引擎**
  - 优点：零耦合 + 高并发
  - 例：`/api/team/state` 直接读 `state/team.yaml`

- **命令类**（POST/PUT/DELETE）：写入 `commands/pending/` 让引擎处理
  - 优点：异步、可审计、断电安全
  - 例：`/api/run/pause` 写入 `commands/pending/pause-{ts}.json`

这种分离让 Web 服务可以独立于引擎进程运行（只要共享文件系统）。

---

## 6. SSE 实现

### 6.1 事件源

SSE 的数据来自 `runtime/events.jsonl`，通过 FileWatcher 感知新事件：

```python
def stream_events():
    """SSE 生成器。"""
    watcher = FileWatcher(runtime_dir / "events.jsonl")
    for event in watcher.follow():
        yield f"event: {event['event']}\n"
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
```

### 6.2 心跳

每 30 秒发送一条 keep-alive 注释：

```
: keep-alive

```

### 6.3 断线重连

浏览器 EventSource 自动重连。服务端支持 `Last-Event-ID` header 从断点续传（基于 events.jsonl 的行号）。

---

## 7. 错误码

### 7.1 HTTP 状态码使用

| 状态 | 含义 |
|------|------|
| 200 | 成功 |
| 201 | 创建成功（如 start_run） |
| 202 | 已接受，异步处理中（如 pause/resume） |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 禁止（如 config.security 限制） |
| 404 | 资源不存在 |
| 409 | 状态冲突（如 run 已在运行中） |
| 422 | 业务校验失败（如 escalate 不允许降档） |
| 500 | 服务端错误 |
| 503 | 服务不可用（引擎初始化中） |

### 7.2 统一错误响应

```json
{
  "error": {
    "code": "RUN_ALREADY_RUNNING",
    "message": "Another run is in progress",
    "details": {"current_run_id": "abc12345"},
    "ts": "2026-05-04T10:00:00Z"
  }
}
```

### 7.3 业务错误码

| code | 说明 |
|------|------|
| `RUN_ALREADY_RUNNING` | 已有运行中 |
| `RUN_NOT_FOUND` | 指定运行不存在 |
| `MODE_ESCALATION_INVALID` | 降档或非法升档 |
| `BUDGET_EXCEEDED` | 预算已用完 |
| `QUOTA_EXCEEDED` | 额度已用完 |
| `ADAPTER_UNAVAILABLE` | Adapter 未初始化 |
| `MEMBER_NOT_FOUND` | 成员不存在 |
| `CONFIG_VALIDATION_FAILED` | 配置校验失败 |
| `ARTIFACT_NOT_FOUND` | 制品不存在 |
| `FORBIDDEN_PATH` | 路径访问被安全规则拒绝 |

---

## 8. 身份认证（第一期可选）

### 8.1 默认策略

- `web.host=127.0.0.1`（默认）→ **无需认证**
- `web.host!=127.0.0.1` → **强制 Token 认证**

### 8.2 Token 认证

```yaml
# config.yaml (Advanced 层)
web:
  host: "0.0.0.0"
  auth:
    enabled: true
    token: "${ENV_VAR_TOKEN}"  # 从环境变量读取
```

请求：

```http
GET /api/run/current
Authorization: Bearer xxx-yyy-zzz
```

### 8.3 防护措施

- 全局限流（默认每 IP 每秒 10 个请求）
- 路径校验（防路径穿越）
- CORS 默认关闭（同源）

---

## 9. 接口版本管理

### 9.1 URL 前缀

第一期不加版本前缀（`/api/...`）。当出现不兼容变更时引入 `/api/v2/...`。

### 9.2 字段演进规则

- 新增字段：允许（向前兼容）
- 删除字段：不允许（废弃 → 保留 6 个版本 → 删除）
- 修改字段类型：不允许
- 修改字段含义：不允许

---

## 10. OpenAPI 规范

第一期产出 `docs/openapi.yaml`，包含：
- 所有端点的请求/响应 Schema
- 错误码定义
- 示例

用 Swagger UI 托管：`http://127.0.0.1:8765/api/docs`。

---

## 11. 验收标准

- ✅ 所有端点按本文档定义可用
- ✅ 读取类 API 直接读 runtime/ 文件（不经引擎）
- ✅ 命令类 API 通过 commands/pending/ 异步处理
- ✅ SSE 事件流稳定（≥ 1 小时无断线）
- ✅ 错误码统一响应格式
- ✅ 本机访问无需认证，远程访问强制 Token
- ✅ OpenAPI 文档完整
- ✅ 集成测试：启动 → 观察 SSE → 暂停 → 恢复 → 停止

---

## 12. 对其他文档的接口

| 使用方 | 接口 |
|-------|-----|
| `01-engine.md` | EngineProxy 调用 engine.start_run / pause / stop 等 |
| `04-web-panel.md` | 前端调用本文档定义的所有 API |
| `10-config-schema.md` | `/api/config/*` 调用 ConfigLoader 的 load_basic/load_advanced |
| `11-runtime-protocol.md` | 读取 state/ messages/ events.jsonl；写入 commands/pending/ |
