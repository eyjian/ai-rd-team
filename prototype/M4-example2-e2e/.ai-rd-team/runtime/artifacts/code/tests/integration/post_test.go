package integration

import (
	"fmt"
	"net/http"
	"testing"
)

// TestPostCRUDAndList 覆盖：创建 / 获取 / 更新（作者/非作者）/ 列表分页+tag 过滤 / 删除
func TestPostCRUDAndList(t *testing.T) {
	requireAppReady(t)
	setupTestDB(t)

	author := createTestUser(t, "author")
	other := createTestUser(t, "other")

	// Create
	var postID int64
	t.Run("create post ok", func(t *testing.T) {
		r := apiCall(t, http.MethodPost, "/v1/posts", map[string]any{
			"title": "hello",
			"body":  "first body",
			"tags":  []string{"go", "kratos"},
		}, author.Token)
		assertStatus(t, r, 200)
		var p struct {
			ID int64 `json:"id"`
		}
		decode(t, r, &p)
		if p.ID == 0 {
			t.Fatalf("empty post id: %s", string(r.Body))
		}
		postID = p.ID
	})

	// Create without auth -> 401
	t.Run("create post unauthenticated", func(t *testing.T) {
		r := apiCall(t, http.MethodPost, "/v1/posts", map[string]any{
			"title": "x",
			"body":  "y",
		}, "")
		assertStatus(t, r, 401)
	})

	// Get
	t.Run("get post ok", func(t *testing.T) {
		r := apiCall(t, http.MethodGet, fmt.Sprintf("/v1/posts/%d", postID), nil, "")
		assertStatus(t, r, 200)
		var p struct {
			Title string   `json:"title"`
			Tags  []string `json:"tags"`
		}
		decode(t, r, &p)
		if p.Title != "hello" {
			t.Fatalf("title=%q", p.Title)
		}
	})

	t.Run("get post not found", func(t *testing.T) {
		r := apiCall(t, http.MethodGet, "/v1/posts/99999", nil, "")
		assertStatus(t, r, 404)
		assertReason(t, r, "POST_NOT_FOUND")
	})

	// Update by non-author -> 403 POST_FORBIDDEN
	t.Run("update by non-author forbidden", func(t *testing.T) {
		r := apiCall(t, http.MethodPut, fmt.Sprintf("/v1/posts/%d", postID), map[string]any{
			"title": "hijack",
			"body":  "nope",
			"tags":  []string{"go"},
		}, other.Token)
		assertStatus(t, r, 403)
		assertReason(t, r, "POST_FORBIDDEN")
	})

	// Update by author
	t.Run("update by author ok", func(t *testing.T) {
		r := apiCall(t, http.MethodPut, fmt.Sprintf("/v1/posts/%d", postID), map[string]any{
			"title": "hello v2",
			"body":  "updated",
			"tags":  []string{"go", "golang"},
		}, author.Token)
		assertStatus(t, r, 200)
	})

	// 再建几篇用于列表分页 + tag 过滤
	for i := 0; i < 3; i++ {
		r := apiCall(t, http.MethodPost, "/v1/posts", map[string]any{
			"title": fmt.Sprintf("post-%d", i),
			"body":  "body",
			"tags":  []string{"misc"},
		}, author.Token)
		assertStatus(t, r, 200)
	}

	t.Run("list page=1 size=2", func(t *testing.T) {
		r := apiCall(t, http.MethodGet, "/v1/posts?page=1&page_size=2", nil, "")
		assertStatus(t, r, 200)
		var list struct {
			Total int64 `json:"total"`
			Items []any `json:"items"`
		}
		decode(t, r, &list)
		if list.Total < 4 {
			t.Fatalf("total=%d want>=4", list.Total)
		}
		if len(list.Items) != 2 {
			t.Fatalf("items=%d want=2", len(list.Items))
		}
	})

	t.Run("list filter by tag=golang", func(t *testing.T) {
		r := apiCall(t, http.MethodGet, "/v1/posts?page=1&page_size=10&tag=golang", nil, "")
		assertStatus(t, r, 200)
		var list struct {
			Total int64 `json:"total"`
			Items []any `json:"items"`
		}
		decode(t, r, &list)
		if list.Total != 1 {
			t.Fatalf("total=%d want=1 (only updated post has tag golang)", list.Total)
		}
	})

	// Like idempotency
	t.Run("like idempotent", func(t *testing.T) {
		for i := 0; i < 2; i++ {
			r := apiCall(t, http.MethodPost, fmt.Sprintf("/v1/posts/%d/like", postID), nil, other.Token)
			assertStatus(t, r, 200)
		}
		// 查 post like_count
		r := apiCall(t, http.MethodGet, fmt.Sprintf("/v1/posts/%d", postID), nil, "")
		assertStatus(t, r, 200)
		var p struct {
			LikeCount int64 `json:"like_count"`
		}
		decode(t, r, &p)
		if p.LikeCount != 1 {
			t.Fatalf("like_count=%d want=1 after 2 likes", p.LikeCount)
		}
	})

	t.Run("unlike idempotent", func(t *testing.T) {
		for i := 0; i < 2; i++ {
			r := apiCall(t, http.MethodDelete, fmt.Sprintf("/v1/posts/%d/like", postID), nil, other.Token)
			assertStatus(t, r, 200)
		}
		r := apiCall(t, http.MethodGet, fmt.Sprintf("/v1/posts/%d", postID), nil, "")
		assertStatus(t, r, 200)
		var p struct {
			LikeCount int64 `json:"like_count"`
		}
		decode(t, r, &p)
		if p.LikeCount != 0 {
			t.Fatalf("like_count=%d want=0 after unlike", p.LikeCount)
		}
	})

	// Delete by non-author -> 403
	t.Run("delete by non-author forbidden", func(t *testing.T) {
		r := apiCall(t, http.MethodDelete, fmt.Sprintf("/v1/posts/%d", postID), nil, other.Token)
		assertStatus(t, r, 403)
		assertReason(t, r, "POST_FORBIDDEN")
	})

	// Delete by author
	t.Run("delete by author ok", func(t *testing.T) {
		r := apiCall(t, http.MethodDelete, fmt.Sprintf("/v1/posts/%d", postID), nil, author.Token)
		assertStatus(t, r, 200)
	})

	t.Run("get after delete -> 404", func(t *testing.T) {
		r := apiCall(t, http.MethodGet, fmt.Sprintf("/v1/posts/%d", postID), nil, "")
		assertStatus(t, r, 404)
	})
}
