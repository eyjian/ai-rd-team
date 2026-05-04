# BlogAPI 架构设计（Standard 档）

> 作者：陈架构（architect）
> 技术栈：Go 1.21+ / Kratos v2 / GORM / PostgreSQL 15 / JWT / wire
> module 名：`blog`

---

## 1. 架构分层

严格遵循 Kratos 四层：

```
+----------------------------------------+
| cmd/server (main + wire_gen)           |
+----------------------------------------+
| internal/server  (HTTP/GRPC 服务器注册) |
+----------------------------------------+
| internal/service (pb 接口实现，DTO<->DO) |
+----------------------------------------+
| internal/biz     (核心业务 usecase, DO) |
+----------------------------------------+
| internal/data    (repo 实现, GORM)      |
+----------------------------------------+
| api/blog/v1      (proto + pb.go)        |
+----------------------------------------+
```

- **biz 层禁止 import gorm**（仅依赖 repo interface 与纯 DO struct）
- **service 层** 只做：pb 入参校验、调用 biz、error -> kratos errors、DO -> pb
- **data 层** 实现 biz 定义的 repo 接口

---

## 2. 目录结构

```
.
├── go.mod                          # module = "blog"
├── cmd/server/
│   ├── main.go
│   ├── wire.go                     # +build wireinject
│   └── wire_gen.go                 # wire 生成（手写等价）
├── api/blog/v1/
│   ├── common.proto / common.pb.go
│   ├── user.proto   / user.pb.go
│   ├── post.proto   / post.pb.go
│   ├── comment.proto/ comment.pb.go
│   └── errors.go                   # 错误码常量 + 便捷构造
├── internal/
│   ├── conf/                       # Bootstrap / Data / Server / Auth 配置
│   ├── server/                     # http.go / grpc.go ProviderSet
│   ├── service/                    # user / post / comment service
│   ├── biz/                        # user / post / comment usecase + repo 接口
│   └── data/                       # data.go / user_repo / post_repo / comment_repo
├── configs/config.yaml
└── Makefile
```

---

## 3. Wire 依赖图

```
cmd/server/main
     │
     ▼
 wireSet = {
   conf.ProviderSet,        // &conf.Bootstrap
   data.ProviderSet,        // NewData, NewUserRepo, NewPostRepo, NewCommentRepo, NewPostLikeRepo
   biz.ProviderSet,         // NewUserUsecase, NewPostUsecase, NewCommentUsecase
   service.ProviderSet,     // NewUserService, NewPostService, NewCommentService
   server.ProviderSet,      // NewHTTPServer, NewGRPCServer
 }
     │
     ▼
 App（kratos.App） => hs + gs
```

注入链：

```
Bootstrap -> Data(GORM *gorm.DB) -> Repo(UserRepo/PostRepo/CommentRepo/PostLikeRepo)
          -> Usecase(UserUsecase/PostUsecase/CommentUsecase)
          -> Service(UserService/PostService/CommentService)
          -> HTTPServer + GRPCServer
          -> kratos.App
```

---

## 4. 错误码（kratos errors）

| Reason                      | HTTP | 说明             |
|-----------------------------|------|------------------|
| USER_NOT_FOUND              | 404  | 用户不存在       |
| USER_ALREADY_EXISTS         | 409  | 邮箱已注册       |
| USER_CREDENTIAL_INVALID     | 401  | 登录失败         |
| USER_UNAUTHENTICATED        | 401  | 未登录/token 无效|
| POST_NOT_FOUND              | 404  | 文章不存在       |
| POST_FORBIDDEN              | 403  | 非作者无权操作   |
| COMMENT_NOT_FOUND           | 404  | 评论不存在       |
| VALIDATION_FAILED           | 400  | 入参校验失败     |
| INTERNAL_ERROR              | 500  | 未分类内部错误   |

统一在 `api/blog/v1/errors.go` 定义常量和便捷构造函数，例如：

```go
func ErrorPostNotFound(format string, a ...any) *errors.Error {
    return errors.New(404, "POST_NOT_FOUND", fmt.Sprintf(format, a...))
}
```

---

## 5. HTTP 映射

| Method | Path                         | Service 方法           | Biz 方法                     | 鉴权 |
|--------|------------------------------|------------------------|------------------------------|------|
| POST   | /v1/users                    | UserService.Register   | UserUsecase.Register         | -    |
| POST   | /v1/auth/login               | UserService.Login      | UserUsecase.Login            | -    |
| GET    | /v1/users/me                 | UserService.GetMe      | UserUsecase.GetByID          | JWT  |
| POST   | /v1/posts                    | PostService.Create     | PostUsecase.Create           | JWT  |
| GET    | /v1/posts/{id}               | PostService.Get        | PostUsecase.Get              | -    |
| GET    | /v1/posts                    | PostService.List       | PostUsecase.List             | -    |
| PUT    | /v1/posts/{id}               | PostService.Update     | PostUsecase.Update           | JWT  |
| DELETE | /v1/posts/{id}               | PostService.Delete     | PostUsecase.Delete           | JWT  |
| POST   | /v1/posts/{id}/comments      | CommentService.Create  | CommentUsecase.Create        | JWT  |
| GET    | /v1/posts/{id}/comments      | CommentService.List    | CommentUsecase.ListByPost    | -    |
| POST   | /v1/posts/{id}/like          | PostService.Like       | PostUsecase.Like             | JWT  |
| DELETE | /v1/posts/{id}/like          | PostService.Unlike     | PostUsecase.Unlike           | JWT  |

---

## 6. 关键技术决策

1. **JWT**：自定义 Claims（user_id, email, exp）；middleware 解析 `Authorization: Bearer xxx` 注入 ctx（key：`userIDCtxKey`）。
2. **密码**：bcrypt（cost=10）。
3. **tag 存储**：`posts.tags` 使用 PostgreSQL `text[]`（GORM: `pq.StringArray`）。
4. **幂等点赞**：`post_likes` 联合主键 `(post_id, user_id)`；Like/Unlike 使用 `ON CONFLICT DO NOTHING` / `DELETE`，并事务中 `posts.like_count++/--`。
5. **分页**：`page>=1, size∈[1,50]`，返回 `total` 以便前端分页。
6. **id 类型**：全部 `int64`（GORM 自增）；proto 中用 `int64`。
7. **time**：数据库 `TIMESTAMPTZ`；proto 用 `google.protobuf.Timestamp`。

---

## 7. 分工（与 team-lead 约定一致）

- **architect**：本设计 + schema.sql + api/blog/v1/* + go.mod
- **developer_1**：internal/biz/ + internal/data/
- **developer_2**：conf + server + service + cmd + wire
- **tester**：tests/integration/（testcontainers-go + PostgreSQL）

---

## 8. 验收目标

- `go mod tidy && go build ./...` 通过
- `go test ./internal/biz/...` biz 单测通过
- 每人输出 `report-*.md`
