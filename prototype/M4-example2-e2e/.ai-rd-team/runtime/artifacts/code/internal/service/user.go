package service

import (
	"context"

	v1 "blog/api/blog/v1"
	"blog/internal/biz"
	"blog/internal/pkg/auth"

	"google.golang.org/protobuf/types/known/timestamppb"
)

// UserService implements v1.UserServiceServer by delegating to biz.UserUsecase.
type UserService struct {
	v1.UnimplementedUserServiceServer
	uc *biz.UserUsecase
}

// NewUserService constructor.
func NewUserService(uc *biz.UserUsecase) *UserService {
	return &UserService{uc: uc}
}

func (s *UserService) Register(ctx context.Context, req *v1.RegisterRequest) (*v1.User, error) {
	u, err := s.uc.Register(ctx, req.GetEmail(), req.GetPassword(), req.GetNickname())
	if err != nil {
		return nil, err
	}
	return toPBUser(u), nil
}

func (s *UserService) Login(ctx context.Context, req *v1.LoginRequest) (*v1.LoginReply, error) {
	token, u, err := s.uc.Login(ctx, req.GetEmail(), req.GetPassword())
	if err != nil {
		return nil, err
	}
	return &v1.LoginReply{Token: token, User: toPBUser(u)}, nil
}

func (s *UserService) GetMe(ctx context.Context, _ *v1.GetMeRequest) (*v1.User, error) {
	uid, ok := auth.UserIDFromContext(ctx)
	if !ok {
		return nil, auth.ErrUnauthorized(v1.ReasonUnauthorized)
	}
	u, err := s.uc.Get(ctx, uid)
	if err != nil {
		return nil, err
	}
	return toPBUser(u), nil
}

func toPBUser(u *biz.User) *v1.User {
	if u == nil {
		return nil
	}
	return &v1.User{
		Id:        u.ID,
		Email:     u.Email,
		Nickname:  u.Nickname,
		CreatedAt: timestamppb.New(u.CreatedAt),
		UpdatedAt: timestamppb.New(u.UpdatedAt),
	}
}
