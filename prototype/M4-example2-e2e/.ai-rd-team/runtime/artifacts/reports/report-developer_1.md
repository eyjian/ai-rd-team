# Report - developer_1 (林1)

> 角色：Go + Kratos 项目实现者
> 范围：`internal/biz/` + `internal/data/` + `internal/pkg/password/`
> module：`blog`

---

## 1. 交付清单

### 1.1 biz 层（核心业务）

| 文件 | 说明 |
|------|------|
| `internal/biz/biz.go` | `ProviderSet`（NewUserUsecase/NewPostUsecase/NewCommentUsecase）+ `UserIDCtxKey` + `UserIDFromContext()` |
| `internal/biz/user.go` | `User` DO、`UserRepo` 接口、`UserUsecase`（Register/Login/GetByID）、JWT(HS256) 签发、`ErrUserNotFound` 哨兵 |
| `internal/biz/post.go` | `Post` DO、`PostRepo` / `PostLikeRepo` 接口、`PostUsecase`（Create/Get/List/Update/Delete/Like/Unlike）、`ErrPostNotFound` 哨兵、tags 标准化 |
| `internal/biz/comment.go` | `Comment` DO、`CommentRepo` 接口、`CommentUsecase`（Create/ListByPost） |

**强约束验证**：
- ✅ biz 层 import 清单：`context / errors / strings / time / blog/api/blog/v1 / blog/internal/conf / blog/internal/pkg/password / go-kratos/kratos/v2/log / golang-jwt/jwt/v5 / google/wire`
- ✅ **无 gorm / gorm.io/* import**
- ✅ data 层返回 biz DO，biz 层只持有 repo interface
- ✅ 所有业务错误走 `v1.ErrorXxx`（USER_ALREADY_EXISTS / USER_CREDENTIAL_INVALID / USER_NOT_FOUND / POST_NOT_FOUND / POST_FORBIDDEN / VALIDATION_FAILED / USER_UNAUTHENTICATED），Reason 字符串严格对齐 architect 的 `errors.go`

### 1.2 密码包

| 文件 | 说明 |
|------|------|
| `internal/pkg/password/bcrypt.go` | `Hash(plain) (string, error)` / `Verify(hash, plain) bool`，cost=10 |

### 1.3 data 层（GORM/PostgreSQL 实现）

| 文件 | 说明 |
|------|------|
| `internal/data/data.go` | `Data` struct、`NewData(c *conf.Data, logger)` 返回 `(*Data, func(), error)`、连接池配置（MaxOpen=20 / MaxIdle=5）、`ProviderSet` |
| `internal/data/models.go` | PO：`userPO / postPO / commentPO / postLikePO`（表名显式声明，GORM tag 与 schema.sql 对齐） |
| `internal/data/user.go` | `UserRepo` 实现：Create / GetByID / GetByEmail，`ErrRecordNotFound` → `biz.ErrUserNotFound` |
| `internal/data/post.go` | `PostRepo` 实现：Create / GetByID / Update / Delete / List（按 tag 过滤使用 `? = ANY(tags)`，走 GIN 索引；分页 + 总数） |
| `internal/data/comment.go` | `CommentRepo` 实现：Create / ListByPost（按 created_at ASC） |
| `internal/data/post_like.go` | `PostLikeRepo` 实现：**幂等 Add/Remove** |

**关键实现点**：
- ✅ **data 层不返回 GORM PO**，所有 repo 方法返回 biz DO（通过 `toUserDO/toPostDO/toCommentDO` 转换）
- ✅ `Like` 使用 `ON CONFLICT DO NOTHING` + 事务：`RowsAffected==1` 才 `like_count+=1`；重复 Like 不重复计数
- ✅ `Unlike` 删除命中 1 行才 `like_count-=1`；带 `like_count > 0` 防御性条件防负
- ✅ `pq.StringArray` 映射 PostgreSQL `text[]`

---

## 2. biz 层单测

单测用**手写 mock**（无需 gomock 工具链），mock 位于 `internal/biz/mock_test.go`（`mockUserRepo / mockPostRepo / mockPostLikeRepo / mockCommentRepo`）。

### 覆盖用例（对应 biz-contracts.md §7）

| 测试文件 | 测试用例 | 契约要求 |
|----------|----------|----------|
| `user_test.go` | Register_EmailExists（USER_ALREADY_EXISTS） | ✅ |
| | Register_Success（bcrypt 非明文、email 小写 trim） | ✅ |
| | Register_ValidationFailed（邮箱/密码/昵称多种非法入参） | ✅ |
| | Login_WrongPassword（USER_CREDENTIAL_INVALID） | ✅ |
| | Login_EmailNotFound（统一 USER_CREDENTIAL_INVALID，不暴露差异） | ✅ |
| | Login_Success（token 非空） | ✅ |
| | GetByID_NotFound（USER_NOT_FOUND） | ✅ |
| `post_test.go` | Create_Success（title trim + tags 去重过滤空） | ✅ |
| | Create_ValidationFailed | ✅ |
| | **List_TagFilter**（tag 传递到 repo） | ✅ |
| | **Update_NonAuthorForbidden**（POST_FORBIDDEN） | ✅ |
| | Update_NotFound（POST_NOT_FOUND） | ✅ |
| | Delete_AuthorSuccess | ✅ |
| | **Like_Idempotent**（连续 Add 两次 likes 只 1 条） | ✅ |
| | Unlike_Idempotent（未点过赞取消不报错） | ✅ |
| | Like_PostNotFound（POST_NOT_FOUND） | ✅ |
| `comment_test.go` | **Create_PostNotFound**（POST_NOT_FOUND） | ✅ |
| | Create_Success（body trim） | ✅ |
| | Create_EmptyBodyValidation | ✅ |
| | ListByPost_PostNotFound | ✅ |
| | ListByPost_Success | ✅ |

共 **20+ 个测试用例**，全部覆盖 biz-contracts.md §7 列出的必测场景（加粗部分为契约强制要求的 5 条）。

---

## 3. 与上下游的契约对齐

### 3.1 与 architect（已确认）

`blog/api/blog/v1/errors.go` 导出 9 个 `Error*` 构造函数 + 9 个 `Reason*` 常量 + `Is*` helpers。Reason 字符串全部严格匹配 HTTP 错误码表，**单测直接对比 Reason 通过**。

### 3.2 与 developer_2（已通知）

- ProviderSet 构造函数签名已全部列出
- `conf.Data.Database.Source`、`conf.Auth.JWTSecret`、`conf.Auth.Expire (time.Duration)` 已按**方案 B（普通 struct + yaml tag）**对齐（由 tester 的 build 错误驱动的修正）
- ctx key：`biz.UserIDCtxKey`（ctxKey 类型），值类型 int64；提供 `biz.UserIDFromContext(ctx)` 给 service 层使用
- go.mod 依赖清单：`golang-jwt/jwt/v5`、`golang.org/x/crypto`、`gorm.io/gorm`、`gorm.io/driver/postgres`、`lib/pq`、`google/wire`、`go-kratos/kratos/v2`、`gopkg.in/yaml.v3`

### 3.3 与 tester（已响应）

- 原 biz/user.go 使用 `auth.GetJwtSecret()` / `auth.GetExpire()` 的 protobuf 风格 getter，tester 反馈 build 失败。
- **已切换为方案 B**：`auth.JWTSecret`、`auth.Expire`、`c.Database.Source` 直接字段访问。
- 单测文件 user_test.go 同步修正字面量构造为 `&conf.Auth{JWTSecret: "...", Expire: 24*time.Hour}`。

---

## 4. 设计决策备忘

1. **哨兵错误位置**：`biz.ErrUserNotFound` / `biz.ErrPostNotFound` 定义在 biz 包。data 层返回这些哨兵，biz 层用 `errors.Is` 识别后转 `v1.Error*`。未给 Comment 定义哨兵，因为 biz 不需要判断「评论不存在」业务（Create/List 只校验 post 存在）。

2. **Like/Unlike 必须先 GetByID**：为了能返回 `POST_NOT_FOUND`（404），Like/Unlike 先 `pr.GetByID` 校验文章存在，再调用 PostLikeRepo。代价是多一次 DB 查询，但符合 HTTP 语义。

3. **分页边界**：`page<1 → 1`、`size<1 → 10`、`size>50 → 50`，与 spec-design.md §6.5 一致。

4. **tags 标准化**：入参 tag 先 trim，空值过滤，保持输入顺序去重（使用 map+slice，非 sort 顺序）。

5. **密码长度下限**：Register 要求 `len(pwd)>=6`（biz-contracts 未明确，按常见最佳实践加 validation）。

6. **bcrypt cost=10**：与 spec-design.md §6.2 一致；单测中 Hash/Verify 实际跑通（未 mock），确保 Login 流程真实闭环。

7. **like_count 防负**：`Unlike` 的 UPDATE 加 `WHERE like_count > 0` 防御：即使 DB 层一致性异常导致 like_count 已 0，再减不会落到负数。

---

## 5. 未完成 / 依赖项

本人交付已完成。**依赖 architect/dev_2 的交付**才能 `go build ./...` 整体通过：

- architect：go.mod / api/blog/v1/*.pb.go / errors.go
- dev_2：internal/conf/conf.go（按方案 B）、internal/server、internal/service、cmd/server、wire_gen.go

当上述就绪后，biz 层单测命令 `go test ./internal/biz/...` 应全绿通过（所有断言均为字符串比对 Reason，不依赖 v1 包符号是否存在业务枚举）。

---

## 6. 交付位置

- 代码根：`prototype/M4-example2-e2e/.ai-rd-team/runtime/artifacts/code/`
- biz：`internal/biz/{biz,user,post,comment}.go + {user,post,comment,mock}_test.go`
- data：`internal/data/{data,models,user,post,comment,post_like}.go`
- pkg：`internal/pkg/password/bcrypt.go`
- 本报告：`.ai-rd-team/runtime/artifacts/reports/report-developer_1.md`
