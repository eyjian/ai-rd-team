# BlogAPI 架构设计

> 作者：陈架构（architect）
> 最后更新：2026-05-04
> 档位：standard（architect + dev × 2 + tester）

---

## 1. 目标与范围

基于 Go + Kratos v2 构建博客系统后端 REST API，核心能力：
- 用户注册 / 登录（JWT 7 天）
- 文章 CRUD + 分页（可按 tag 过滤）
- 评论、点赞（幂等）

**非目标**：前端、文章搜索（ES）、邮件、图片上传。

---

## 2. 技术栈与核心约束

| 项           | 选型                                            |
| ------------ | ----------------------------------------------- |
| 语言         | Go 1.21+                                        |
| 框架         | go-kratos v2（标准 layout）                     |
| ORM          | GORM（PostgreSQL 15）                           |
| 协议         | proto 定义（gRPC + HTTP 由 proto 生成）         |
| 认证         | `kratos/middleware/auth/jwt`（HS256，7 天）     |
| 依赖注入     | wire                                            |
| 密码哈希     | `golang.org/x/crypto/bcrypt`（cost=10）         |
| 集成测试     | testcontainers-go（启动真实 PostgreSQL 容器）   |
| 配置         | Kratos conf.proto + config.yaml                 |
| 错误         | `github.com/go-kratos/kratos/v2/errors`         |

**硬约束（必须遵守）**：
- biz 层**不允许** import `gorm.io/gorm` 或 `github.com/go-kratos/kratos/v2/transport`
- service 层**只做** proto ↔ biz DTO 转换和参数校验，不写业务逻辑
- **不手写 HTTP handler**，全部由 `protoc-gen-go-http` 生成
- 每个公共函数带 godoc 注释，错误路径必须有测试覆盖

---

## 3. Kratos 标准分层

```
artifacts/code/
├── api/blog/v1/
│   ├── user.proto           # 用户服务
│   ├── post.proto           # 文章服务
│   ├── comment.proto        # 评论 + 点赞服务
│   ├── errors.proto         # 错误码定义（可选）
│   └── *.pb.go              # 生成的代码
├── cmd/blog/
│   ├── main.go              # 入口
│   ├── wire.go              # wire 声明
│   └── wire_gen.go          # wire 生成
├── configs/
│   ├── config.yaml          # 运行配置
│   └── schema.sql           # 数据库 DDL（给 DBA / CI 用）
├── internal/
│   ├── conf/
│   │   ├── conf.proto       # 配置 proto
│   │   └── conf.pb.go
│   ├── server/
│   │   ├── http.go          # HTTP 服务器装配（中间件链）
│   │   ├── grpc.go          # gRPC 服务器装配
│   │   └── server.go        # ProviderSet
│   ├── service/             # proto 接口的实现，只做转换
│   │   ├── service.go       # ProviderSet
│   │   ├── user.go
│   │   ├── post.go
│   │   └── comment.go
│   ├── biz/                 # 业务用例（核心领域逻辑）
│   │   ├── biz.go           # ProviderSet
│   │   ├── user.go          # User 实体 + UserRepo 接口 + UserUsecase
│   │   ├── post.go
│   │   └── comment.go
│   └── data/                # Repo 实现（GORM）
│       ├── data.go          # ProviderSet + DB 连接
│       ├── user.go
│       ├── post.go
│       └── comment.go
└── tests/
    ├── integration/
    │   └── api_test.go      # testcontainers-go 端到端
    └── biz/
        └── *_test.go        # biz 单测（用 mock repo）
```

### 依赖方向（严格单向）

```
api (proto)  ←──────────  service  ──→  biz (纯逻辑)  ←── data (GORM)
                              ↑                              ↑
                              │                              │
                            server  ──────→  conf / data（连接池）
                              ↑
                             cmd (wire 装配)
```

- `service` 依赖 `biz` 的 **Usecase**
- `biz` 定义 `XxxRepo` **接口**；`data` 实现之
- `biz` 不感知 `data`（由 wire 注入）

---

## 4. wire 依赖图

```
main
 └── wireApp(Bootstrap.Server, Bootstrap.Data, Logger)
      ├── conf.Bootstrap（解析 YAML）
      ├── data.ProviderSet
      │    ├── NewData(conf.Data, logger) → *Data (包含 *gorm.DB)
      │    ├── NewUserRepo(*Data) biz.UserRepo
      │    ├── NewPostRepo(*Data) biz.PostRepo
      │    └── NewCommentRepo(*Data) biz.CommentRepo
      ├── biz.ProviderSet
      │    ├── NewUserUsecase(biz.UserRepo, *conf.Auth, logger)
      │    ├── NewPostUsecase(biz.PostRepo, logger)
      │    └── NewCommentUsecase(biz.CommentRepo, biz.PostRepo, logger)
      ├── service.ProviderSet
      │    ├── NewUserService(*biz.UserUsecase)
      │    ├── NewPostService(*biz.PostUsecase)
      │    └── NewCommentService(*biz.CommentUsecase)
      └── server.ProviderSet
           ├── NewHTTPServer(conf.Server, jwt-secret, user/post/comment Service)
           └── NewGRPCServer(同上)
```

