package integration

import (
	"fmt"
	"net/http"
	"testing"
)

// TestE2EFlow 贯穿注册 -> 登录 -> GetMe -> 创建文章 -> 评论 -> 点赞 -> 列表 -> 删除
// 作为“金字塔顶端”的 smoke e2e，保护关键链路不崩。
func TestE2EFlow(t *testing.T) {
	requireAppReady(t)
	setupTestDB(t)

	// 1. 注册 + 登录
	u := createTestUser(t, "e2e")

	// 2. GetMe
	r := apiCall(t, http.MethodGet, "/v1/users/me", nil, u.Token)
	assertStatus(t, r, 200)

	// 3. 创建文章
	r = apiCall(t, http.MethodPost, "/v1/posts", map[string]any{
		"title": "e2e post",
		"body":  "e2e body",
		"tags":  []string{"e2e"},
	}, u.Token)
	assertStatus(t, r, 200)
	var p struct {
		ID int64 `json:"id"`
	}
	decode(t, r, &p)

	// 4. 评论
	r = apiCall(t, http.MethodPost, fmt.Sprintf("/v1/posts/%d/comments", p.ID), map[string]any{
		"body": "nice post",
	}, u.Token)
	assertStatus(t, r, 200)

	// 5. 点赞幂等（再来一次不变）
	for i := 0; i < 2; i++ {
		r = apiCall(t, http.MethodPost, fmt.Sprintf("/v1/posts/%d/like", p.ID), nil, u.Token)
		assertStatus(t, r, 200)
	}

	// 6. 列表（带 tag）
	r = apiCall(t, http.MethodGet, "/v1/posts?page=1&page_size=10&tag=e2e", nil, "")
	assertStatus(t, r, 200)
	var list struct {
		Total int64 `json:"total"`
	}
	decode(t, r, &list)
	if list.Total != 1 {
		t.Fatalf("total=%d want=1", list.Total)
	}

	// 7. 删除
	r = apiCall(t, http.MethodDelete, fmt.Sprintf("/v1/posts/%d", p.ID), nil, u.Token)
	assertStatus(t, r, 200)

	// 8. 再获取 -> 404
	r = apiCall(t, http.MethodGet, fmt.Sprintf("/v1/posts/%d", p.ID), nil, "")
	assertStatus(t, r, 404)
}
