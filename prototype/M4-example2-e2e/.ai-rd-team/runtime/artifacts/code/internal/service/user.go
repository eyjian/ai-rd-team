package service

import (
	"context"

	v1 "blog/api/blog/v1"
	"blog/internal/biz"
	"blog/internal/pkg/auth"

	"github.com/go-kratos/kratos/v2/log"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// UserService 用户协议层
type UserService struct {
	v1.UnimplementedUserServer

	uc  *biz.UserUsecase
	log *log.Helper
}

// NewUserService 构造
func NewUserService(uc *biz.UserUsecase, logger log.Logger) *UserService {
	return &UserService{uc: uc, log: log.NewHelper(logger)}
}

func userToReply(u *biz.User) *v1.UserReply {
	if u == nil {
		return nil
	}
	return &v1.UserReply{
		Id:        u.ID,
		Email:     u.Email,
		Nickname:  u.Nickname,
		CreatedAt: timestamppb.New(u.CreatedAt),
	}
}

// Register POST /v1/users
func (s *UserService) Register(ctx context.Context, req *v1.RegisterRequest) (*v1.UserReply, error) {
	if req.Email == "" || req.Password == "" {
		return nil, v1.ErrorValidationFailed("email/password required")
	}
	u, err := s.uc.Register(ctx, req.Email, req.Password, req.Nickname)
	if err != nil {
		return nil, err
	}
	return userToReply(u), nil
}

// Login POST /v1/auth/login
func (s *UserService) Login(ctx context.Context, req *v1.LoginRequest) (*v1.LoginReply, error) {
	if req.Email == "" || req.Password == "" {
		return nil, v1.ErrorValidationFailed("email/password required")
	}
	token, u, err := s.uc.Login(ctx, req.Email, req.Password)
	if err != nil {
		return nil, err
	}
	return &v1.LoginReply{Token: token, User: userToReply(u)}, nil
}

// GetMe GET /v1/users/me（需 JWT）
func (s *UserService) GetMe(ctx context.Context, _ *v1.GetMeRequest) (*v1.UserReply, error) {
	uid, err := auth.MustUserIDFromContext(ctx)
	if err != nil {
		return nil, err
	}
	u, err := s.uc.GetByID(ctx, uid)
	if err != nil {
		return nil, err
	}
	return userToReply(u), nil
}
