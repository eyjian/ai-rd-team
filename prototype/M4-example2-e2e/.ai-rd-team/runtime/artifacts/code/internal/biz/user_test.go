package biz

import (
	"context"
	"testing"
	"time"

	"blog/internal/conf"
	"blog/internal/pkg/password"

	"github.com/go-kratos/kratos/v2/errors"
	"github.com/go-kratos/kratos/v2/log"
)

func newTestUserUsecase(repo UserRepo) *UserUsecase {
	auth := &conf.Auth{JWTSecret: "test-secret", Expire: 24 * time.Hour}
	return NewUserUsecase(repo, auth, log.DefaultLogger)
}

func TestUser_Register_EmailExists(t *testing.T) {
	repo := &mockUserRepo{
		getByEmailFn: func(ctx context.Context, email string) (*User, error) {
			return &User{ID: 1, Email: email}, nil
		},
	}
	uc := newTestUserUsecase(repo)
	_, err := uc.Register(context.Background(), "a@b.com", "secret123", "alice")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if reason := errors.FromError(err).Reason; reason != "USER_ALREADY_EXISTS" {
		t.Fatalf("want USER_ALREADY_EXISTS, got %q", reason)
	}
}

func TestUser_Register_Success(t *testing.T) {
	var created *User
	repo := &mockUserRepo{
		getByEmailFn: func(ctx context.Context, email string) (*User, error) {
			return nil, ErrUserNotFound
		},
		createFn: func(ctx context.Context, u *User) (*User, error) {
			u.ID = 42
			u.CreatedAt = time.Now()
			u.UpdatedAt = u.CreatedAt
			created = u
			return u, nil
		},
	}
	uc := newTestUserUsecase(repo)
	u, err := uc.Register(context.Background(), "  A@B.COM ", "secret123", "alice")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if u.ID != 42 {
		t.Fatalf("want ID=42, got %d", u.ID)
	}
	if u.Email != "a@b.com" {
		t.Fatalf("email should be lowercased/trimmed, got %q", u.Email)
	}
	if created == nil || created.PasswordHash == "" || created.PasswordHash == "secret123" {
		t.Fatalf("password must be bcrypt-hashed, got %q", created.PasswordHash)
	}
	if !password.Verify(created.PasswordHash, "secret123") {
		t.Fatalf("bcrypt hash should verify")
	}
}

func TestUser_Register_ValidationFailed(t *testing.T) {
	uc := newTestUserUsecase(&mockUserRepo{})
	cases := []struct {
		name, email, pwd, nick string
	}{
		{"empty email", "", "secret123", "alice"},
		{"bad email", "noat", "secret123", "alice"},
		{"short password", "a@b.com", "123", "alice"},
		{"empty nick", "a@b.com", "secret123", ""},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			_, err := uc.Register(context.Background(), tc.email, tc.pwd, tc.nick)
			if err == nil {
				t.Fatal("expected validation error")
			}
			if errors.FromError(err).Reason != "VALIDATION_FAILED" {
				t.Fatalf("want VALIDATION_FAILED, got %q", errors.FromError(err).Reason)
			}
		})
	}
}

func TestUser_Login_WrongPassword(t *testing.T) {
	hash, _ := password.Hash("correct-pwd")
	repo := &mockUserRepo{
		getByEmailFn: func(ctx context.Context, email string) (*User, error) {
			return &User{ID: 1, Email: email, PasswordHash: hash}, nil
		},
	}
	uc := newTestUserUsecase(repo)
	_, _, err := uc.Login(context.Background(), "a@b.com", "wrong")
	if err == nil {
		t.Fatal("expected credential error")
	}
	if errors.FromError(err).Reason != "USER_CREDENTIAL_INVALID" {
		t.Fatalf("want USER_CREDENTIAL_INVALID, got %q", errors.FromError(err).Reason)
	}
}

func TestUser_Login_EmailNotFound(t *testing.T) {
	repo := &mockUserRepo{
		getByEmailFn: func(ctx context.Context, email string) (*User, error) {
			return nil, ErrUserNotFound
		},
	}
	uc := newTestUserUsecase(repo)
	_, _, err := uc.Login(context.Background(), "a@b.com", "whatever")
	if err == nil {
		t.Fatal("expected error")
	}
	// 不暴露具体原因：统一 USER_CREDENTIAL_INVALID
	if errors.FromError(err).Reason != "USER_CREDENTIAL_INVALID" {
		t.Fatalf("want USER_CREDENTIAL_INVALID, got %q", errors.FromError(err).Reason)
	}
}

func TestUser_Login_Success(t *testing.T) {
	hash, _ := password.Hash("correct-pwd")
	repo := &mockUserRepo{
		getByEmailFn: func(ctx context.Context, email string) (*User, error) {
			return &User{ID: 7, Email: email, PasswordHash: hash, Nickname: "alice"}, nil
		},
	}
	uc := newTestUserUsecase(repo)
	token, u, err := uc.Login(context.Background(), "a@b.com", "correct-pwd")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if token == "" {
		t.Fatal("token should not be empty")
	}
	if u.ID != 7 {
		t.Fatalf("want ID=7, got %d", u.ID)
	}
}

func TestUser_GetByID_NotFound(t *testing.T) {
	repo := &mockUserRepo{
		getByIDFn: func(ctx context.Context, id int64) (*User, error) {
			return nil, ErrUserNotFound
		},
	}
	uc := newTestUserUsecase(repo)
	_, err := uc.GetByID(context.Background(), 99)
	if err == nil {
		t.Fatal("expected USER_NOT_FOUND")
	}
	if errors.FromError(err).Reason != "USER_NOT_FOUND" {
		t.Fatalf("want USER_NOT_FOUND, got %q", errors.FromError(err).Reason)
	}
}
