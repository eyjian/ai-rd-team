# Architect 总结报告（BlogAPI）

> Owner: architect（陈架构）
> 时间：2026-05-04
> 档位：standard

## 1. 交付清单

### 设计产出（artifacts/design/）
- `spec-design.md` —— 系统架构总览、分层、横切关注（认证/错误/幂等/事务/配置）、风险 & 分工
- `data-interfaces.yaml` —— 机器可读的唯一契约源：领域模型、Repo/Usecase 签名、HTTP 路由、错误码、DB schema、测试规划
- `biz-contracts.md` —— biz 层人读版契约 + 验收清单
- `schema.sql` —— 最终 PostgreSQL 15 schema（users/posts/comments/post_likes，含 CASCADE/GIN 索引/幂等主键）
- `go.mod.template` —— 依赖参考

### 代码骨架（artifacts/code/）
- `go.mod` —— module=`blog`，go 1.21，固化 kratos v2 / jwt v5 / grpc / protobuf / gorm / postgres / crypto 版本
- `api/blog/v1/*.proto` —— UserService / PostService / CommentService 接口源（含 google.api.http 注解）
- `api/blog/v1/*.pb.go` —— **手写等价版**：所有 Request/Response + *ServiceServer 接口 + Unimplemented 基类
- `api/blog/v1/errors.go` —— 统一错误 reason 常量（USER_EMAIL_EXISTS / INVALID_CREDENTIALS / FORBIDDEN / *_NOT_FOUND / VALIDATION_FAILED / UNAUTHORIZED）

## 2. 关键技术决策

1. **module 名 `blog`，go 1.21**，PostgreSQL 15，JWT 7 天 TTL（与 team-lead 需求对齐）。
2. **分层严格依赖倒置**：service → biz ← data；biz 只持有 Repo 接口，data 实现；PO 不得泄漏到 biz。
3. **不跑 protoc / wire CLI**：手写 pb.go 提供接口，HTTP 路由由 developer_2 在 `internal/server/http.go` 用 kratos `transhttp.Server.Route` 直接注册。wire_gen.go 手写。规避了 CI 环境缺工具链导致 `go build ./...` 失败的风险。
4. **幂等语义下沉到 Repo**：`AddLike/RemoveLike` 返回 `(bool, error)`，usecase 层无需 IsLikedBy 预检；计数与 post_likes 变更在同事务内完成。
5. **错误模型统一**：biz 层用 `kratos/errors.{Conflict,Unauthorized,Forbidden,NotFound,BadRequest}`；service 层不重包；reason 字符串常量在 `api/blog/v1/errors.go`。

## 3. 分工协同

| Owner | 负责模块 |
|-------|----------|
| architect | design 四件套 + go.mod + api/blog/v1（proto+手写 pb.go） |
| developer_1 | internal/biz + internal/data + internal/pkg/password + configs/schema.sql |
| developer_2 | internal/conf + internal/server + internal/service + cmd/server（含 wire_gen.go）+ internal/pkg/auth + Makefile + configs/config.yaml |
| tester | tests/e2e + biz 单测 + data 集成测 + README 测试章节 |

与 developer_1 对齐了 Repo 命名与幂等语义；与 developer_2 明确了"不跑 protoc / 手写 wire_gen"策略与 HTTP 路由注册模板；与 tester 明确了三层测试（unit/integration/e2e）的覆盖点与错误断言方式。

## 4. 风险与遗留

- **未亲自验证 `go build ./...` 通过**：因本次关闭请求到达时 developer_1/2 尚在实现中，最终构建由他们在集成时验证。手写 pb.go 覆盖所有 service/server 需要的类型与接口，若后续发现缺字段属常规补丁，可直接在 `api/blog/v1/` 追加。
- **gRPC 接口**：本期手写 pb.go 只提供 Server 接口（给 service 实现用），没有生成 gRPC 的注册函数（`Register*ServiceServer(s, impl)`）。HTTP 路径可完整跑通；如需真正的 gRPC endpoint 对接，后续再补一份 `_grpc.pb.go`。
- **proto → pb.go 的字段后续如扩展**，请同步更新 `.proto` 与手写 `.pb.go`，两者保持一致（审视点：字段 tag 对齐）。

## 5. 对后续实现者的建议

- biz 层记得在 `gorm.ErrRecordNotFound` 分支返回领域语义错误。
- service 层从 `context` 取 `user_id` 统一走 `auth.UserIDFromContext(ctx)`，失败一律 `UNAUTHORIZED`。
- 所有时间字段序列化用 `timestamppb.New(t)`。
- Makefile 的 `tidy` 和 `build` 目标是 `go build ./...` 通过的最后一道把关，优先保证它们绿。

## 6. 结论

架构设计、契约、核心 API 骨架（go.mod + api/blog/v1）已全部落盘，与 developer_1 / developer_2 / tester 的工作边界已明确。后续由三位队友在契约之上独立实现，契约冲突以 `data-interfaces.yaml` 为准。
