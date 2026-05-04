package integration

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"
)

// apiResp 是对 HTTP 响应的轻量封装，提供便捷断言。
type apiResp struct {
	StatusCode int
	Body       []byte
}

// decode 把响应体 JSON 反序列化到 out。
func (r *apiResp) decode(t *testing.T, out interface{}) {
	t.Helper()
	if len(r.Body) == 0 {
		t.Fatalf("empty response body")
	}
	if err := json.Unmarshal(r.Body, out); err != nil {
		t.Fatalf("decode body %q: %v", string(r.Body), err)
	}
}

// reason 从 kratos 错误响应中抽出 reason 字段（形如 {"code":..,"reason":"...","message":".."}）。
func (r *apiResp) reason() string {
	var e struct {
		Reason string `json:"reason"`
	}
	_ = json.Unmarshal(r.Body, &e)
	return e.Reason
}

// apiCall 执行 HTTP 调用。
// body == nil 时不带请求体；token 非空时附带 Authorization 头。
func apiCall(t *testing.T, method, path string, body interface{}, token string) *apiResp {
	t.Helper()

	var reader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			t.Fatalf("marshal body: %v", err)
		}
		reader = bytes.NewReader(b)
	}

	url := testEnv.baseURL + path
	req, err := http.NewRequest(method, url, reader)
	if err != nil {
		t.Fatalf("new request %s %s: %v", method, url, err)
	}
	req.Header.Set("Content-Type", "application/json")
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		t.Fatalf("do %s %s: %v", method, url, err)
	}
	defer resp.Body.Close()

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatalf("read body: %v", err)
	}

	return &apiResp{StatusCode: resp.StatusCode, Body: raw}
}

// ---------- 业务级别 fixture ----------

// testUser 描述一个测试用户及其 JWT。
type testUser struct {
	ID       int64
	Email    string
	Password string
	Nickname string
	Token    string
}

// uniqueEmail 生成不易冲突的邮箱（使用 nano 时间戳）。
func uniqueEmail(prefix string) string {
	return fmt.Sprintf("%s_%d@example.com", strings.ToLower(prefix), time.Now().UnixNano())
}

// createTestUser 注册并登录，返回可直接用于鉴权调用的用户。
func createTestUser(t *testing.T, nickname string) *testUser {
	t.Helper()
	u := &testUser{
		Email:    uniqueEmail(nickname),
		Password: "password123",
		Nickname: nickname,
	}

	// Register
	regResp := apiCall(t, http.MethodPost, "/v1/users", map[string]interface{}{
		"email":    u.Email,
		"password": u.Password,
		"nickname": u.Nickname,
	}, "")
	if regResp.StatusCode != http.StatusOK {
		t.Fatalf("register user %s unexpected status=%d body=%s", u.Email, regResp.StatusCode, string(regResp.Body))
	}
	var reg struct {
		ID int64 `json:"id"`
	}
	regResp.decode(t, &reg)
	u.ID = reg.ID

	// Login
	u.Token = loginAndGetToken(t, u.Email, u.Password)
	return u
}

// loginAndGetToken 仅登录并取 token。
func loginAndGetToken(t *testing.T, email, password string) string {
	t.Helper()
	resp := apiCall(t, http.MethodPost, "/v1/auth/login", map[string]interface{}{
		"email":    email,
		"password": password,
	}, "")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("login %s unexpected status=%d body=%s", email, resp.StatusCode, string(resp.Body))
	}
	var loginReply struct {
		Token     string `json:"token"`
		ExpiresIn int64  `json:"expires_in"`
	}
	resp.decode(t, &loginReply)
	if loginReply.Token == "" {
		t.Fatalf("login %s empty token, body=%s", email, string(resp.Body))
	}
	return loginReply.Token
}

// createTestPost 用指定用户发一篇测试文章，返回 post_id。
func createTestPost(t *testing.T, u *testUser, title string, tags []string) int64 {
	t.Helper()
	resp := apiCall(t, http.MethodPost, "/v1/posts", map[string]interface{}{
		"title":         title,
		"body_markdown": "# " + title + "\n\nbody for integration test",
		"tags":          tags,
	}, u.Token)
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("create post unexpected status=%d body=%s", resp.StatusCode, string(resp.Body))
	}
	var p struct {
		ID int64 `json:"id"`
	}
	resp.decode(t, &p)
	if p.ID <= 0 {
		t.Fatalf("create post: invalid id %d", p.ID)
	}
	return p.ID
}

// assertStatus 统一断言状态码，失败时打印 body。
func assertStatus(t *testing.T, resp *apiResp, want int) {
	t.Helper()
	if resp.StatusCode != want {
		t.Fatalf("status want=%d got=%d body=%s", want, resp.StatusCode, string(resp.Body))
	}
}

// assertReason 断言 kratos 错误响应中的 reason。
func assertReason(t *testing.T, resp *apiResp, wantReason string) {
	t.Helper()
	got := resp.reason()
	if got != wantReason {
		t.Fatalf("reason want=%q got=%q body=%s", wantReason, got, string(resp.Body))
	}
}
