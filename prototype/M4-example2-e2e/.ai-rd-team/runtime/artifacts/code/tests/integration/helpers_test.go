package integration

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"strings"
	"testing"
	"time"
)

// HTTP 测试辅助：统一请求构造、JSON 解包、token 注入

type apiResp struct {
	Status int
	Body   []byte
	Header http.Header
}

// apiCall 发起一次 HTTP 请求，body 可为 nil；token 非空则自动加 Bearer。
func apiCall(t *testing.T, method, path string, body any, token string) apiResp {
	t.Helper()
	if testBaseURL == "" {
		t.Fatalf("testBaseURL empty; call requireAppReady first")
	}
	var reader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			t.Fatalf("marshal body: %v", err)
		}
		reader = bytes.NewReader(b)
	}
	req, err := http.NewRequest(method, testBaseURL+path, reader)
	if err != nil {
		t.Fatalf("new request: %v", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		t.Fatalf("do request: %v", err)
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	return apiResp{Status: resp.StatusCode, Body: data, Header: resp.Header}
}

// decode 将响应体解到 out，便于 table-driven 断言。
func decode(t *testing.T, r apiResp, out any) {
	t.Helper()
	if len(r.Body) == 0 {
		return
	}
	if err := json.Unmarshal(r.Body, out); err != nil {
		t.Fatalf("decode json: %v, body=%s", err, string(r.Body))
	}
}

// ------------------------- DB 辅助 -------------------------

// setupTestDB 清空 4 张业务表，保证用例间独立。
// 使用 TRUNCATE RESTART IDENTITY CASCADE 一次清理并重置自增。
func setupTestDB(t *testing.T) {
	t.Helper()
	if testDSN == "" {
		t.Skip("no DSN; PG container not started")
	}
	db, err := sql.Open("postgres", testDSN)
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	defer db.Close()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_, err = db.ExecContext(ctx,
		`TRUNCATE TABLE post_likes, comments, posts, users RESTART IDENTITY CASCADE`)
	if err != nil {
		t.Fatalf("truncate: %v", err)
	}
}

// ------------------------- User 辅助 -------------------------

// testUser 用例层面持有的测试用户信息（含 token）。
type testUser struct {
	ID       int64
	Email    string
	Password string
	Nickname string
	Token    string
}

// randEmail 生成随机邮箱，避免并发用例冲突。
func randEmail(prefix string) string {
	return fmt.Sprintf("%s_%d_%d@example.com", prefix, time.Now().UnixNano(), rand.Intn(10000))
}

// createTestUser：POST /v1/users 注册 -> POST /v1/auth/login 登录 -> 返回带 token 的 testUser。
// 约定响应体含 `id` / `token`（JSON 字段名按 proto JSONName = snake_case）。
func createTestUser(t *testing.T, nickname string) *testUser {
	t.Helper()
	u := &testUser{
		Email:    randEmail("u"),
		Password: "Passw0rd!",
		Nickname: nickname,
	}
	// 注册
	reg := apiCall(t, http.MethodPost, "/v1/users", map[string]any{
		"email":    u.Email,
		"password": u.Password,
		"nickname": u.Nickname,
	}, "")
	if reg.Status/100 != 2 {
		t.Fatalf("register failed: status=%d body=%s", reg.Status, string(reg.Body))
	}
	var regBody struct {
		ID    int64  `json:"id"`
		Email string `json:"email"`
	}
	decode(t, reg, &regBody)
	u.ID = regBody.ID

	// 登录
	login := apiCall(t, http.MethodPost, "/v1/auth/login", map[string]any{
		"email":    u.Email,
		"password": u.Password,
	}, "")
	if login.Status/100 != 2 {
		t.Fatalf("login failed: status=%d body=%s", login.Status, string(login.Body))
	}
	var loginBody struct {
		Token string `json:"token"`
		User  struct {
			ID int64 `json:"id"`
		} `json:"user"`
	}
	decode(t, login, &loginBody)
	if loginBody.Token == "" {
		t.Fatalf("empty token in login body: %s", string(login.Body))
	}
	u.Token = loginBody.Token
	if u.ID == 0 && loginBody.User.ID != 0 {
		u.ID = loginBody.User.ID
	}
	return u
}

// ------------------------- Assertion helpers -------------------------

// assertStatus 断言 HTTP 状态码。
func assertStatus(t *testing.T, r apiResp, want int) {
	t.Helper()
	if r.Status != want {
		t.Fatalf("status=%d want=%d body=%s", r.Status, want, string(r.Body))
	}
}

// assertReason 断言 kratos errors 响应体中的 reason 字段。
func assertReason(t *testing.T, r apiResp, want string) {
	t.Helper()
	var e struct {
		Reason string `json:"reason"`
	}
	_ = json.Unmarshal(r.Body, &e)
	if !strings.EqualFold(e.Reason, want) {
		t.Fatalf("reason=%q want=%q body=%s", e.Reason, want, string(r.Body))
	}
}
