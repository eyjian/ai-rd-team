# biz 层契约（给 developer_1）

> 规则：
> - biz 层**禁止 import gorm**
> - biz 只依赖 repo 接口（data 层实现）
> - 所有错误走 `api/blog/v1` 的 kratos errors（如 `v1.ErrorPostNotFound(...)`）
> - DO 结构体放在 `internal/biz/*.go`
> - ctx 中的 user_id 约定：`biz.UserIDCtxKey`，值类型 int64

---

## 1. Domain Object（DO）

```go
// internal/biz/user.go
type User struct {
    ID           int64
    Email        string
    PasswordHash string
    Nickname     string
    CreatedAt    time.Time
    UpdatedAt    time.Time
}

// internal/biz/post.go
type Post struct {
    ID        int64
    AuthorID  int64
    Title     string
    Body      string
    Tags      []string
    LikeCount int64
    CreatedAt time.Time
    UpdatedAt time.Time
}

// internal/biz/comment.go
type Comment struct {
    ID        int64
    PostID    int64
    AuthorID  int64
    Body      string
    CreatedAt time.Time
}
```

---

## 2. Repo 接口（biz 定义，data 实现）

```go
// internal/biz/user.go
type UserRepo interface {
    Create(ctx context.Context, u *User) (*User, error)
    GetByID(ctx context.Context, id int64) (*User, error)
    GetByEmail(ctx context.Context, email string) (*User, error)
}

// internal/biz/post.go
type PostRepo interface {
    Create(ctx context.Context, p *Post) (*Post, error)
    GetByID(ctx context.Context, id int64) (*Post, error)
    Update(ctx context.Context, p *Post) error
    Delete(ctx context.Context, id int64) error
    List(ctx context.Context, page, size int32, tag string) ([]*Post, int64, error)
}

type PostLikeRepo interface {
    // Add: 新增点赞（已存在则返回 false, nil，同时 posts.like_count 不变；新增则 +1）
    Add(ctx context.Context, postID, userID int64) (added bool, err error)
    // Remove: 取消点赞（不存在返回 false, nil；存在则 -1）
    Remove(ctx context.Context, postID, userID int64) (removed bool, err error)
}

// internal/biz/comment.go
type CommentRepo interface {
    Create(ctx context.Context, c *Comment) (*Comment, error)
    ListByPost(ctx context.Context, postID int64) ([]*Comment, error)
}
```

---

## 3. Usecase 方法签名

```go
// internal/biz/user.go
type UserUsecase struct { repo UserRepo; jwtSecret string; log *log.Helper }

func NewUserUsecase(repo UserRepo, bc *conf.Auth, logger log.Logger) *UserUsecase

func (uc *UserUsecase) Register(ctx context.Context, email, password, nickname string) (*User, error)
func (uc *UserUsecase) Login(ctx context.Context, email, password string) (token string, u *User, err error)
func (uc *UserUsecase) GetByID(ctx context.Context, id int64) (*User, error)

// internal/biz/post.go
type PostUsecase struct { pr PostRepo; lr PostLikeRepo; log *log.Helper }

func NewPostUsecase(pr PostRepo, lr PostLikeRepo, logger log.Logger) *PostUsecase

func (uc *PostUsecase) Create(ctx context.Context, authorID int64, title, body string, tags []string) (*Post, error)
func (uc *PostUsecase) Get(ctx context.Context, id int64) (*Post, error)
func (uc *PostUsecase) List(ctx context.Context, page, size int32, tag string) ([]*Post, int64, error)
func (uc *PostUsecase) Update(ctx context.Context, authorID, id int64, title, body string, tags []string) (*Post, error)
func (uc *PostUsecase) Delete(ctx context.Context, authorID, id int64) error
func (uc *PostUsecase) Like(ctx context.Context, postID, userID int64) error   // 幂等
func (uc *PostUsecase) Unlike(ctx context.Context, postID, userID int64) error // 幂等

// internal/biz/comment.go
type CommentUsecase struct { cr CommentRepo; pr PostRepo; log *log.Helper }

func NewCommentUsecase(cr CommentRepo, pr PostRepo, logger log.Logger) *CommentUsecase

func (uc *CommentUsecase) Create(ctx context.Context, postID, authorID int64, body string) (*Comment, error)
func (uc *CommentUsecase) ListByPost(ctx context.Context, postID int64) ([]*Comment, error)
```

---

## 4. 错误语义（必须用 `v1` 包错误）

- `Register`：邮箱已存在 → `v1.ErrorUserAlreadyExists`；校验失败 → `v1.ErrorValidationFailed`。
- `Login`：邮箱不存在或密码错 → 统一 `v1.ErrorUserCredentialInvalid`。
- `GetByID`：不存在 → `v1.ErrorUserNotFound`。
- `Post.Get/Update/Delete/Like/Unlike/Comment.Create`：`post_id` 不存在 → `v1.ErrorPostNotFound`。
- `Update/Delete`：`authorID != post.AuthorID` → `v1.ErrorPostForbidden`。
- 非业务错误（DB 等）：返回原 error，由 service 兜底转 `v1.ErrorInternalError`。

---

## 5. ProviderSet

```go
// internal/biz/biz.go
var ProviderSet = wire.NewSet(NewUserUsecase, NewPostUsecase, NewCommentUsecase)

// internal/data/data.go
var ProviderSet = wire.NewSet(NewData, NewUserRepo, NewPostRepo, NewCommentRepo, NewPostLikeRepo)
```

---

## 6. conf.Auth（biz 依赖）

```go
// internal/conf/conf.go
type Auth struct {
    JWTSecret string        `yaml:"jwt_secret"`
    Expire    time.Duration `yaml:"expire"` // e.g. 24h
}
```

Bootstrap 结构大致：

```go
type Bootstrap struct {
    Server *Server
    Data   *Data
    Auth   *Auth
}
```

---

## 7. 单测建议（developer_1 必交付）

biz 层 usecase 必须配 mock repo 的单测，覆盖：

- Register 邮箱已存在 / 成功
- Login 密码错 / 成功（token 非空）
- Post.Create / List(tag 过滤) / Update 非作者拒绝
- Like 幂等：连续 Add 两次只 +1
- Comment.Create 当 post 不存在时 `ErrorPostNotFound`
