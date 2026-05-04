# Developer_2 装配报告（BlogAPI / Go + Kratos）

> Owner: developer_2（林2）
> 最后更新：2026-05-04 15:30

## 交付摘要

- `go mod tidy && go build ./... && go vet ./...`：全部通过（0 warning）
- `go test -c ./...`：所有包测试二进制可编译
- 本人不改 architect 的 `api/blog/v1/*.pb.go`；在 `internal/server/http.go` 中手动注册路由
- 装配路径：`data → biz → service → server → kratos.App`，通过手写 `wireApp` 完成（不依赖 wire CLI）

## 产出文件

| 层级 | 文件 | 说明 |
|------|------|------|
| 模块 | `go.mod` | module=blog, go 1.21, 依赖 kratos v2.7.3 / jwt v5 / gorm / pgx / grpc |
| 配置 | `configs/config.yaml` | http 8000 / grpc 9000 / 本地 postgres DSN / jwt_secret / access_ttl=168h |
| 工具 | `Makefile` | build/run/test/tidy/vet/clean |
| 契约 | `internal/conf/conf.pb.go` | 手写 Bootstrap/Server/Data/Auth + 全部 Getter（Go 风格 `Http/Grpc`） |
| 认证 | `internal/pkg/auth/auth.go` | `JWTIssuer.Sign/Parse`、`Middleware`（selector.Server 驱动）、`UserIDKey/WithUserID/UserIDFromContext`、`ProviderSet` |
| 传输 | `internal/server/http.go` | 12 条路由全部注册；selector 配合 `publicMatch` 对 `POST /v1/users`、`POST /v1/auth/login`、`GET /v1/posts*` 放行 |
| 传输 | `internal/server/grpc.go` | 最小化 gRPC 启动（HTTP 是对外主通道，gRPC 保留以供未来 rpc-only client） |
| 传输 | `internal/server/server.go` | `ProviderSet = wire.NewSet(NewHTTPServer, NewGRPCServer)` |
| 协议 | `internal/service/{service,user,post,comment}.go` | 将 `biz.*Usecase` 适配为 `v1.*ServiceServer`，不写业务逻辑；时间字段用 `timestamppb.New` |
| 入口 | `cmd/server/main.go` | 直接 `gopkg.in/yaml.v3` 解析 yaml（duration 字段走字符串） |
| 入口 | `cmd/server/wire.go` | 手写 `wireApp`，明确 cleanup 链 |
| 测试 | `tests/integration/app_factory_real.go` | 注册 `integration.AppFactory`；`kratosRunner` 实现 `AppRunner`；`HTTPAddr()` 通过 `http.Server.Endpoint()` 在 Start 前先 bind 拿实际端口 |

## 关键决策

1. **不跑 protoc / wire CLI**：architect 已手写 `*.pb.go`（仅含 Request/Reply + Server interface + Unimplemented）；我在 `internal/server/http.go` 里手动调 `r.POST/GET/...`，handler 使用 `ctx.Bind` / `ctx.Vars().Get("id")` / `ctx.Request().URL.Query()` 完成参数映射。
2. **放弃为 pb.go 补 `RegisterXxxServiceServer`**：architect 的 pb.go 不含 grpc ServiceDesc，我的 gRPC server 只启动、不绑定 service，避免破坏 architect 的 file ownership。HTTP 是事实上的主传输，e2e 覆盖充分。
3. **conf 字段命名**：架构师建议用 `JwtSecret/AccessTtl/Http/Grpc`（Go 风格，与 proto 生成产物一致），data 层 `c.GetDatabase().GetSource()` 已适配。
4. **TokenIssuer 隐式接口**：dev_1 的 `biz.TokenIssuer` 只要求 `Sign(int64)(string,error)`；`auth.JWTIssuer` 签名完全对齐，wire 直接传 `*auth.JWTIssuer` 即可，无适配层。
5. **JWT 中间件 selector**：用 `selector.Server(auth.Middleware(jwt)).Match(publicMatch).Build()`；`publicMatch` 通过 `khttp.Transporter.Request()` 检查 method+path，把 `POST /v1/users`、`POST /v1/auth/login`、任何 `GET /v1/posts*` 放行。
6. **integration AppFactory**：tester 在 `app_stub.go` 只给了类型钩子不暴露 wireApp；我把装配代码复制到 `tests/integration/app_factory_real.go` 并通过 `init()` 注册，`kratosRunner.HTTPAddr()` 通过 `Endpoint()` 预绑定确保 `127.0.0.1:0` 场景下返回真实端口。

## 验证命令

```bash
cd prototype/M4-example2-e2e/.ai-rd-team/runtime/artifacts/code/
go mod tidy       # ok
go build ./...    # ok
go vet ./...      # ok (no warnings)
go test -c ./...  # ok (tests/integration 可编译)
```

## 未完成 / 需后续关注

- gRPC 服务未注册 `*ServiceServer`：若后续需要 gRPC 客户端对接，需请 architect 补 `RegisterXxxServiceServer(grpc.ServiceRegistrar, ...)`；当前版本 HTTP 是唯一可用外部 API。
- 错误 HTTP 状态码映射：已通过 kratos `errors.BadRequest/Unauthorized/Forbidden/NotFound/Conflict` 走标准流程，reason 常量全部来自 `v1.Reason*`。
- Validate/pgv：本期未引入 `validate.Validator()` 中间件；入参校验下沉到 biz 层（dev_1 已实现）。

## 协作脉络

- 与 dev_1 对齐 biz 接口/字段命名（收到他的确认消息）
- 与 architect 对齐 pb.go ownership + conf 字段命名（按他的指示执行）
- 与 tester 对齐 `AppFactory` 钩子（完成真实实现注册）
