package integration

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strings"
	"testing"
	"time"

	"github.com/go-kratos/kratos/v2/log"
)

// -----------------------------------------------------------------------------
// App startup (invoked from main_test.startEnv when AppFactory != nil)
// -----------------------------------------------------------------------------

// startApp asks AppFactory for a runner, kicks Start() off in a goroutine
// and blocks until the HTTP port is actually reachable. It returns the
// concrete listen address (host:port) and a cleanup function that stops
// the server.
func startApp(ctx context.Context, pgDSN string) (string, func(), error) {
	cfg := AppConfig{
		HTTPAddr:      "127.0.0.1:0",
		GRPCAddr:      "127.0.0.1:0",
		ServerTimeout: 10 * time.Second,
		PostgresDSN:   pgDSN,
		LogLevel:      "warn",
		JWTSecret:     "integration-test-secret",
		AccessTTL:     24 * time.Hour,
	}

	runner, cleanup, err := AppFactory(cfg, log.NewStdLogger(io.Discard))
	if err != nil {
		return "", nil, fmt.Errorf("build app: %w", err)
	}

	startErrCh := make(chan error, 1)
	go func() {
		startErrCh <- runner.Start(context.Background())
	}()

	// Give the runner a short window to bind before we query the address;
	// some kratos builds only assign the real port after Start() runs.
	var addr string
	deadline := time.Now().Add(5 * time.Second)
	for {
		addr = runner.HTTPAddr()
		if addr != "" && !strings.HasSuffix(addr, ":0") {
			break
		}
		if time.Now().After(deadline) {
			break
		}
		time.Sleep(50 * time.Millisecond)
	}
	if addr == "" || strings.HasSuffix(addr, ":0") {
		if cleanup != nil {
			cleanup()
		}
		return "", nil, fmt.Errorf("app runner returned unusable HTTPAddr=%q", addr)
	}

	waitCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	if err := waitTCP(waitCtx, addr); err != nil {
		if cleanup != nil {
			cleanup()
		}
		return "", nil, fmt.Errorf("http not ready at %s: %w", addr, err)
	}

	stop := func() {
		stopCtx, stopCancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer stopCancel()
		_ = runner.Stop(stopCtx)
		if cleanup != nil {
			cleanup()
		}
		select {
		case <-startErrCh:
		case <-time.After(time.Second):
		}
	}
	return addr, stop, nil
}

func waitTCP(ctx context.Context, addr string) error {
	for {
		conn, err := net.DialTimeout("tcp", addr, 500*time.Millisecond)
		if err == nil {
			_ = conn.Close()
			return nil
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(200 * time.Millisecond):
		}
	}
}

// -----------------------------------------------------------------------------
// Per-test helpers
// -----------------------------------------------------------------------------

// requireEnv ensures Postgres was successfully started; skips the test
// otherwise (e.g. Docker unavailable).
func requireEnv(t *testing.T) *testEnv {
	t.Helper()
	if sharedEnv == nil {
		t.Skip("integration env not available (Docker missing?)")
	}
	return sharedEnv
}

// requireApp ensures the BlogAPI HTTP server is up; skips the test if
// developer_2 has not wired AppFactory yet.
func requireApp(t *testing.T) *testEnv {
	t.Helper()
	env := requireEnv(t)
	if env.httpBaseURL == "" {
		t.Skip("AppFactory not registered yet — skipping HTTP-level test until wireApp is wired")
	}
	return env
}

// setupTestDB truncates all tables that the HTTP API writes to, giving
// each test a clean slate without having to recreate the schema.
//
// The truncation order is irrelevant here because we use CASCADE.
func setupTestDB(t *testing.T) *sql.DB {
	t.Helper()
	env := requireEnv(t)

	db, err := sql.Open("postgres", env.pgDSN)
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	t.Cleanup(func() { _ = db.Close() })

	_, err = db.ExecContext(context.Background(),
		`TRUNCATE TABLE post_likes, comments, posts, users RESTART IDENTITY CASCADE`)
	if err != nil {
		t.Fatalf("truncate: %v", err)
	}
	return db
}

// -----------------------------------------------------------------------------
// HTTP client
// -----------------------------------------------------------------------------

// apiClient is a tiny wrapper around net/http that knows how to sign
// requests with a JWT and unmarshal JSON responses.
type apiClient struct {
	t       *testing.T
	baseURL string
	hc      *http.Client
	token   string
}

func newAPIClient(t *testing.T) *apiClient {
	t.Helper()
	env := requireApp(t)
	return &apiClient{
		t:       t,
		baseURL: env.httpBaseURL,
		hc:      &http.Client{Timeout: 10 * time.Second},
	}
}

// withToken returns a copy of the client carrying the given JWT.
func (c *apiClient) withToken(token string) *apiClient {
	cp := *c
	cp.token = token
	return &cp
}

// apiResponse is what every API call returns; tests inspect Status and
// optionally Decode() the Body.
type apiResponse struct {
	Status int
	Body   []byte
	Header http.Header
}

