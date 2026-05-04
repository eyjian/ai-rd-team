package integration

import (
	"net/http"
	"testing"
)

// TestUser_Auth 覆盖用户注册/登录/GetMe 的正常路径与异常。
func TestUser_Auth(t *testing.T) {
	skipIfAppNotReady(t)

	t.Run("Register_OK", func(t *testing.T) {
		email := uniqueEmail("reg_ok")
		resp := apiCall(t, http.MethodPost, "/v1/users", map[string]interface{}{
			"email":    email,
			"password": "password123",
			"nickname": "regok",
		}, "")
		assertStatus(t, resp, http.StatusOK)
		var r struct {
			ID       int64  `json:"id"`
			Email    string `json:"email"`
			Nickname string `json:"nickname"`
		}
		resp.decode(t, &r)
		if r.ID <= 0 || r.Email != email || r.Nickname != "regok" {
			t.Fatalf("unexpected register reply: %+v", r)
		}
	})

	t.Run("Register_Duplicate_409", func(t *testing.T) {
		email := uniqueEmail("dup")
		body := map[string]interface{}{
			"email":    email,
			"password": "password123",
			"nickname": "dup",
		}
		r1 := apiCall(t, http.MethodPost, "/v1/users", body, "")
		assertStatus(t, r1, http.StatusOK)

		r2 := apiCall(t, http.MethodPost, "/v1/users", body, "")
		assertStatus(t, r2, http.StatusConflict)
		assertReason(t, r2, "USER_EMAIL_EXISTS")
	})

	t.Run("Register_InvalidEmail_400", func(t *testing.T) {
		resp := apiCall(t, http.MethodPost, "/v1/users", map[string]interface{}{
			"email":    "not-an-email",
			"password": "password123",
			"nickname": "bad",
		}, "")
		// validate.Validator() 中间件会把校验失败映射到 400
		if resp.StatusCode != http.StatusBadRequest {
			t.Fatalf("want 400, got %d body=%s", resp.StatusCode, string(resp.Body))
		}
	})

	t.Run("Login_OK", func(t *testing.T) {
		u := createTestUser(t, "login_ok")
		if u.Token == "" {
			t.Fatal("token is empty")
		}
	})

	t.Run("Login_WrongPassword_401", func(t *testing.T) {
		u := createTestUser(t, "login_bad")
		resp := apiCall(t, http.MethodPost, "/v1/auth/login", map[string]interface{}{
			"email":    u.Email,
			"password": "wrong_pwd",
		}, "")
		assertStatus(t, resp, http.StatusUnauthorized)
		assertReason(t, resp, "USER_CRED_INVALID")
	})

	t.Run("Login_UnknownEmail_401", func(t *testing.T) {
		resp := apiCall(t, http.MethodPost, "/v1/auth/login", map[string]interface{}{
			"email":    uniqueEmail("nonexist"),
			"password": "password123",
		}, "")
		assertStatus(t, resp, http.StatusUnauthorized)
		assertReason(t, resp, "USER_CRED_INVALID")
	})

	t.Run("GetMe_NoToken_401", func(t *testing.T) {
		resp := apiCall(t, http.MethodGet, "/v1/users/me", nil, "")
		assertStatus(t, resp, http.StatusUnauthorized)
	})

	t.Run("GetMe_InvalidToken_401", func(t *testing.T) {
		resp := apiCall(t, http.MethodGet, "/v1/users/me", nil, "garbage.token.value")
		assertStatus(t, resp, http.StatusUnauthorized)
	})

	t.Run("GetMe_OK", func(t *testing.T) {
		u := createTestUser(t, "me")
		resp := apiCall(t, http.MethodGet, "/v1/users/me", nil, u.Token)
		assertStatus(t, resp, http.StatusOK)
		var info struct {
			ID    int64  `json:"id"`
			Email string `json:"email"`
		}
		resp.decode(t, &info)
		if info.ID != u.ID || info.Email != u.Email {
			t.Fatalf("me info mismatch: got %+v want id=%d email=%s", info, u.ID, u.Email)
		}
	})
}
