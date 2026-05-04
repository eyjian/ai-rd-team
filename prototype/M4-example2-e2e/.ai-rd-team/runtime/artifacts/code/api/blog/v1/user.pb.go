// Code equivalent to protoc-gen-go + protoc-gen-go-http output (hand-written for prototype).
package v1

import (
	"context"

	"github.com/go-kratos/kratos/v2/transport/http"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// --- Messages ---

type RegisterRequest struct {
	Email    string `json:"email,omitempty"`
	Password string `json:"password,omitempty"`
	Nickname string `json:"nickname,omitempty"`
}

type LoginRequest struct {
	Email    string `json:"email,omitempty"`
	Password string `json:"password,omitempty"`
}

type LoginReply struct {
	Token string     `json:"token,omitempty"`
	User  *UserReply `json:"user,omitempty"`
}

type GetMeRequest struct{}

type UserReply struct {
	Id        int64                  `json:"id,omitempty"`
	Email     string                 `json:"email,omitempty"`
	Nickname  string                 `json:"nickname,omitempty"`
	CreatedAt *timestamppb.Timestamp `json:"created_at,omitempty"`
}

// --- Service interface ---

type UserServer interface {
	Register(context.Context, *RegisterRequest) (*UserReply, error)
	Login(context.Context, *LoginRequest) (*LoginReply, error)
	GetMe(context.Context, *GetMeRequest) (*UserReply, error)
}

type UnimplementedUserServer struct{}

func (UnimplementedUserServer) Register(context.Context, *RegisterRequest) (*UserReply, error) {
	return nil, ErrorInternalError("method Register not implemented")
}
func (UnimplementedUserServer) Login(context.Context, *LoginRequest) (*LoginReply, error) {
	return nil, ErrorInternalError("method Login not implemented")
}
func (UnimplementedUserServer) GetMe(context.Context, *GetMeRequest) (*UserReply, error) {
	return nil, ErrorInternalError("method GetMe not implemented")
}

// --- HTTP registration ---

const OperationUserRegister = "/blog.v1.User/Register"
const OperationUserLogin = "/blog.v1.User/Login"
const OperationUserGetMe = "/blog.v1.User/GetMe"

func RegisterUserHTTPServer(s *http.Server, srv UserServer) {
	r := s.Route("/")
	r.POST("/v1/users", _User_Register0_HTTP_Handler(srv))
	r.POST("/v1/auth/login", _User_Login0_HTTP_Handler(srv))
	r.GET("/v1/users/me", _User_GetMe0_HTTP_Handler(srv))
}

func _User_Register0_HTTP_Handler(srv UserServer) func(http.Context) error {
	return func(ctx http.Context) error {
		var in RegisterRequest
		if err := ctx.Bind(&in); err != nil {
			return err
		}
		http.SetOperation(ctx, OperationUserRegister)
		h := ctx.Middleware(func(c context.Context, req any) (any, error) {
			return srv.Register(c, req.(*RegisterRequest))
		})
		out, err := h(ctx, &in)
		if err != nil {
			return err
		}
		reply, _ := out.(*UserReply)
		return ctx.Result(200, reply)
	}
}

func _User_Login0_HTTP_Handler(srv UserServer) func(http.Context) error {
	return func(ctx http.Context) error {
		var in LoginRequest
		if err := ctx.Bind(&in); err != nil {
			return err
		}
		http.SetOperation(ctx, OperationUserLogin)
		h := ctx.Middleware(func(c context.Context, req any) (any, error) {
			return srv.Login(c, req.(*LoginRequest))
		})
		out, err := h(ctx, &in)
		if err != nil {
			return err
		}
		reply, _ := out.(*LoginReply)
		return ctx.Result(200, reply)
	}
}

func _User_GetMe0_HTTP_Handler(srv UserServer) func(http.Context) error {
	return func(ctx http.Context) error {
		var in GetMeRequest
		http.SetOperation(ctx, OperationUserGetMe)
		h := ctx.Middleware(func(c context.Context, req any) (any, error) {
			return srv.GetMe(c, req.(*GetMeRequest))
		})
		out, err := h(ctx, &in)
		if err != nil {
			return err
		}
		reply, _ := out.(*UserReply)
		return ctx.Result(200, reply)
	}
}