---

## 5. 数据库设计

### 5.1 表结构

见 `configs/schema.sql`。关键点：

| 表          | 主键                      | 关键索引                                                |
| ----------- | ------------------------- | ------------------------------------------------------- |
| users       | `id BIGSERIAL`            | `UNIQUE(email)`                                         |
| posts       | `id BIGSERIAL`            | `idx(author_id)`, `idx(created_at DESC)`, `GIN(tags)`   |
| comments    | `id BIGSERIAL`            | `idx(post_id, created_at DESC)`                         |
| post_likes  | `(post_id, user_id)` 联合 | `idx(user_id)`（反向查询用户点赞列表）                  |

### 5.2 一致性策略

- `posts.likes_count` **冗余**字段，写入时通过 `UPDATE posts SET likes_count = likes_count ± 1 WHERE id = ?` 维护
- 点赞 / 取消点赞使用 `ON CONFLICT DO NOTHING` / `DELETE` 实现幂等
- 建议用事务包裹「写 post_likes + 更新 likes_count」

### 5.3 迁移

第一期用 `configs/schema.sql` 手动建表；Data 层启动时**不执行** AutoMigrate（避免生产误操作），测试容器里由 testcontainers-go 执行 schema.sql。

---

## 6. 接口契约（细节见 proto 文件）

### HTTP 路径映射

| 方法   | 路径                         | proto RPC              | 鉴权 |
| ------ | ---------------------------- | ---------------------- | ---- |
| POST   | `/v1/users`                  | User.Register          | ×    |
| POST   | `/v1/auth/login`             | User.Login             | ×    |
| GET    | `/v1/users/me`               | User.GetMe             | √    |
| POST   | `/v1/posts`                  | Post.Create            | √    |
| GET    | `/v1/posts/{id}`             | Post.Get               | ×    |
| GET    | `/v1/posts`                  | Post.List              | ×    |
| PUT    | `/v1/posts/{id}`             | Post.Update            | √    |
| DELETE | `/v1/posts/{id}`             | Post.Delete            | √    |
| POST   | `/v1/posts/{post_id}/comments` | Comment.Create       | √    |
| GET    | `/v1/posts/{post_id}/comments` | Comment.List         | ×    |
| POST   | `/v1/posts/{post_id}/like`   | Comment.Like           | √    |
| DELETE | `/v1/posts/{post_id}/like`   | Comment.Unlike         | √    |

---

## 7. 错误码规范

使用 `github.com/go-kratos/kratos/v2/errors`。Reason 全大写下划线分隔。

| Reason               | HTTP | 场景                               |
| -------------------- | ---- | ---------------------------------- |
| `USER_INVALID_INPUT` | 400  | 参数格式错误（邮箱、密码长度）     |
| `USER_EMAIL_EXISTS`  | 409  | 注册时邮箱已存在                   |
| `USER_CRED_INVALID`  | 401  | 登录时邮箱或密码错误               |
| `USER_UNAUTHORIZED`  | 401  | 缺失或无效 JWT                     |
| `POST_NOT_FOUND`     | 404  | 查询 / 更新 / 删除不存在的文章     |
| `POST_NOT_OWNED`     | 403  | 更新 / 删除不属于自己的文章        |
| `COMMENT_NOT_FOUND`  | 404  | （预留，本期未用）                 |
| `INTERNAL_ERROR`     | 500  | 兜底                               |

示例：
```go
return nil, errors.Unauthorized("USER_UNAUTHORIZED", "invalid token")
return nil, errors.NotFound("POST_NOT_FOUND", "post 123 does not exist")
return nil, errors.Forbidden("POST_NOT_OWNED", "cannot modify others' post")
```

---

## 8. 中间件链（HTTP / gRPC）

```go
// HTTP Server
server.Middleware(
    recovery.Recovery(),                      // panic 捕获
    tracing.Server(),
    logging.Server(logger),
    validate.Validator(),                     // 基于 proto validate
    selector.Server(                          // JWT 白名单
        jwt.Server(func(token *jwtv4.Token) (interface{}, error) {
            return []byte(secret), nil
        }),
    ).Match(NewWhiteListMatcher()).Build(),
)
```

