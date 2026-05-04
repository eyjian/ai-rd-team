package biz

import (
	"context"
	"errors"
	"strings"
	"time"

	v1 "blog/api/blog/v1"
	"blog/internal/conf"
	"blog/internal/pkg/password"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/golang-jwt/jwt/v5"
)

// User 为用户 DO。
type User struct {
	ID           int64
	Email        string
	PasswordHash string
	Nickname     string
	CreatedAt    time.Time
	UpdatedAt    time.Time
}

// UserRepo 由 data 层实现。
type UserRepo interface {
	Create(ctx context.Context, u *User) (*User, error)
	GetByID(ctx context.Context, id int64) (*User, error)
	GetByEmail(ctx context.Context, email string) (*User, error)
}

// ErrUserNotFound 是 data 层在用户不存在时应返回的哨兵错误。
// biz 层据此转换为 v1.ErrorUserNotFound。
var ErrUserNotFound = errors.New("biz: user not found")

// UserUsecase 封装用户相关用例。
type UserUsecase struct {
	repo      UserRepo
	jwtSecret string
	jwtExpire time.Duration
	log       *log.Helper
}

// NewUserUsecase 构造 UserUsecase。
func NewUserUsecase(repo UserRepo, auth *conf.Auth, logger log.Logger) *UserUsecase {
	return &UserUsecase{
		repo:      repo,
		jwtSecret: auth.JWTSecret,
		jwtExpire: auth.Expire,
		log:       log.NewHelper(log.With(logger, "module", "biz/user")),
	}
}

// Register 注册新用户：校验入参、检查邮箱唯一、bcrypt 加密密码并落库。
func (uc *UserUsecase) Register(ctx context.Context, email, pwd, nickname string) (*User, error) {
	email = strings.TrimSpace(strings.ToLower(email))
	nickname = strings.TrimSpace(nickname)
	if email == "" || !strings.Contains(email, "@") {
		return nil, v1.ErrorValidationFailed("email invalid")
	}
	if len(pwd) < 6 {
		return nil, v1.ErrorValidationFailed("password too short (>=6)")
	}
	if nickname == "" {
		return nil, v1.ErrorValidationFailed("nickname required")
	}

	// 邮箱唯一性检查
	if existing, err := uc.repo.GetByEmail(ctx, email); err == nil && existing != nil {
		return nil, v1.ErrorUserAlreadyExists("email %s already registered", email)
	} else if err != nil && !errors.Is(err, ErrUserNotFound) {
		return nil, err
	}

	hash, err := password.Hash(pwd)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("bcrypt hash failed: %v", err)
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
	return created, nil
}

// Login 登录：校验密码并签发 JWT。
// 错误语义：邮箱不存在或密码错误，统一返回 ErrorUserCredentialInvalid（不暴露细节）。
func (uc *UserUsecase) Login(ctx context.Context, email, pwd string) (string, *User, error) {
	email = strings.TrimSpace(strings.ToLower(email))
	if email == "" || pwd == "" {
		return "", nil, v1.ErrorUserCredentialInvalid("invalid credential")
	}

	u, err := uc.repo.GetByEmail(ctx, email)
	if err != nil {
		if errors.Is(err, ErrUserNotFound) {
			return "", nil, v1.ErrorUserCredentialInvalid("invalid credential")
		}
		return "", nil, err
	}
	if u == nil {
		return "", nil, v1.ErrorUserCredentialInvalid("invalid credential")
	}

	if !password.Verify(u.PasswordHash, pwd) {
		return "", nil, v1.ErrorUserCredentialInvalid("invalid credential")
	}

	token, err := uc.signToken(u)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("sign jwt failed: %v", err)
		return "", nil, err
	}
	return token, u, nil
}

// GetByID 按 ID 查询用户。
func (uc *UserUsecase) GetByID(ctx context.Context, id int64) (*User, error) {
	if id <= 0 {
		return nil, v1.ErrorValidationFailed("id must be positive")
	}
	u, err := uc.repo.GetByID(ctx, id)
	if err != nil {
		if errors.Is(err, ErrUserNotFound) {
			return nil, v1.ErrorUserNotFound("user %d not found", id)
		}
		return nil, err
	}
	if u == nil {
		return nil, v1.ErrorUserNotFound("user %d not found", id)
	}
	return u, nil
}

// signToken 签发 JWT（HS256）。
func (uc *UserUsecase) signToken(u *User) (string, error) {
	now := time.Now()
	exp := uc.jwtExpire
	if exp <= 0 {
		exp = 24 * time.Hour
	}
	claims := jwt.MapClaims{
		"user_id": u.ID,
		"email":   u.Email,
		"iat":     now.Unix(),
		"exp":     now.Add(exp).Unix(),
	}
	tok := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return tok.SignedString([]byte(uc.jwtSecret))
}
