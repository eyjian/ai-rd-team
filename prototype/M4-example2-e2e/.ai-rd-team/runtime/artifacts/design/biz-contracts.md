# BlogAPI biz 层契约

> Owner: architect
> 配套：`spec-design.md`（架构） + `data-interfaces.yaml`（结构化契约，机器可读）
> 本文档用于人读，聚焦 biz/data 边界。**字段/签名如与 `data-interfaces.yaml` 冲突，以 yaml 为准。**

---

## 1. 领域模型（`internal/biz` 纯 struct，无 gorm tag）

```go
package biz

import "time"

type User struct {
    ID           int64
    Email        string  // 入库前 strings.ToLower
    PasswordHash string  // 对外返回时必须置空
    Nickname     string
    CreatedAt    time.Time
    UpdatedAt    time.Time
}

type Post struct {
    ID           int64
    AuthorID     int64
    Title        string
    BodyMarkdown string
    Tags         []string  // 非 nil；无标签则 []string{}
    LikesCount   int64
    CreatedAt    time.Time
    UpdatedAt    time.Time
}

type Comment struct {
    ID        int64
    PostID    int64
    AuthorID  int64
    Content   string
    CreatedAt time.Time
}
```

> **data 层在返回前必须把 PO 映射为上述 biz 模型。** 禁止把 GORM 的 `*gorm.Model` 或 PO 结构体泄漏到 biz。

---

## 2. Repo 接口（biz 定义，data 实现）

```go
package biz

import "context"

type UserRepo interface {
    Create(ctx context.Context, u *User) (*User, error)
    GetByID(ctx context.Context, id int64) (*User, error)
    GetByEmail(ctx context.Context, email string) (*User, error)
}

type PostRepo interface {
    Create(ctx context.Context, p *Post) (*Post, error)
    GetByID(ctx context.Context, id int64) (*Post, error)
    Update(ctx context.Context, p *Post) (*Post, error)
    Delete(ctx context.Context, id int64) error
    // tag 为空字符串表示不过滤；返回 total 用于分页
    List(ctx context.Context, page, size int32, tag string) ([]*Post, int64, error)

    // AddLike 返回 added=true 表示本次确实插入了新记录并已把 likes_count+1
    // added=false 表示用户已点过赞（幂等 no-op）
    AddLike(ctx context.Context, postID, userID int64) (added bool, err error)
    // 对称地，removed=true 表示本次确实删除了记录并已把 likes_count-1
    RemoveLike(ctx context.Context, postID, userID int64) (removed bool, err error)
}

type CommentRepo interface {
    Create(ctx context.Context, c *Comment) (*Comment, error)
    ListByPost(ctx context.Context, postID int64, page, size int32) ([]*Comment, int64, error)
}
```

### 约束

- Repo 方法**只接受 biz 模型**；返回时字段（`PasswordHash` 除外）必须填充。
- `List*` 的分页参数：`page` 从 1 起，`size` ≤ 100；由 usecase 做边界校正，Repo 只负责按传入值 LIMIT/OFFSET。
- DB 错误统一包装为 `errors.New(500, "INTERNAL", msg)`；业务语义错误（如未找到）由 usecase 根据 `gorm.ErrRecordNotFound` 翻译。

---

## 3. Usecase（业务规则）

```go
// UserUsecase
func NewUserUsecase(repo UserRepo, issuer *auth.JWTIssuer, logger log.Logger) *UserUsecase

(u *UserUsecase) Register(ctx, email, password, nickname string) (*User, error)
  - 校验 email 格式、密码长度≥6、nickname 1..50
  - email 已存在 → errors.Conflict("USER_EMAIL_EXISTS", ...)
  - bcrypt Hash（cost 来自配置，测试环境传 4）
  - 返回的 User.PasswordHash 必须置空

(u *UserUsecase) Login(ctx, email, password string) (token string, user *User, err error)
  - 找不到 or 密码错 → errors.Unauthorized("INVALID_CREDENTIALS", ...)
  - 签 JWT (sub=user.ID, exp=now+AccessTTL)
  - user.PasswordHash 必须置空

(u *UserUsecase) Get(ctx, id int64) (*User, error)
  - 不存在 → errors.NotFound("USER_NOT_FOUND", ...)

// PostUsecase
(u *PostUsecase) Create(ctx, authorID, title, body, tags) (*Post, error)
  - title 1..200；body 非空；tags 去重 + 小写 + len ≤ 10；每个 tag 1..30
(u *PostUsecase) Update(ctx, operatorID, postID, title, body, tags) (*Post, error)
  - 先 GetByID；post.AuthorID != operatorID → errors.Forbidden("FORBIDDEN", ...)
(u *PostUsecase) Delete(ctx, operatorID, postID) error
  - 同 Update 的权限校验；成功后依赖 ON DELETE CASCADE 清理 comments/post_likes
(u *PostUsecase) Like(ctx, postID, userID) error
  - 幂等：Repo 返回 added=false 时也视为成功
(u *PostUsecase) Unlike(ctx, postID, userID) error
  - 幂等：removed=false 时也视为成功

// CommentUsecase
(u *CommentUsecase) Create(ctx, postID, authorID, content) (*Comment, error)
  - content 1..2000；postID 不存在 → POST_NOT_FOUND
(u *CommentUsecase) ListByPost(ctx, postID, page, size) ([]*Comment, int64, error)
```