**白名单**（免 JWT）：
- `POST /v1/users`
- `POST /v1/auth/login`
- `GET /v1/posts` (list)
- `GET /v1/posts/{id}`
- `GET /v1/posts/{id}/comments`

JWT claims 规定 `sub = user_id(string)`, `exp = now + 7d`。service 层通过 `jwt.FromContext(ctx)` 取 `user_id`，封装成 `auth.GetUserID(ctx)` 辅助函数。

---

## 9. 配置（configs/config.yaml）

```yaml
server:
  http:
    addr: 0.0.0.0:8000
    timeout: 30s
  grpc:
    addr: 0.0.0.0:9000
    timeout: 30s

data:
  database:
    driver: postgres
    source: "host=127.0.0.1 port=5432 user=postgres password=postgres dbname=blog_dev sslmode=disable"
    max_idle: 10
    max_open: 100

auth:
  jwt_secret: "replace-me-in-prod"
  jwt_ttl_seconds: 604800   # 7d
```

---

## 10. 分工建议

### developer（biz + data 层）
- **产出目录**：`internal/biz/*`, `internal/data/*`
- **任务**：
  1. `biz/user.go`：`User` 实体、`UserRepo` 接口、`UserUsecase`（Register/Login/GetMe，含 bcrypt 校验、JWT 签发）
  2. `biz/post.go`：`Post` 实体、`PostRepo` 接口、`PostUsecase`（Create/Get/List/Update/Delete，含所有权校验）
  3. `biz/comment.go`：`Comment` 实体、`CommentRepo` 接口、`CommentUsecase`（Create/List/Like/Unlike，点赞幂等）
  4. `data/*`：GORM 实现三个 Repo，事务处理点赞 + 计数
  5. biz 层单测（用 gomock / 手写 fake 实现 Repo 接口）
- **不要碰**：proto、service、server、wire.go

### developer_2（service + server + wire + cmd）
- **产出目录**：`internal/service/*`, `internal/server/*`, `internal/conf/*`, `cmd/blog/*`, `configs/config.yaml`, `Makefile`, `go.mod`
- **任务**：
  1. 初始化 `go.mod`（参考 kratos-layout）、Makefile（make api / make build / make wire）
  2. 根据架构师的 3 个 proto 跑 `make api` 生成 `*.pb.go`（依赖 developer 尚未产出时也可以先做，只要 proto 文件已就位）
  3. `internal/conf/conf.proto` + 生成
  4. `internal/service/*.go`：实现 UserServiceServer/PostServiceServer/CommentServiceServer，只做 DTO 转换和 `auth.GetUserID(ctx)` 取值
  5. `internal/server/http.go`, `grpc.go`：装配中间件链、JWT 白名单
  6. `cmd/blog/main.go` + `wire.go`，跑 `make wire`
  7. 与 developer 对齐 biz 接口签名（有变动互发消息）
- **不要碰**：biz / data 内部实现

### tester（测试框架 + 集成测试）
- **产出目录**：`tests/integration/*`
- **任务**：
  1. 先搭骨架：`TestMain` 用 testcontainers-go 启动 PostgreSQL 容器，执行 `configs/schema.sql`
  2. 启动 app（复用 wire，或直接构造 HTTPServer）绑定临时端口
  3. 用 `net/http` 写端到端用例：注册→登录→发帖→列表→评论→点赞→取消点赞→更新→删除
  4. biz 单测可以由 developer 自己写，tester 做覆盖度补充（错误路径）
  5. 目标：`go test ./... -race -cover` 核心路径 ≥ 70%
- **协作点**：
  - 等 architect 产出 proto + schema 后即可动工搭骨架
  - 等 developer_2 产出 wire / main.go 后，测试里可以 `go run ./cmd/blog`

---

## 11. 里程碑与协作序列

```
T0  architect  发 proto + schema + 架构文档 → 通知 3 人
T1  developer_2 初始化 go.mod / Makefile / 生成 proto
T1  developer   写 biz 实体 + Repo 接口（只对外）
T2  developer   完成 biz，developer_2 完成 service，两人对齐
T3  developer   完成 data（GORM 实现）
T3  developer_2 完成 server + cmd + wire
T4  tester     集成测试跑通，上报覆盖率
T5  architect  review，汇总 report-architect.md
```

---

## 12. 验收清单

- [ ] `go build ./...` 通过
- [ ] `go vet ./...` 无告警
- [ ] `go test ./... -race -cover` 通过，核心路径 ≥ 70%
- [ ] 集成测试（testcontainers-go）能从注册跑到点赞全流程
- [ ] biz 层不 import gorm / kratos/transport（grep 校验）
- [ ] 没有手写 HTTP handler（只认 `_http.pb.go` 生成物）
