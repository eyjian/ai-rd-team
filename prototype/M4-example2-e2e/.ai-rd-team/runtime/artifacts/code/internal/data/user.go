package data

import (
	"context"
	"errors"

	"blog/internal/biz"

	"github.com/go-kratos/kratos/v2/log"
	"gorm.io/gorm"
)

type userRepo struct {
	data *Data
	log  *log.Helper
}

// NewUserRepo 构造 UserRepo 实现。
func NewUserRepo(d *Data, logger log.Logger) biz.UserRepo {
	return &userRepo{
		data: d,
		log:  log.NewHelper(log.With(logger, "module", "data/user")),
	}
}

func toUserDO(po *userPO) *biz.User {
	if po == nil {
		return nil
	}
	return &biz.User{
		ID:           po.ID,
		Email:        po.Email,
		PasswordHash: po.PasswordHash,
		Nickname:     po.Nickname,
		CreatedAt:    po.CreatedAt,
		UpdatedAt:    po.UpdatedAt,
	}
}

func (r *userRepo) Create(ctx context.Context, u *biz.User) (*biz.User, error) {
	po := &userPO{
		Email:        u.Email,
		PasswordHash: u.PasswordHash,
		Nickname:     u.Nickname,
	}
	if err := r.data.db.WithContext(ctx).Create(po).Error; err != nil {
		return nil, err
	}
	return toUserDO(po), nil
}

func (r *userRepo) GetByID(ctx context.Context, id int64) (*biz.User, error) {
	var po userPO
	err := r.data.db.WithContext(ctx).First(&po, "id = ?", id).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, biz.ErrUserNotFound
		}
		return nil, err
	}
	return toUserDO(&po), nil
}

func (r *userRepo) GetByEmail(ctx context.Context, email string) (*biz.User, error) {
	var po userPO
	err := r.data.db.WithContext(ctx).First(&po, "email = ?", email).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, biz.ErrUserNotFound
		}
		return nil, err
	}
	return toUserDO(&po), nil
}