---

## 4. 统一错误码（和 service 层直通）

| reason                | 层       | HTTP | 触发点                                  |
| --------------------- | -------- | ---- | --------------------------------------- |
| VALIDATION_FAILED     | biz/svc  | 400  | 参数非法                                |
| UNAUTHORIZED          | middleware | 401 | 无 token / token 过期                   |
| INVALID_CREDENTIALS   | biz      | 401  | 登录失败                                |
| FORBIDDEN             | biz      | 403  | 非作者改/删文章                         |
| USER_NOT_FOUND        | biz      | 404  | GetByID 未命中                          |
| POST_NOT_FOUND        | biz      | 404  | 文章查/改/删/评论/点赞时未命中          |
| COMMENT_NOT_FOUND     | biz      | 404  | 预留（本期无单条查询）                  |
| USER_EMAIL_EXISTS     | biz      | 409  | 注册冲突                                |

**用法**：

```go
import kerr "github.com/go-kratos/kratos/v2/errors"

return nil, kerr.Conflict("USER_EMAIL_EXISTS", "email already registered")
return nil, kerr.Forbidden("FORBIDDEN", "only author can update this post")
return nil, kerr.NotFound("POST_NOT_FOUND", "post %d not found", id)
return nil, kerr.BadRequest("VALIDATION_FAILED", "title length must be 1..200")
```

---

## 5. ProviderSet（wire）

```go
// internal/biz/biz.go
var ProviderSet = wire.NewSet(
    NewUserUsecase,
    NewPostUsecase,
    NewCommentUsecase,
)

// internal/data/data.go
var ProviderSet = wire.NewSet(
    NewData,
    NewUserRepo,   // 返回 biz.UserRepo
    NewPostRepo,
    NewCommentRepo,
)
```

data.NewData 签名：

```go
func NewData(c *conf.Data, logger log.Logger) (*Data, func(), error)
```

cleanup 函数关闭数据库连接。

---

## 6. 事务封装（data 内部工具）

```go
// internal/data/data.go
type Data struct{ db *gorm.DB }

// contextKey 用于把 tx 注入 context
type txKey struct{}

func (d *Data) withTx(ctx context.Context) *gorm.DB {
    if tx, ok := ctx.Value(txKey{}).(*gorm.DB); ok {
        return tx
    }
    return d.db.WithContext(ctx)
}

func (d *Data) Transaction(ctx context.Context, fn func(context.Context) error) error {
    return d.db.Transaction(func(tx *gorm.DB) error {
        return fn(context.WithValue(ctx, txKey{}, tx))
    })
}
```

**谁用事务**：

- `PostRepo.AddLike / RemoveLike`：内部自己 `db.Transaction`（本 Repo 内两条 SQL 同事务即可，无需 usecase 介入）。
- `PostUsecase.Delete`：依赖 DB 级 CASCADE，不需要显式事务。

---

## 7. 验收（developer_1 自测清单）

- [ ] `go build ./internal/biz/... ./internal/data/...` 通过
- [ ] `biz` 包不 import `gorm.io/gorm`、不 import `github.com/go-kratos/kratos/v2/transport/*`
- [ ] `data` 包不 import 任何 `internal/service` 或 `internal/server`
- [ ] 所有 Repo 方法都有 `err == gorm.ErrRecordNotFound` 的分支（在 biz 层转成领域错误）
- [ ] 幂等 Like/Unlike 连续调两次，第二次不产生错误
