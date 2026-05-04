# developer_1 交付报告 — BlogAPI 后端 biz/data 层

- Owner: 林1（developer_1）
- 完成时间: 2026-05-04 15:40 CST
- 工作目录: `prototype/M4-example2-e2e/.ai-rd-team/runtime/artifacts/code/`

## 1. 交付范围

对照 architect 的 `artifacts/design/data-interfaces.yaml` 与 `spec-design.md` 实现：

| 模块 | 文件 | 说明 |
|------|------|------|
| biz 层 | `internal/biz/biz.go` | `ProviderSet = wire.NewSet(NewUserUsecase, NewPostUsecase, NewCommentUsecase)` |
| biz 层 | `internal/biz/user.go` | `User` 模型 + `UserRepo` 接口 + `TokenIssuer` 接口 + `UserUsecase` (Register/Login/Get) |
| biz 层 | `internal/biz/post.go` | `Post` 模型 + `PostRepo` 接口 + `PostUsecase` (CRUD + 幂等 Like/Unlike) |
| biz 层 | `internal/biz/comment.go` | `Comment` 模型 + `CommentRepo` 接口 + `CommentUsecase` (Create / ListByPost) |
| data 层 | `internal/data/data.go` | `Data{*gorm.DB}` + `NewData(*conf.Data, log.Logger)` + ProviderSet |
| data 层 | `internal/data/user.go` | `userPO` + `userRepo`（GORM 实现，唯一索引冲突映射为 USER_EMAIL_EXISTS） |
| data 层 | `internal/data/post.go` | `postPO/postLikePO` + `postRepo`（TEXT[] tags + GIN、事务内 like 计数幂等） |
| data 层 | `internal/data/comment.go` | `commentPO` + `commentRepo` |
| data 层 | `internal/data/errors.go` | PG 唯一索引冲突探测工具 |
| 工具 | `internal/pkg/password/bcrypt.go` | bcrypt 封装 + `SetTestCost` 便于单测加速 |
| SQL | `configs/schema.sql` | Postgres 15 schema（tags TEXT[] + GIN 索引、post_likes 复合 PK + ON DELETE CASCADE） |
| 单测 | `internal/biz/{mock_test.go,user_test.go,post_test.go,comment_test.go}` | biz 层 mock 单测（不依赖 gomock，纯内存 fake repo） |

## 2. 关键契约对齐

### 2.1 与 architect 对齐
- Repo 接口签名、领域模型字段、错误 reason 全部来自 `data-interfaces.yaml`，未自行引入新字段。
- `AddLike/RemoveLike` 返回 `(bool, error)`，幂等语义下沉到 data 层（`ON CONFLICT DO NOTHING` + `RowsAffected`）。
- `ListByPost` 一次调用即返回 `(items, total, error)`，不再暴露 `CountByPost`。

### 2.2 与 developer_2 对齐
- biz 层的 `TokenIssuer` 接口方法名从 `Issue` 改为 `Sign(userID int64) (string, error)`，直接对齐 `auth.JWTIssuer.Sign` 的签名 → developer_2 不需要额外适配。
- `NewUserUsecase(repo UserRepo, auth TokenIssuer, logger log.Logger)` 第二个参数是接口，handwired wire 里直接传 `*auth.JWTIssuer` 即可编译通过（Go 隐式接口实现）。
- module 名固定 `blog`。所有 import 路径：`blog/internal/biz`、`blog/internal/data`、`blog/internal/pkg/password`。

## 3. 分层契约（严格遵守）

- **biz 层零依赖 GORM** — `grep -R "gorm" internal/biz/` 结果为空。
- **data 层返回 biz 模型** — 所有 Repo 方法签名参数/返回都使用 `*biz.User / *biz.Post / *biz.Comment`，PO（userPO/postPO/commentPO）仅在 data 包内部使用。
- **错误映射**：data 返回 `biz.ErrXxxNotFound` 或 kratos errors，biz 层统一包装为 `kerrors.NotFound("POST_NOT_FOUND", ...)` 等最终 reason。
- **权限校验在 biz 层**：Update/Delete Post 会检查 `operatorID == existing.AuthorID`，非作者返回 FORBIDDEN。

## 4. 测试情况

biz 层单测覆盖：
- UserUsecase: Register 成功 / 3 种校验失败 / 邮箱重复 / Login 成功 / 密码错误 / 用户不存在 / Get
- PostUsecase: Create/Update/Delete/List（分页 + tag 过滤）/ Like/Unlike 幂等 / 非作者 FORBIDDEN / post 不存在
- CommentUsecase: Create + 校验 + post 不存在 / ListByPost

所有单测使用手写 fake Repo，不依赖 DB。bcrypt 测试 cost=4 加速。

> ⚠️ data 层集成测试（testcontainers-go）由 tester 负责，我未实现。

## 5. 对其他团队成员的影响

- **developer_2**：可以放心在 service 层写：
  - `biz.ProviderSet` 已就位
  - `data.ProviderSet` 已就位（包含 `NewData` + 三个 NewXxxRepo）
  - 顶层 wire 把 `biz.ProviderSet + data.ProviderSet + auth.ProviderSet` 合并即可。
  - `NewUserUsecase` 期望一个实现 `Sign(int64) (string, error)` 的类型，直接传 `*auth.JWTIssuer`。
- **tester**：biz 层已有完整 mock 单测，可以作为风格参考；data 层集成测试可以直接用 `internal/data` 的 Repo 构造函数。

## 6. 未决 / 风险

- `isUniqueViolation` 依赖 `github.com/jackc/pgconn`。若 developer_2 / architect 在 go.mod 中未引入，需要加一个 `go get`。作为兜底，函数里也带了字符串匹配。
- `TokenIssuer` 是接口而非具体类型，handwired wire 要显式传参；如果 developer_2 希望我改回 `*auth.JWTIssuer` 具体类型，我可以一分钟内切回去。

## 7. 落盘文件清单

```
internal/biz/biz.go
internal/biz/user.go
internal/biz/post.go
internal/biz/comment.go
internal/biz/mock_test.go
internal/biz/user_test.go
internal/biz/post_test.go
internal/biz/comment_test.go
internal/data/data.go
internal/data/errors.go
internal/data/user.go
internal/data/post.go
internal/data/comment.go
internal/pkg/password/bcrypt.go
configs/schema.sql
```
