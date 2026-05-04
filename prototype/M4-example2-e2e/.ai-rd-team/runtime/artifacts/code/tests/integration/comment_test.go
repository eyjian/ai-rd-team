package integration

import (
	"fmt"
	"net/http"
	"testing"
)

// TestCommentCreateAndList 覆盖：评论创建 / 列表 / post 不存在时 404
func TestCommentCreateAndList(t *testing.T) {
	requireAppReady(t)
	setupTestDB(t)

	author := createTestUser(t, "author")
	commenter := createTestUser(t, "commenter")

	// 先建 post
	r := apiCall(t, http.MethodPost, "/v1/posts", map[string]any{
		"title": "for comments",
		"body":  "body",
		"tags":  []string{},
	}, author.Token)
	assertStatus(t, r, 200)
	var p struct {
		ID int64 `json:"id"`
	}
	decode(t, r, &p)
	postID := p.ID

	t.Run("create comment on missing post -> 404", func(t *testing.T) {
		r := apiCall(t, http.MethodPost, "/v1/posts/999999/comments", map[string]any{
			"body": "hi",
		}, commenter.Token)
		assertStatus(t, r, 404)
		assertReason(t, r, "POST_NOT_FOUND")
	})

	t.Run("create comment unauthenticated -> 401", func(t *testing.T) {
		r := apiCall(t, http.MethodPost, fmt.Sprintf("/v1/posts/%d/comments", postID), map[string]any{
			"body": "hi",
		}, "")
		assertStatus(t, r, 401)
	})

	// 创建 3 条评论
	for i := 0; i < 3; i++ {
		r := apiCall(t, http.MethodPost, fmt.Sprintf("/v1/posts/%d/comments", postID), map[string]any{
			"body": fmt.Sprintf("comment-%d", i),
		}, commenter.Token)
		assertStatus(t, r, 200)
	}

	t.Run("list comments", func(t *testing.T) {
		r := apiCall(t, http.MethodGet, fmt.Sprintf("/v1/posts/%d/comments", postID), nil, "")
		assertStatus(t, r, 200)
		var list struct {
			Items []any `json:"items"`
		}
		decode(t, r, &list)
		if len(list.Items) != 3 {
			t.Fatalf("items=%d want=3", len(list.Items))
		}
	})
}