func (r *apiResponse) decode(v interface{}) error {
	return json.Unmarshal(r.Body, v)
}

// apiCall executes an HTTP request and returns the response. It never
// fails the test directly so that callers can assert on status codes
// (both 2xx and error paths).
func (c *apiClient) apiCall(method, path string, body interface{}, query url.Values) *apiResponse {
	c.t.Helper()

	var reader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			c.t.Fatalf("marshal body: %v", err)
		}
		reader = bytes.NewReader(b)
	}

	u := c.baseURL + path
	if len(query) > 0 {
		sep := "?"
		if strings.Contains(u, "?") {
			sep = "&"
		}
		u = u + sep + query.Encode()
	}

	req, err := http.NewRequest(method, u, reader)
	if err != nil {
		c.t.Fatalf("new request: %v", err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}

	resp, err := c.hc.Do(req)
	if err != nil {
		c.t.Fatalf("http do: %v", err)
	}
	defer resp.Body.Close()

	b, err := io.ReadAll(resp.Body)
	if err != nil {
		c.t.Fatalf("read body: %v", err)
	}
	return &apiResponse{Status: resp.StatusCode, Body: b, Header: resp.Header.Clone()}
}

// -----------------------------------------------------------------------------
// Fixtures
// -----------------------------------------------------------------------------

// userFixture captures everything tests need about a freshly-registered
// user: their id (echoed back from the API), credentials to log in again
// and a valid JWT.
type userFixture struct {
	ID       int64
	Email    string
	Password string
	Nickname string
	Token    string
}

// createTestUser registers a user via POST /v1/users and logs them in
// via POST /v1/auth/login. It fails the test on any non-2xx response
// so callers can use the returned fixture directly.
func createTestUser(t *testing.T, client *apiClient, email, password, nickname string) *userFixture {
	t.Helper()

	regResp := client.apiCall(http.MethodPost, "/v1/users", map[string]string{
		"email":    email,
		"password": password,
		"nickname": nickname,
	}, nil)
	if regResp.Status < 200 || regResp.Status >= 300 {
		t.Fatalf("register user: status=%d body=%s", regResp.Status, regResp.Body)
	}
	var regOut struct {
		Id       int64  `json:"id"`
		Email    string `json:"email"`
		Nickname string `json:"nickname"`
	}
	if err := regResp.decode(&regOut); err != nil {
		t.Fatalf("decode register resp: %v (%s)", err, regResp.Body)
	}

	loginResp := client.apiCall(http.MethodPost, "/v1/auth/login", map[string]string{
		"email":    email,
		"password": password,
	}, nil)
	if loginResp.Status < 200 || loginResp.Status >= 300 {
		t.Fatalf("login user: status=%d body=%s", loginResp.Status, loginResp.Body)
	}
	var loginOut struct {
		Token string `json:"token"`
		User  struct {
			Id int64 `json:"id"`
		} `json:"user"`
	}
	if err := loginResp.decode(&loginOut); err != nil {
		t.Fatalf("decode login resp: %v (%s)", err, loginResp.Body)
	}

	id := regOut.Id
	if id == 0 {
		id = loginOut.User.Id
	}
	return &userFixture{
		ID:       id,
		Email:    email,
		Password: password,
		Nickname: nickname,
		Token:    loginOut.Token,
	}
}

// uniqueEmail returns a predictable-but-unique email for each table-driven
// sub-test so re-runs don't collide on the `users.email` unique index.
func uniqueEmail(t *testing.T, tag string) string {
	t.Helper()
	return fmt.Sprintf("%s+%d@example.com", tag, time.Now().UnixNano())
}

// -----------------------------------------------------------------------------
// Assertion helpers
// -----------------------------------------------------------------------------

// assertErrorReason checks that the response body carries the Kratos-style
// error envelope with the given `reason`. Kratos error JSON looks like:
//
//	{ "code": 409, "reason": "USER_EMAIL_EXISTS", "message": "...", "metadata": {} }
//
// Tests call this after already verifying the HTTP status code, so we do
// not re-check status here.
func assertErrorReason(t *testing.T, resp *apiResponse, want string) {
	t.Helper()
	var env struct {
		Reason string `json:"reason"`
	}
	if err := resp.decode(&env); err != nil {
		t.Fatalf("decode error envelope: %v (body=%s)", err, resp.Body)
	}
	if env.Reason != want {
		t.Errorf("error reason mismatch: got %q want %q (body=%s)", env.Reason, want, resp.Body)
	}
}

// contains reports whether substr appears in b; used for cheap body-shape
// sanity checks (e.g. "password" must not leak in user responses).
func contains(b []byte, substr string) bool {
	return strings.Contains(string(b), substr)
}

// upper uppercases the whole string; used by email case-insensitivity
// tests. Wrapped as a helper so it reads naturally at call sites.
func upper(s string) string { return strings.ToUpper(s) }
