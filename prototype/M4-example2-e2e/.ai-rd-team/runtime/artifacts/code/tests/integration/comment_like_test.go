package integration

import (
	"net/http"
	"testing"
)

// TestComment 覆盖评论的正常路径与异常。
func TestComment(t *testing.T) {
	skipIfAppNotReady(t)

	t.Run("Create_NoToken_401", func(t *testing.T) {
		resp := apiCall(t, http.MethodPost, pathComments(1), map[string]interface{}{
			"content": "hi",
		}, "")
		assertStatus(t, resp, http.StatusUnauthorized)
	})

	t.Run("Create_PostNotFound_404", func(t *testing.T) {
		u := createTestUser(t, "c_nf")
		resp := apiCall(t, http.MethodPost, pathComments(99999990), map[string]interface{}{
			"content": "hi",
		}, u.Token)
		assertStatus(t, resp, http.StatusNotFound)
		assertReason(t, resp, "POST_NOT_FOUND")
	})

	t.Run("List_OK", func(t *testing.T) {
		alice := createTestUser(t, "c_ok_a")
		bob := createTestUser(t, "c_ok_b")
		postID := createTestPost(t, alice, "post for comments", nil)

		r1 := apiCall(t, http.MethodPost, pathComments(postID), map[string]interface{}{"content": "first"}, bob.Token)
		assertStatus(t, r1, http.StatusOK)
		r2 := apiCall(t, http.MethodPost, pathComments(postID), map[string]interface{}{"content": "second"}, alice.Token)
		assertStatus(t, r2, http.StatusOK)

		lr := apiCall(t, http.MethodGet, pathComments(postID), nil, "")
		assertStatus(t, lr, http.StatusOK)
		var v struct {
			Comments []struct {
				Content string `json:"content"`
			} `json:"comments"`
			Total int64 `json:"total"`
		}
		lr.decode(t, &v)
		if v.Total < 2 {
			t.Fatalf("want total>=2, got %d", v.Total)
		}
	})
}

// TestLike 覆盖点赞/取消点赞、幂等性、401/404 路径。
func TestLike(t *testing.T) {
	skipIfAppNotReady(t)

	t.Run("Like_NoToken_401", func(t *testing.T) {
		resp := apiCall(t, http.MethodPost, pathLike(1), nil, "")
		assertStatus(t, resp, http.StatusUnauthorized)
	})

	t.Run("Unlike_NoToken_401", func(t *testing.T) {
		resp := apiCall(t, http.MethodDelete, pathLike(1), nil, "")
		assertStatus(t, resp, http.StatusUnauthorized)
	})

	t.Run("Like_PostNotFound_404", func(t *testing.T) {
		u := createTestUser(t, "like_nf")
		resp := apiCall(t, http.MethodPost, pathLike(99999991), nil, u.Token)
		assertStatus(t, resp, http.StatusNotFound)
		assertReason(t, resp, "POST_NOT_FOUND")
	})

	t.Run("Unlike_WhenNotLiked_Idempotent", func(t *testing.T) {
		alice := createTestUser(t, "lk_a")
		bob := createTestUser(t, "lk_b")
		postID := createTestPost(t, alice, "likeme", nil)

		// bob 从未点赞，直接 unlike 也应成功（幂等），likes_count 保持 0
		resp := apiCall(t, http.MethodDelete, pathLike(postID), nil, bob.Token)
		assertStatus(t, resp, http.StatusOK)
		var v struct {
			LikesCount int64 `json:"likes_count"`
		}
		resp.decode(t, &v)
		if v.LikesCount != 0 {
			t.Fatalf("idempotent unlike: want 0 got %d", v.LikesCount)
		}
	})
}
