# BlogAPI 系统设计（spec-design）

> Owner: architect（陈架构）
> Stack: Go 1.21 + go-kratos v2 + PostgreSQL 15 + GORM + JWT + wire
> Module name: `blog`

---

## 1. 目标与范围

构建一个博客后端服务 BlogAPI，提供：

- 用户：注册、登录（JWT）、获取当前用户
- 文章：CRUD、分页 + 标签过滤、点赞（幂等）
- 评论：发表、列表（按文章）

非目标（本期不做）：富文本渲染、图片上传、关注关系、通知、管理后台。

---

## 2. 架构总览

采用 Kratos 推荐的分层架构，依赖方向 **从外向内，内层不感知外层**：

```
 ┌──────────────────────────────────────────────────┐
 │ transport (HTTP + gRPC, by proto)                │
 │                                                  │
 │   api/blog/v1/*.proto  ──生成──>  *.pb.go        │
 └────────────────────────┬─────────────────────────┘
                          │
 ┌────────────────────────▼─────────────────────────┐
 │ service/ （协议层）                               │
 │   - 把 proto 请求映射到 biz                      │
 │   - 不写业务逻辑                                 │
 └────────────────────────┬─────────────────────────┘
                          │
 ┌────────────────────────▼─────────────────────────┐
 │ biz/ （业务逻辑）                                 │
 │   - UserUsecase / PostUsecase / CommentUsecase   │
 │   - 只依赖 *Repo 接口                            │
 └────────────────────────┬─────────────────────────┘
                          │
 ┌────────────────────────▼─────────────────────────┐
 │ data/ （存储实现）                                │
 │   - userRepo / postRepo / commentRepo            │
 │   - GORM + PostgreSQL                            │
 └──────────────────────────────────────────────────┘
```

- **biz 接口、data 实现**：`biz` 定义 `UserRepo / PostRepo / CommentRepo` 接口，`data` 提供实现，`wire` 在装配阶段绑定。
- **依赖注入**：使用 `google/wire`，禁止全局变量和 `init()` 副作用。
- **配置**：`configs/config.yaml` 由 `internal/conf/conf.pb.go`（proto 生成）反序列化，支持环境变量覆盖。

---

## 3. 目录结构

```
prototype/M4-example2-e2e/.ai-rd-team/runtime/artifacts/code/
├── Makefile
├── go.mod                             # module blog
├── go.sum
├── buf.gen.yaml
├── api/
│   ├── buf.yaml
│   └── blog/v1/
│       ├── common.proto
│       ├── user.proto
│       ├── post.proto
│       ├── comment.proto
│       ├── common.pb.go               # 手写版，免去 protoc
│       ├── user.pb.go
│       ├── post.pb.go
│       └── comment.pb.go
├── configs/
│   ├── config.yaml
│   └── schema.sql
├── cmd/server/
│   ├── main.go
│   ├── wire.go                        # +build wireinject
│   └── wire_gen.go
└── internal/
    ├── conf/
    │   ├── conf.proto
    │   └── conf.pb.go
    ├── biz/
    │   ├── biz.go                     # ProviderSet
    │   ├── user.go
    │   ├── post.go
    │   └── comment.go
    ├── data/
    │   ├── data.go                    # ProviderSet + *gorm.DB
    │   ├── user.go
    │   ├── post.go
    │   └── comment.go
    ├── service/
    │   ├── service.go                 # ProviderSet
    │   ├── user.go
    │   ├── post.go
    │   └── comment.go
    ├── server/
    │   ├── server.go                  # ProviderSet
    │   ├── http.go
    │   └── grpc.go
    └── pkg/
        ├── auth/                      # JWT 工具 + middleware
        └── password/                  # bcrypt 封装
```

---

## 4. 模块职责

### 4.1 `api/blog/v1`（契约层）
- 定义 `UserService / PostService / CommentService` 的 proto。
- 生成（或手写）对应 `*.pb.go`，对外暴露 `UnimplementedXxxServer` + HTTP 路由注册函数。
- **约束**：只定义协议，不放业务。

### 4.2 `internal/service`（协议适配）
- 实现 proto 定义的 gRPC interface，HTTP 通过同一实现自动暴露。
- 调用 `biz.*Usecase`，把 biz 的领域模型映射回 `*.pb.go` 的 Response。
- 负责从 context 提取 JWT 中的 `user_id`（通过中间件注入）。

### 4.3 `internal/biz`（业务核心）
- 定义领域模型 `User / Post / Comment`（纯结构体，无 GORM tag）。
- 定义 `UserRepo / PostRepo / CommentRepo` 接口，字段语义锁定在 biz 侧。
- Usecase 组合 Repo + 业务规则（权限、幂等、校验）。

### 4.4 `internal/data`（持久化）
- `Data` 结构体持有 `*gorm.DB`；`NewData(c *conf.Data) (*Data, cleanup, error)` 负责建立连接池。
- 每个 Repo 内部定义 PO（GORM 模型）并在返回前映射为 biz 领域模型。
- **禁止**把 PO 泄漏到 biz 层。

### 4.5 `internal/server`
- `NewHTTPServer` / `NewGRPCServer` 装配 middleware（recovery / logging / jwt / validate）。
- 通过 proto 生成的 `Registerxxx` 函数把 service 绑定到 transport。

