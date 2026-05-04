# report-architect.md

> 作者：陈架构（architect）
> 时间：2026-05-04

## 交付清单

### 设计文档（`.../runtime/artifacts/design/`）
- `spec-design.md`：架构分层、目录结构、wire 依赖图、错误码、HTTP 映射、关键技术决策、验收目标
- `biz-contracts.md`：biz 层 DO、Repo 接口、Usecase 方法签名、错误语义（给 developer_1）
- `schema.sql`：4 张表（users / posts / comments / post_likes 联合主键幂等点赞）

### 代码（`.../runtime/artifacts/code/`）
- `go.mod`（module = `blog`，go 1.21，含 kratos v2 / gorm / postgres / jwt / wire / yaml）
- `Makefile`（tidy / build / test / run）
- `api/blog/v1/`
    - `common.proto` + `common.pb.go`
    - `user.proto`   + `user.pb.go`（Register / Login / GetMe + HTTP 路由注册）
    - `post.proto`   + `post.pb.go`（CRUD + List + Like/Unlike）
    - `comment.proto`+ `comment.pb.go`（Create / List）
    - `errors.go`（kratos errors 统一封装，给 biz/service 使用）

### state
- `runtime/state/members/architect.yaml`

---

## 分工触达

已 `send_message` 给三位队友：
- **developer_1**：`internal/biz/` + `internal/data/`，并附 biz-contracts.md 指引
- **developer_2**：`go.mod` tidy + `conf` + `server` + `service` + `cmd` + `wire`，并说明 service 层可直接 import 我写的 pb.go
- **tester**：`tests/integration/`，覆盖注册登录/文章 CRUD/评论/幂等点赞/403 非作者

---

## 关键技术决策速览
1. 严格四层：api → service → biz → data；biz 禁止 gorm。
2. 手写 pb.go「等价 protoc 产出」策略：保留 message struct、`XxxHTTPServer` interface 与 `RegisterXxxHTTPServer`，使用 kratos `transport/http` 原生路由。不依赖 protoc，`go build` 可通过。
3. 幂等点赞：`post_likes` 联合主键 `(post_id, user_id)`；仓储层返回 `added/removed bool`，事务中 `posts.like_count` 自增自减。
4. JWT：`github.com/golang-jwt/jwt/v5`，Claims 含 `user_id`；middleware 注入 ctx。
5. ID 用 `int64`；tag 用 PostgreSQL `text[]` + `pq.StringArray`。

---

## 已识别风险
- kratos `transport/http` 在 v2.7.3 中 `http.Context` API 为 `ctx.Vars()` / `ctx.Query()` / `ctx.Middleware()`；若版本有差异，developer_2 在集成时需微调。
- `testcontainers-go` 在 CI 环境需 docker socket；tester 请在 README 中声明。

## 下一步
等待三位队友产出后整体复核，协助消解 `go build ./...` 残余错误。
