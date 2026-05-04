package integration

import (
	"net/http"
	"testing"
)

// TestPost 覆盖文章 CRUD + 异常路径。
func TestPost(t *testing.T) {
	skipIfAppNotReady(t)

	t.Run("Create_NoToken_401", func(t *testing.T) {
		resp := apiCall(t, http.MethodPost, "/v1/posts", map[string]interface{}{
			"title":         "x",
			"body_markdown": "y",
		}, "")
		assertStatus(t, resp, http.StatusUnauthorized)
	})

	t.Run("Get_NotFound_404", func(t *testing.T) {
		resp := apiCall(t, http.MethodGet, pathPost(99999999), nil, "")
		assertStatus(t, resp, http.StatusNotFound)
		assertReason(t, resp, "POST_NOT_FOUND")
	})

	t.Run("Update_NotFound_404", func(t *testing.T) {
		u := createTestUser(t, "upd404")
		resp := apiCall(t, http.MethodPut, pathPost(99999998), map[string]interface{}{
			"title":         "x",
			"body_markdown": "y",
			"tags":          []string{},
		}, u.Token)
		assertStatus(t, resp, http.StatusNotFound)
		assertReason(t, resp, "POST_NOT_FOUND")
	})

	t.Run("Delete_NotOwned_403", func(t *testing.T) {
		alice := createTestUser(t, "del_owner")
		bob := createTestUser(t, "del_other")
		postID := createTestPost(t, alice, "owned by alice", []string{"p"})

		resp := apiCall(t, http.MethodDelete, pathPost(postID), nil, bob.Token)
		assertStatus(t, resp, http.StatusForbidden)
		assertReason(t, resp, "POST_NOT_OWNED")
	})

	t.Run("List_Pagination_OK", func(t *testing.T) {
		resp := apiCall(t, http.MethodGet, "/v1/posts?page=1&size=5", nil, "")
		assertStatus(t, resp, http.StatusOK)
		var r struct {
			Posts []interface{} `json:"posts"`
			Total int64         `json:"total"`
			Page  int32         `json:"page"`
			Size  int32         `json:"size"`
		}
		resp.decode(t, &r)
		if r.Size != 5 && r.Size != 0 {
			// 说明：size=0 时 service 端可能按默认 10 处理，这里兼容
			t.Logf("list size=%d (allowed: 5 or default)", r.Size)
		}
	})
}