### 4.6 `cmd/server`
- `main.go` 读取 config → 调用 `wireApp` → `kratos.New().Run()`。
- `wire.go` 声明 ProviderSet；`wire_gen.go` 为 wire 生成产物（允许手写，保持幂等）。

---

## 5. 关键横切关注

### 5.1 认证
- 注册：`POST /v1/users`，bcrypt 散列密码。
- 登录：`POST /v1/auth/login`，成功返回 JWT（HS256，claim: `sub=user_id`, `exp=24h`）。
- 鉴权中间件：`internal/pkg/auth.JWTAuth(secret)`，把 `user_id` 注入 context；受保护路由通过 `selector.Server` 白名单放行 `/v1/users` 和 `/v1/auth/login` 以及 `GET /v1/posts*`。

### 5.2 错误模型
统一使用 `github.com/go-kratos/kratos/v2/errors`：

| reason                | HTTP | 场景                       |
| --------------------- | ---- | -------------------------- |
| `USER_EMAIL_EXISTS`   | 409  | 注册时邮箱已存在           |
| `USER_NOT_FOUND`      | 404  | 用户不存在                 |
| `INVALID_CREDENTIALS` | 401  | 登录密码错误               |
| `UNAUTHORIZED`        | 401  | 无 token 或过期            |
| `FORBIDDEN`           | 403  | 非作者操作他人文章         |
| `POST_NOT_FOUND`      | 404  | 文章不存在                 |
| `COMMENT_NOT_FOUND`   | 404  | 评论不存在                 |
| `VALIDATION_FAILED`   | 400  | 参数非法                   |

### 5.3 幂等
- `POST /v1/posts/:id/like`：DB 主键 `(post_id, user_id)`，`ON CONFLICT DO NOTHING` + 事务内 `UPDATE posts SET likes_count = likes_count + 1 WHERE changed`。
- `DELETE /v1/posts/:id/like`：`DELETE WHERE` 返回影响行数决定是否 `likes_count -= 1`。

### 5.4 事务
- 涉及点赞计数、文章删除级联评论场景统一通过 `data.Transaction(ctx, func(txCtx) error)` 封装，Repo 在 `txCtx` 中取同一 `*gorm.DB`。

### 5.5 配置
`configs/config.yaml`：

```yaml
server:
  http: { addr: "0.0.0.0:8000", timeout: "10s" }
  grpc: { addr: "0.0.0.0:9000", timeout: "10s" }
data:
  database:
    driver: "postgres"
    source: "postgres://blog:blog@localhost:5432/blog?sslmode=disable"
  log_level: "info"
auth:
  jwt_secret: "change-me-in-prod"
  access_ttl: "24h"
```

对应 proto：`internal/conf/conf.proto` 定义 `Bootstrap{ Server, Data, Auth }`。

---

## 6. 数据库 schema（最终版）

与 team-lead 提供的 memory 基本一致，做了以下细化：

- `users.email` 强制 `CITEXT`（大小写无关），否则等价邮箱会重复；本期先用 `VARCHAR` + 入库前 `lower()`。
- `posts.tags` 使用 `TEXT[] + GIN 索引`，搜索 `WHERE $1 = ANY(tags)`。
- `comments` 增加 `ON DELETE CASCADE` 保证文章删除时自动清理。
- `post_likes` 使用联合主键保证幂等。

SQL 见 `configs/schema.sql`（由 developer_1 落盘）。

---

## 7. 测试策略（tester 接入点）

- **单元测试**：`biz/*_test.go` 使用 mock 的 Repo 接口（`gomock` 或手写 stub）。
- **集成测试**：`internal/data/*_test.go` 通过 `testcontainers-go` 起 Postgres 15。
- **契约测试**：针对 HTTP API 提供 `tests/e2e/`（可由 tester 用 `httptest` 或 `resty` 编写）。
- 命令：`go test ./... -race -cover`。

---

## 8. 风险 & 未决项

| 项 | 风险 | 方案 |
|----|------|------|
| proto 生成 | 环境可能缺 `protoc` | 提供**手写版** `*.pb.go`，保持最小结构体/方法即可编译 |
| wire 生成 | 可能缺 wire CLI | `wire_gen.go` 手写落盘 |
| bcrypt 成本 | 默认 cost=10 单测慢 | 测试环境设 `cost=4` |
| tags 数组 | SQLite 兼容问题 | 只承诺 Postgres 15，不支持 sqlite |

---

## 9. 分工（与 developer_1 / developer_2 / tester 协作）

| Owner        | 产出                                                                          |
| ------------ | ----------------------------------------------------------------------------- |
| architect    | `spec-design.md`、`data-interfaces.yaml`、`go.mod`、`api/blog/v1/*.pb.go`（含 proto 源） |
| developer_1  | `internal/biz/*.go`、`internal/data/*.go`、`configs/schema.sql`、`internal/pkg/password`           |
| developer_2  | `internal/conf/conf.pb.go`、`internal/server/*.go`、`internal/service/*.go`、`cmd/server/{main,wire,wire_gen}.go`、`Makefile`、`configs/config.yaml`、`internal/pkg/auth` |
| tester       | `tests/e2e/*_test.go`、`internal/biz/*_test.go` 示例、`README` 测试章节                     |

所有人对外契约**锁定**在 `data-interfaces.yaml` 和 proto 文件。
