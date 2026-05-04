package data

import (
	"context"
	"errors"
	"time"

	"blog/internal/biz"

	kerrors "github.com/go-kratos/kratos/v2/errors"
	"github.com/go-kratos/kratos/v2/log"
	"gorm.io/gorm"
)

// userPO 为 users 表的 GORM 映射，仅在 data 包内可见。
type userPO struct {
	ID           int64     `gorm:"column:id;primaryKey;autoIncrement"`
	Email        string    `gorm:"column:email;size:255;not null;uniqueIndex"`
	PasswordHash string    `gorm:"column:password_hash;size:255;not null"`
	Nickname     string    `gorm:"column:nickname;size:100;not null"`
	CreatedAt    time.Time `gorm:"column:created_at;autoCreateTime"`
	UpdatedAt    time.Time `gorm:"column:updated_at;autoUpdateTime"`
}

func (userPO) TableName() string { return "users" }

func (po *userPO) toBiz() *biz.User {
	return &biz.User{
		ID:           po.ID,
		Email:        po.Email,
		PasswordHash: po.PasswordHash,
		Nickname:     po.Nickname,
		CreatedAt:    po.CreatedAt,
		UpdatedAt:    po.UpdatedAt,
	}
}

type userRepo struct {
	data *Data
	log  *log.Helper
}

// NewUserRepo 实现 biz.UserRepo。
func NewUserRepo(d *Data, logger log.Logger) biz.UserRepo {
	return &userRepo{data: d, log: log.NewHelper(log.With(logger, "module", "data/user"))}
}

func (r *userRepo) Create(ctx context.Context, u *biz.User) (*biz.User, error) {
	po := &userPO{
		Email:        u.Email,
		PasswordHash: u.PasswordHash,
		Nickname:     u.Nickname,
	}
	if err := r.data.DB.WithContext(ctx).Create(po).Error; err != nil {
		// 邮箱唯一索引冲突 → 业务错误
		if isUniqueViolation(err) {
			return nil, kerrors.Conflict("USER_EMAIL_EXISTS", "email already registered")
		}
		return nil, err
	}
	return po.toBiz(), nil
}

func (r *userRepo) GetByID(ctx context.Context, id int64) (*biz.User, error) {
	var po userPO
	if err := r.data.DB.WithContext(ctx).Where("id = ?", id).First(&po).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, biz.ErrUserNotFound
		}
		return nil, err
	}
	return po.toBiz(), nil
}

func (r *userRepo) GetByEmail(ctx context.Context, email string) (*biz.User, error) {
	var po userPO
	if err := r.data.DB.WithContext(ctx).Where("email = ?", email).First(&po).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, biz.ErrUserNotFound
		}
		return nil, err
	}
	return po.toBiz(), nil
}
