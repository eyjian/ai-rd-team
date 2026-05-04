package biz

import (
	"context"
	"errors"
	"strings"
	"time"

	"blog/internal/pkg/password"

	kerrors "github.com/go-kratos/kratos/v2/errors"
	"github.com/go-kratos/kratos/v2/log"
)

// User 为用户聚合根的领域模型（不含 GORM tag）。
type User struct {
	ID           int64
	Email        string
	PasswordHash string
	Nickname     string
	CreatedAt    time.Time
	UpdatedAt    time.Time
}

// ErrUserNotFound 用于 data 层向 biz 层传递 "未找到" 语义。
// data 层使用 kratos errors 直接返回即可，这里保留为内部哨兵值以便
// biz 层在需要判断时使用 errors.Is。
var ErrUserNotFound = errors.New("user not found")

// UserRepo 由 data 层实现，biz 层只依赖该接口。
type UserRepo interface {
	Create(ctx context.Context, u *User) (*User, error)
	GetByID(ctx context.Context, id int64) (*User, error)
	GetByEmail(ctx context.Context, email string) (*User, error)
}

// TokenIssuer 签发访问令牌的能力，由 internal/pkg/auth.JWTIssuer 实现。
// 方法名 Sign 与 auth.JWTIssuer.Sign(userID int64) (string, error) 签名对齐，
// 这样 developer_2 在 auth 包里不必再加适配代码，直接传 *auth.JWTIssuer 即可。
type TokenIssuer interface {
	Sign(userID int64) (token string, err error)
}

// UserUsecase 用户相关用例。
type UserUsecase struct {
	repo  UserRepo
	auth  TokenIssuer
	log   *log.Helper
}

// NewUserUsecase 构造函数，供 wire 使用。
func NewUserUsecase(repo UserRepo, auth TokenIssuer, logger log.Logger) *UserUsecase {
	return &UserUsecase{
		repo: repo,
		auth: auth,
		log:  log.NewHelper(log.With(logger, "module", "biz/user")),
	}
}

// Register 注册新用户：参数校验 → 规范化 email → bcrypt 散列 → 落库。
func (uc *UserUsecase) Register(ctx context.Context, email, pwd, nickname string) (*User, error) {
	email = strings.ToLower(strings.TrimSpace(email))
	nickname = strings.TrimSpace(nickname)
	if email == "" || !strings.Contains(email, "@") {
		return nil, kerrors.BadRequest("VALIDATION_FAILED", "email is invalid")
	}
	if len(pwd) < 6 {
		return nil, kerrors.BadRequest("VALIDATION_FAILED", "password too short")
	}
	if nickname == "" {
		return nil, kerrors.BadRequest("VALIDATION_FAILED", "nickname is required")
	}

	// 邮箱唯一性由 DB 唯一索引保证，这里做一次预检以返回更友好的错误。
	if existing, err := uc.repo.GetByEmail(ctx, email); err == nil && existing != nil {
		return nil, kerrors.Conflict("USER_EMAIL_EXISTS", "email already registered")
	} else if err != nil && !errors.Is(err, ErrUserNotFound) && !kerrors.IsNotFound(err) {
		return nil, err
	}

	hash, err := password.Hash(pwd)
	if err != nil {
		return nil, err
	}
	u := &User{
		Email:        email,
		PasswordHash: hash,
		Nickname:     nickname,
	}
	created, err := uc.repo.Create(ctx, u)
	if err != nil {
		return nil, err
	}
	created.PasswordHash = "" // 永不对外暴露
	return created, nil
}

// Login 通过邮箱 + 密码换取 JWT。
func (uc *UserUsecase) Login(ctx context.Context, email, pwd string) (string, *User, error) {
	email = strings.ToLower(strings.TrimSpace(email))
	if email == "" || pwd == "" {
		return "", nil, kerrors.BadRequest("VALIDATION_FAILED", "email/password required")
	}

	u, err := uc.repo.GetByEmail(ctx, email)
	if err != nil {
		if errors.Is(err, ErrUserNotFound) || kerrors.IsNotFound(err) {
			return "", nil, kerrors.Unauthorized("INVALID_CREDENTIALS", "email or password incorrect")
		}
		return "", nil, err
	}
	if !password.Verify(u.PasswordHash, pwd) {
		return "", nil, kerrors.Unauthorized("INVALID_CREDENTIALS", "email or password incorrect")
	}
	token, err := uc.auth.Sign(u.ID)
	if err != nil {
		return "", nil, err
	}
	u.PasswordHash = ""
	return token, u, nil
}

// Get 获取指定用户。
func (uc *UserUsecase) Get(ctx context.Context, id int64) (*User, error) {
	u, err := uc.repo.GetByID(ctx, id)
	if err != nil {
		if errors.Is(err, ErrUserNotFound) || kerrors.IsNotFound(err) {
			return nil, kerrors.NotFound("USER_NOT_FOUND", "user not found")
		}
		return nil, err
	}
	u.PasswordHash = ""
	return u, nil
}
