package integration

import (
	"net/http"
	"testing"
)

// TestUser_RegisterLoginAndAuth exercises the three user-related routes
// plus the JWT middleware:
//
//   POST /v1/users         -> register (public)
//   POST /v1/auth/login    -> login    (public, returns JWT)
//   GET  /v1/users/me      -> get self (requires JWT)
//
// It is table-driven so each scenario fails independently with a clear
// name. Every case gets its own email to avoid USER_EMAIL_EXISTS across
// re-runs of `go test -count=N`.
func TestUser_RegisterLoginAndAuth(t *testing.T) {
	_ = setupTestDB(t)
	client := newAPIClient(t)

	t.Run("register succeeds with fresh email", func(t *testing.T) {
		email := uniqueEmail(t, "reg-ok")
		resp := client.apiCall(http.MethodPost, "/v1/users", map[string]string{
			"email":    email,
			"password": "hunter2-strong",
			"nickname": "alice",
		}, nil)
		if resp.Status != http.StatusOK && resp.Status != http.StatusCreated {
			t.Fatalf("want 200/201, got %d body=%s", resp.Status, resp.Body)
		}
		var out struct {
			Id       int64  `json:"id"`
			Email    string `json:"email"`
			Nickname string `json:"nickname"`
		}
		if err := resp.decode(&out); err != nil {
			t.Fatalf("decode: %v (%s)", err, resp.Body)
		}
		if out.Id == 0 {
			t.Errorf("expect non-zero id, got %+v", out)
		}
		if out.Email != email {
			t.Errorf("email echoed as %q, want %q", out.Email, email)
		}
		// password_hash MUST NOT appear in the response, per spec §4.2.
		if contains(resp.Body, "password") {
			t.Errorf("response leaks password-like field: %s", resp.Body)
		}
	})

	t.Run("register rejects duplicate email with USER_EMAIL_EXISTS", func(t *testing.T) {
		email := uniqueEmail(t, "dup")
		_ = createTestUser(t, client, email, "pw-aaaaaaa1", "first")

		resp := client.apiCall(http.MethodPost, "/v1/users", map[string]string{
			"email":    email,
			"password": "pw-bbbbbbb1",
			"nickname": "second",
		}, nil)
		if resp.Status != http.StatusConflict {
			t.Fatalf("want 409, got %d body=%s", resp.Status, resp.Body)
		}
		assertErrorReason(t, resp, "USER_EMAIL_EXISTS")
	})

	t.Run("register is case-insensitive on email", func(t *testing.T) {
		email := uniqueEmail(t, "case")
		_ = createTestUser(t, client, email, "pw-aaaaaaa1", "orig")

		// Same address with uppercase letters should still conflict.
		resp := client.apiCall(http.MethodPost, "/v1/users", map[string]string{
			"email":    upper(email),
			"password": "pw-bbbbbbb1",
			"nickname": "dup",
		}, nil)
		if resp.Status != http.StatusConflict {
			t.Fatalf("want 409 on case-variant email, got %d body=%s", resp.Status, resp.Body)
		}
	})

	t.Run("register rejects short password", func(t *testing.T) {
		resp := client.apiCall(http.MethodPost, "/v1/users", map[string]string{
			"email":    uniqueEmail(t, "short-pw"),
			"password": "x",
			"nickname": "z",
		}, nil)
		if resp.Status != http.StatusBadRequest {
			t.Fatalf("want 400, got %d body=%s", resp.Status, resp.Body)
		}
		assertErrorReason(t, resp, "VALIDATION_FAILED")
	})

	t.Run("login returns token for correct credentials", func(t *testing.T) {
		u := createTestUser(t, client, uniqueEmail(t, "login-ok"), "pw-aaaaaaa1", "loginuser")
		if u.Token == "" {
			t.Fatal("expected non-empty JWT token")
		}
	})

	t.Run("login rejects wrong password with INVALID_CREDENTIALS", func(t *testing.T) {
		email := uniqueEmail(t, "wrong-pw")
		_ = createTestUser(t, client, email, "pw-aaaaaaa1", "user")

		resp := client.apiCall(http.MethodPost, "/v1/auth/login", map[string]string{
			"email":    email,
			"password": "totally-different",
		}, nil)
		if resp.Status != http.StatusUnauthorized {
			t.Fatalf("want 401, got %d body=%s", resp.Status, resp.Body)
		}
		assertErrorReason(t, resp, "INVALID_CREDENTIALS")
	})

	t.Run("GET /v1/users/me without token -> 401 UNAUTHORIZED", func(t *testing.T) {
		resp := client.apiCall(http.MethodGet, "/v1/users/me", nil, nil)
		if resp.Status != http.StatusUnauthorized {
			t.Fatalf("want 401, got %d body=%s", resp.Status, resp.Body)
		}
		assertErrorReason(t, resp, "UNAUTHORIZED")
	})

	t.Run("GET /v1/users/me with invalid token -> 401", func(t *testing.T) {
		bad := client.withToken("not-a-real-jwt.abc.def")
		resp := bad.apiCall(http.MethodGet, "/v1/users/me", nil, nil)
		if resp.Status != http.StatusUnauthorized {
			t.Fatalf("want 401, got %d body=%s", resp.Status, resp.Body)
		}
	})

	t.Run("GET /v1/users/me with valid token returns same user", func(t *testing.T) {
		u := createTestUser(t, client, uniqueEmail(t, "me"), "pw-aaaaaaa1", "me-user")
		authed := client.withToken(u.Token)

		resp := authed.apiCall(http.MethodGet, "/v1/users/me", nil, nil)
		if resp.Status != http.StatusOK {
			t.Fatalf("want 200, got %d body=%s", resp.Status, resp.Body)
		}
		var out struct {
			Id    int64  `json:"id"`
			Email string `json:"email"`
		}
		if err := resp.decode(&out); err != nil {
			t.Fatalf("decode: %v (%s)", err, resp.Body)
		}
		if out.Id != u.ID {
			t.Errorf("id mismatch: got %d want %d", out.Id, u.ID)
		}
		if out.Email != u.Email {
			t.Errorf("email mismatch: got %q want %q", out.Email, u.Email)
		}
	})
}
