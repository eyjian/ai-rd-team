# biz 层接口契约（供 developer / developer_2 对齐）

> 架构师：陈架构
> 用途：让 dev 和 dev_2 并行开发时，service 与 biz 间接口不漂移。
> 签名可微调，但**参数/返回值语义**保持不变，有调整请 send_message 同步。

## internal/biz/biz.go

```go
package biz

import "github.com/google/wire"

// ProviderSet 注入到 wire
var ProviderSet = wire.NewSet(
    NewUserUsecase,
    NewPostUsecase,
    NewCommentUsecase,
)
```

---

## internal/biz/user.go

```go
package biz

import (
    "context"
    "time"
)

// User 用户领域实体（不含密码）
type User struct {
    ID        int64
    Email     string
    Nickname  string
    CreatedAt time.Time
}

// UserRepo 用户仓储接口（由 data 层实现）
type UserRepo interface {
    // Create 新增用户，email 冲突返回 ErrEmailExists
    Create(ctx context.Context, email, passwordHash, nickname string) (*User, error)
    // FindByEmail 查询用户（含 password_hash），找不到返回 ErrUserNotFound
    FindByEmail(ctx context.Context, email string) (u *User, passwordHash string, err error)
    // FindByID 按 id 查询，找不到返回 ErrUserNotFound
    FindByID(ctx context.Context, id int64) (*User, error)
}

// 哨兵错误（data 层抛出；usecase 层转成 kratos errors）
var (
    ErrEmailExists  = errors.New("biz: email already exists")
    ErrUserNotFound = errors.New("biz: user not found")
)

// UserUsecase 用户用例
type UserUsecase struct {
    repo     UserRepo
    secret   []byte
    ttl      time.Duration
    log      *log.Helper
}

func NewUserUsecase(repo UserRepo, c *conf.Auth, logger log.Logger) *UserUsecase

// Register 注册（内部做 bcrypt）
func (uc *UserUsecase) Register(ctx context.Context, email, password, nickname string) (*User, error)

// Login 校验密码，签发 JWT，返回 token + 用户
func (uc *UserUsecase) Login(ctx context.Context, email, password string) (token string, ttlSec int64, user *User, err error)

// GetMe 根据 JWT sub（user_id）读取用户
func (uc *UserUsecase) GetMe(ctx context.Context, userID int64) (*User, error)
```

---

## internal/biz/post.go

```go
package biz

type Post struct {
    ID             int64
    AuthorID       int64
    AuthorNickname string
    Title          string
    BodyMarkdown   string
    Tags           []string
    LikesCount     int64
    CreatedAt      time.Time
    UpdatedAt      time.Time
}

type PostRepo interface {
    Create(ctx context.Context, authorID int64, title, body string, tags []string) (*Post, error)
    GetByID(ctx context.Context, id int64) (*Post, error) // not found → ErrPostNotFound
    List(ctx context.Context, page, size int32, tag string) (items []*Post, total int64, err error)
    Update(ctx context.Context, id, authorID int64, title, body string, tags []string) (*Post, error) // 所有权不匹配 → ErrPostNotOwned
    Delete(ctx context.Context, id, authorID int64) error // not found / not owned
}

var (
    ErrPostNotFound = errors.New("biz: post not found")
    ErrPostNotOwned = errors.New("biz: post not owned")
)

type PostUsecase struct { /* repo, log */ }

func NewPostUsecase(repo PostRepo, logger log.Logger) *PostUsecase

func (uc *PostUsecase) Create(ctx context.Context, authorID int64, title, body string, tags []string) (*Post, error)
func (uc *PostUsecase) Get(ctx context.Context, id int64) (*Post, error)
func (uc *PostUsecase) List(ctx context.Context, page, size int32, tag string) ([]*Post, int64, error)
func (uc *PostUsecase) Update(ctx context.Context, id, authorID int64, title, body string, tags []string) (*Post, error)
func (uc *PostUsecase) Delete(ctx context.Context, id, authorID int64) error
```

---

## internal/biz/comment.go

```go
package biz

type Comment struct {
    ID             int64
    PostID         int64
    AuthorID       int64
    AuthorNickname string
    Content        string
    CreatedAt      time.Time
}

type CommentRepo interface {
    Create(ctx context.Context, postID, authorID int64, content string) (*Comment, error)
    List(ctx context.Context, postID int64, page, size int32) (items []*Comment, total int64, err error)

    // Like 插入 post_likes 并 likes_count+1（幂等：已存在时不变）
    // 返回操作后 likes_count 以及当前用户的 liked 状态（始终 true）
    Like(ctx context.Context, postID, userID int64) (likesCount int64, liked bool, err error)
    // Unlike 删除 post_likes 并 likes_count-1（幂等：不存在时不变）
    Unlike(ctx context.Context, postID, userID int64) (likesCount int64, liked bool, err error)
}

type CommentUsecase struct { /* commentRepo, postRepo (校验 post 存在), log */ }

func NewCommentUsecase(cr CommentRepo, pr PostRepo, logger log.Logger) *CommentUsecase

func (uc *CommentUsecase) Create(ctx context.Context, postID, authorID int64, content string) (*Comment, error)
func (uc *CommentUsecase) List(ctx context.Context, postID int64, page, size int32) ([]*Comment, int64, error)
func (uc *CommentUsecase) Like(ctx context.Context, postID, userID int64) (int64, bool, error)
func (uc *CommentUsecase) Unlike(ctx context.Context, postID, userID int64) (int64, bool, error)
```

---

## service 层取 user_id 的约定（给 developer_2）

```go
// internal/pkg/auth/auth.go
package auth

import (
    "context"
    "strconv"

    jwtv4 "github.com/golang-jwt/jwt/v4"
    "github.com/go-kratos/kratos/v2/middleware/auth/jwt"
    "github.com/go-kratos/kratos/v2/errors"
)

// GetUserID 从 JWT claims 取 sub，转 int64
func GetUserID(ctx context.Context) (int64, error) {
    claims, ok := jwt.FromContext(ctx)
    if !ok {
        return 0, errors.Unauthorized("USER_UNAUTHORIZED", "missing token")
    }
    mc, ok := claims.(jwtv4.MapClaims)
    if !ok {
        return 0, errors.Unauthorized("USER_UNAUTHORIZED", "invalid claims")
    }
    sub, _ := mc["sub"].(string)
    id, err := strconv.ParseInt(sub, 10, 64)
    if err != nil || id <= 0 {
        return 0, errors.Unauthorized("USER_UNAUTHORIZED", "invalid subject")
    }
    return id, nil
}
```

## 错误映射（service 层负责 biz error → kratos errors）

| biz error        | kratos                                           |
| ---------------- | ------------------------------------------------ |
| ErrEmailExists   | `errors.Conflict("USER_EMAIL_EXISTS", ...)`      |
| ErrUserNotFound  | 登录时 → `errors.Unauthorized("USER_CRED_INVALID", ...)`；GetMe → `errors.Unauthorized("USER_UNAUTHORIZED", ...)` |
| 密码不匹配       | `errors.Unauthorized("USER_CRED_INVALID", ...)`  |
| ErrPostNotFound  | `errors.NotFound("POST_NOT_FOUND", ...)`         |
| ErrPostNotOwned  | `errors.Forbidden("POST_NOT_OWNED", ...)`        |
