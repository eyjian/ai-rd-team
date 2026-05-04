package integration

import (
	"net/http"
	"testing"
)

// TestUserRegisterAndLogin 覆盖：注册 / 重复注册 / 登录失败 / 登录成功 / GetMe
func TestUserRegisterAndLogin(t *testing.T) {
	requireAppReady(t)
	setupTestDB(t)

	type step struct {
		name     string
		method   string
		path     string
		body     any
		token    string
		wantCode int
		wantErr  string // kratos errors reason（空则不校验）
	}

	email := randEmail("alice")
	cases := []step{
		{
			name:     "register ok",
			method:   http.MethodPost,
			path:     "/v1/users",
			body:     map[string]any{"email": email, "password": "Passw0rd!", "nickname": "Alice"},
			wantCode: 200,
		},
		{
			name:     "register duplicate -> 409 USER_ALREADY_EXISTS",
			method:   http.MethodPost,
			path:     "/v1/users",
			body:     map[string]any{"email": email, "password": "Passw0rd!", "nickname": "Alice"},
			wantCode: 409,
			wantErr:  "USER_ALREADY_EXISTS",
		},
		{
			name:     "login wrong password -> 401",
			method:   http.MethodPost,
			path:     "/v1/auth/login",
			body:     map[string]any{"email": email, "password": "wrong"},
			wantCode: 401,
			wantErr:  "USER_CREDENTIAL_INVALID",
		},
		{
			name:     "login ok",
			method:   http.MethodPost,
			path:     "/v1/auth/login",
			body:     map[string]any{"email": email, "password": "Passw0rd!"},
			wantCode: 200,
		},
	}

	var token string
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			r := apiCall(t, tc.method, tc.path, tc.body, tc.token)
			assertStatus(t, r, tc.wantCode)
			if tc.wantErr != "" {
				assertReason(t, r, tc.wantErr)
			}
			if tc.name == "login ok" {
				var body struct {
					Token string `json:"token"`
				}
				decode(t, r, &body)
				if body.Token == "" {
					t.Fatalf("empty token: %s", string(r.Body))
				}
				token = body.Token
			}
		})
	}

	// GetMe（带 token）
	t.Run("get me", func(t *testing.T) {
		r := apiCall(t, http.MethodGet, "/v1/users/me", nil, token)
		assertStatus(t, r, 200)
		var me struct {
			Email string `json:"email"`
		}
		decode(t, r, &me)
		if me.Email != email {
			t.Fatalf("me.email=%s want=%s", me.Email, email)
		}
	})

	// GetMe 无 token -> 401
	t.Run("get me unauthenticated", func(t *testing.T) {
		r := apiCall(t, http.MethodGet, "/v1/users/me", nil, "")
		assertStatus(t, r, 401)
	})
}
