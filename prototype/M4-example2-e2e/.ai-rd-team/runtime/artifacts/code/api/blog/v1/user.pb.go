// Code hand-written by architect (minimal subset of protoc-gen-go output).
// Source: user.proto

package v1

import (
	context "context"

	"google.golang.org/protobuf/reflect/protoreflect"
	timestamppb "google.golang.org/protobuf/types/known/timestamppb"
)

// ----------------------------- Messages ------------------------------------

type User struct {
	Id        int64                  `json:"id,omitempty"`
	Email     string                 `json:"email,omitempty"`
	Nickname  string                 `json:"nickname,omitempty"`
	CreatedAt *timestamppb.Timestamp `json:"created_at,omitempty"`
	UpdatedAt *timestamppb.Timestamp `json:"updated_at,omitempty"`
}

func (m *User) Reset()                          { *m = User{} }
func (m *User) String() string                  { return "User" }
func (*User) ProtoMessage()                     {}
func (m *User) ProtoReflect() protoreflect.Message { return nil }

func (m *User) GetId() int64 {
	if m == nil {
		return 0
	}
	return m.Id
}
func (m *User) GetEmail() string {
	if m == nil {
		return ""
	}
	return m.Email
}
func (m *User) GetNickname() string {
	if m == nil {
		return ""
	}
	return m.Nickname
}
func (m *User) GetCreatedAt() *timestamppb.Timestamp {
	if m == nil {
		return nil
	}
	return m.CreatedAt
}
func (m *User) GetUpdatedAt() *timestamppb.Timestamp {
	if m == nil {
		return nil
	}
	return m.UpdatedAt
}

type RegisterRequest struct {
	Email    string `json:"email,omitempty"`
	Password string `json:"password,omitempty"`
	Nickname string `json:"nickname,omitempty"`
}

func (m *RegisterRequest) Reset()                          { *m = RegisterRequest{} }
func (m *RegisterRequest) String() string                  { return "RegisterRequest" }
func (*RegisterRequest) ProtoMessage()                     {}
func (m *RegisterRequest) ProtoReflect() protoreflect.Message { return nil }

func (m *RegisterRequest) GetEmail() string {
	if m == nil {
		return ""
	}
	return m.Email
}
func (m *RegisterRequest) GetPassword() string {
	if m == nil {
		return ""
	}
	return m.Password
}
func (m *RegisterRequest) GetNickname() string {
	if m == nil {
		return ""
	}
	return m.Nickname
}

type LoginRequest struct {
	Email    string `json:"email,omitempty"`
	Password string `json:"password,omitempty"`
}

func (m *LoginRequest) Reset()                          { *m = LoginRequest{} }
func (m *LoginRequest) String() string                  { return "LoginRequest" }
func (*LoginRequest) ProtoMessage()                     {}
func (m *LoginRequest) ProtoReflect() protoreflect.Message { return nil }

func (m *LoginRequest) GetEmail() string {
	if m == nil {
		return ""
	}
	return m.Email
}
func (m *LoginRequest) GetPassword() string {
	if m == nil {
		return ""
	}
	return m.Password
}

type LoginReply struct {
	Token string `json:"token,omitempty"`
	User  *User  `json:"user,omitempty"`
}

func (m *LoginReply) Reset()                          { *m = LoginReply{} }
func (m *LoginReply) String() string                  { return "LoginReply" }
func (*LoginReply) ProtoMessage()                     {}
func (m *LoginReply) ProtoReflect() protoreflect.Message { return nil }

func (m *LoginReply) GetToken() string {
	if m == nil {
		return ""
	}
	return m.Token
}
func (m *LoginReply) GetUser() *User {
	if m == nil {
		return nil
	}
	return m.User
}

type GetMeRequest struct{}

func (m *GetMeRequest) Reset()                          { *m = GetMeRequest{} }
func (m *GetMeRequest) String() string                  { return "GetMeRequest" }
func (*GetMeRequest) ProtoMessage()                     {}
func (m *GetMeRequest) ProtoReflect() protoreflect.Message { return nil }

// ----------------------------- Service -------------------------------------

// UserServiceServer is the interface implemented by internal/service.UserService.
type UserServiceServer interface {
	Register(ctx context.Context, req *RegisterRequest) (*User, error)
	Login(ctx context.Context, req *LoginRequest) (*LoginReply, error)
	GetMe(ctx context.Context, req *GetMeRequest) (*User, error)
}

// UnimplementedUserServiceServer can be embedded for forward compatibility.
type UnimplementedUserServiceServer struct{}

func (UnimplementedUserServiceServer) Register(context.Context, *RegisterRequest) (*User, error) {
	return nil, errNotImpl("Register")
}
func (UnimplementedUserServiceServer) Login(context.Context, *LoginRequest) (*LoginReply, error) {
	return nil, errNotImpl("Login")
}
func (UnimplementedUserServiceServer) GetMe(context.Context, *GetMeRequest) (*User, error) {
	return nil, errNotImpl("GetMe")
}
