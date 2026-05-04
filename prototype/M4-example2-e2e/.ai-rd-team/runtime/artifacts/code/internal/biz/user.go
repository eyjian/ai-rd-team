package biz

import (
	"context"
	"errors"
	"strconv"
	"time"

	"blog/internal/conf"

	"github.com/go-kratos/kratos/v2/log"
	jwtv4 "github.com/golang-jwt/jwt/v4"
	"golang.org/x/crypto/bcrypt"
)

// bcryptCost 密码哈希 cost，按架构文档规定使用 10。
const bcryptCost = 10

// 用户相关的哨兵错误。service 层负责将其映射为 kratos errors。
var (
	// ErrEmailExists 邮箱已被注册。对应 USER_EMAIL_EXISTS / 409。
	ErrEmailExists = errors.New("biz: email already exists")
	// ErrUserNotFound 用户不存在。登录时对应 USER_CRED_INVALID / 401；
	// GetMe 时对应 USER_UNAUTHORIZED / 401。
	ErrUserNotFound = errors.New("biz: user not found")
	// ErrInvalidCredential 邮箱或密码错误（bcrypt 校验失败）。
	// 对应 USER_CRED_INVALID / 401。
	ErrInvalidCredential = errors.New("biz: invalid credential")
)

// User 用户领域实体，不包含密码。
type User struct {
	ID        int64
	Email     string
	Nickname  string
	CreatedAt time.Time
}

// UserRepo 用户仓储接口，由 internal/data 层通过 GORM 实现。
type UserRepo interface {
	// Create 新建用户。若 email 已存在则返回 ErrEmailExists。
	Create(ctx context.Context, email, passwordHash, nickname string) (*User, error)
	// FindByEmail 按邮箱查询用户并返回其 password_hash。
	// 找不到返回 ErrUserNotFound。
	FindByEmail(ctx context.Context, email string) (u *User, passwordHash string, err error)
	// FindByID 按主键查询。找不到返回 ErrUserNotFound。
	FindByID(ctx context.Context, id int64) (*User, error)
}

// UserUsecase 用户用例，封装注册/登录/取当前用户信息。
type UserUsecase struct {
	repo   UserRepo
	secret []byte
	ttl    time.Duration
	log    *log.Helper
}

// NewUserUsecase 构造 UserUsecase。
// 参数 c 中 jwt_secret / jwt_ttl_seconds 用于签发 JWT。
func NewUserUsecase(repo UserRepo, c *conf.Auth, logger log.Logger) *UserUsecase {
	ttl := time.Duration(c.GetJwtTtlSeconds()) * time.Second
	if ttl <= 0 {
		ttl = 7 * 24 * time.Hour
	}
	return &UserUsecase{
		repo:   repo,
		secret: []byte(c.GetJwtSecret()),
		ttl:    ttl,
		log:    log.NewHelper(log.With(logger, "module", "biz/user")),
	}
}

// Register 注册新用户：bcrypt(cost=10) 哈希密码后写库。
// email 已存在返回 ErrEmailExists；其他错误原样返回。
func (uc *UserUsecase) Register(ctx context.Context, email, password, nickname string) (*User, error) {
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcryptCost)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("bcrypt generate: %v", err)
		return nil, err
	}
	u, err := uc.repo.Create(ctx, email, string(hash), nickname)
	if err != nil {
		return nil, err
	}
	uc.log.WithContext(ctx).Infof("user registered id=%d email=%s", u.ID, u.Email)
	return u, nil
}

// Login 校验密码，成功时签发 JWT。
// 账号不存在或密码错误统一返回 ErrInvalidCredential，避免泄露账号是否存在。
// 返回 token、ttl 秒数、用户实体。
func (uc *UserUsecase) Login(ctx context.Context, email, password string) (string, int64, *User, error) {
	u, hash, err := uc.repo.FindByEmail(ctx, email)
	if err != nil {
		if errors.Is(err, ErrUserNotFound) {
			return "", 0, nil, ErrInvalidCredential
		}
		return "", 0, nil, err
	}
	if err := bcrypt.CompareHashAndPassword([]byte(hash), []byte(password)); err != nil {
		return "", 0, nil, ErrInvalidCredential
	}
	token, err := uc.signToken(u.ID)
	if err != nil {
		uc.log.WithContext(ctx).Errorf("sign jwt: %v", err)
		return "", 0, nil, err
	}
	return token, int64(uc.ttl.Seconds()), u, nil
}

// GetMe 根据 JWT sub 读取当前用户。
// 找不到返回 ErrUserNotFound（service 层映射为 401 USER_UNAUTHORIZED）。
func (uc *UserUsecase) GetMe(ctx context.Context, userID int64) (*User, error) {
	return uc.repo.FindByID(ctx, userID)
}

// signToken 生成 HS256 JWT，claims: sub=userID(string), exp=now+ttl, iat=now。
func (uc *UserUsecase) signToken(userID int64) (string, error) {
	now := time.Now()
	claims := jwtv4.MapClaims{
		"sub": strconv.FormatInt(userID, 10),
		"iat": now.Unix(),
		"exp": now.Add(uc.ttl).Unix(),
	}
	token := jwtv4.NewWithClaims(jwtv4.SigningMethodHS256, claims)
	return token.SignedString(uc.secret)
}
