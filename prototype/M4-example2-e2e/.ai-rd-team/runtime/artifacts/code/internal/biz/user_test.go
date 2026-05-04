package biz

import (
	"context"
	"testing"

	"blog/internal/pkg/password"

	kerrors "github.com/go-kratos/kratos/v2/errors"
)

func init() {
	// 加速 bcrypt 在单测中的执行
	password.SetTestCost(4)
}

func TestUserUsecase_Register_Success(t *testing.T) {
	repo := newFakeUserRepo()
	uc := NewUserUsecase(repo, &stubTokenIssuer{token: "t"}, testLogger())

	u, err := uc.Register(context.Background(), "Alice@Example.COM", "secret1", " Alice ")
	if err != nil {
		t.Fatalf("unexpected err: %v", err)
	}
	if u.ID == 0 {
		t.Fatalf("expected id assigned")
	}
	if u.Email != "alice@example.com" {
		t.Fatalf("email not normalized, got %q", u.Email)
	}
	if u.Nickname != "Alice" {
		t.Fatalf("nickname not trimmed, got %q", u.Nickname)
	}
	if u.PasswordHash != "" {
		t.Fatalf("password hash must not leak, got %q", u.PasswordHash)
	}
}

func TestUserUsecase_Register_ValidationFailed(t *testing.T) {
	repo := newFakeUserRepo()
	uc := NewUserUsecase(repo, &stubTokenIssuer{}, testLogger())

	tests := []struct {
		name, email, pwd, nick string
	}{
		{"bad email", "invalid", "secret1", "a"},
		{"short pwd", "a@b.com", "123", "a"},
		{"empty nick", "a@b.com", "secret1", ""},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			_, err := uc.Register(context.Background(), tc.email, tc.pwd, tc.nick)
			if err == nil || kerrors.Reason(err) != "VALIDATION_FAILED" {
				t.Fatalf("expected VALIDATION_FAILED, got %v", err)
			}
		})
	}
}

func TestUserUsecase_Register_EmailExists(t *testing.T) {
	repo := newFakeUserRepo()
	uc := NewUserUsecase(repo, &stubTokenIssuer{}, testLogger())

	if _, err := uc.Register(context.Background(), "a@b.com", "secret1", "alice"); err != nil {
		t.Fatal(err)
	}
	_, err := uc.Register(context.Background(), "A@B.com", "secret1", "alice2")
	if err == nil || kerrors.Reason(err) != "USER_EMAIL_EXISTS" {
		t.Fatalf("expected USER_EMAIL_EXISTS, got %v", err)
	}
}

func TestUserUsecase_Login_Success(t *testing.T) {
	repo := newFakeUserRepo()
	uc := NewUserUsecase(repo, &stubTokenIssuer{token: "tkn"}, testLogger())
	if _, err := uc.Register(context.Background(), "a@b.com", "secret1", "alice"); err != nil {
		t.Fatal(err)
	}

	token, u, err := uc.Login(context.Background(), "A@B.COM", "secret1")
	if err != nil {
		t.Fatalf("login: %v", err)
	}
	if token != "tkn" {
		t.Fatalf("token mismatch: %s", token)
	}
	if u == nil || u.PasswordHash != "" {
		t.Fatalf("user invalid: %+v", u)
	}
}

func TestUserUsecase_Login_WrongPassword(t *testing.T) {
	repo := newFakeUserRepo()
	uc := NewUserUsecase(repo, &stubTokenIssuer{token: "tkn"}, testLogger())
	if _, err := uc.Register(context.Background(), "a@b.com", "secret1", "alice"); err != nil {
		t.Fatal(err)
	}

	_, _, err := uc.Login(context.Background(), "a@b.com", "bad-pass")
	if err == nil || kerrors.Reason(err) != "INVALID_CREDENTIALS" {
		t.Fatalf("expected INVALID_CREDENTIALS, got %v", err)
	}
}

func TestUserUsecase_Login_UserMissing(t *testing.T) {
	repo := newFakeUserRepo()
	uc := NewUserUsecase(repo, &stubTokenIssuer{}, testLogger())

	_, _, err := uc.Login(context.Background(), "nope@b.com", "secret1")
	if err == nil || kerrors.Reason(err) != "INVALID_CREDENTIALS" {
		t.Fatalf("expected INVALID_CREDENTIALS, got %v", err)
	}
}

func TestUserUsecase_Get(t *testing.T) {
	repo := newFakeUserRepo()
	uc := NewUserUsecase(repo, &stubTokenIssuer{}, testLogger())

	u, err := uc.Register(context.Background(), "a@b.com", "secret1", "alice")
	if err != nil {
		t.Fatal(err)
	}

	got, err := uc.Get(context.Background(), u.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.PasswordHash != "" {
		t.Fatalf("password hash must not leak")
	}

	_, err = uc.Get(context.Background(), 9999)
	if err == nil || kerrors.Reason(err) != "USER_NOT_FOUND" {
		t.Fatalf("expected USER_NOT_FOUND, got %v", err)
	}
}
