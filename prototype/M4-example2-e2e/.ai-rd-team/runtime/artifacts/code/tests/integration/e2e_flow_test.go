package integration

import (
	"net/http"
	"testing"
)

// TestE2E_FullFlow 按照 REQUIREMENT.md 验收路径走一遍：
// 注册 → 登录 → 发帖 → 查帖 → 列表 → 评论 → 点赞 → 幂等 → 取消 → 删除。
//
// 设计要点：
//   - 同一个用例内共享 user/post，避免重复 setup；
//   - 另起 otherUser 用于 403 POST_NOT_OWNED 覆盖；
//   - 每一步都断言 status + 关键业务字段；
//   - 取消/点赞验证 likes_count 幂等语义。
func TestE2E_FullFlow(t *testing.T) {
	skipIfAppNotReady(t)

	alice := createTestUser(t, "alice")
	bob := createTestUser(t, "bob")

	// 1. 发帖
	postID := createTestPost(t, alice, "Hello Kratos", []string{"golang", "kratos"})

	// 2. 查单篇
	t.Run("GetPost", func(t *testing.T) {
		resp := apiCall(t, http.MethodGet, pathPost(postID), nil, "")
		assertStatus(t, resp, http.StatusOK)
		var p struct {
			ID    int64  `json:"id"`
			Title string `json:"title"`
		}
		resp.decode(t, &p)
		if p.ID != postID || p.Title != "Hello Kratos" {
			t.Fatalf("post mismatch: %+v", p)
		}
	})

	// 3. 列表按 tag 过滤
	t.Run("ListByTag", func(t *testing.T) {
		resp := apiCall(t, http.MethodGet, "/v1/posts?page=1&size=10&tag=golang", nil, "")
		assertStatus(t, resp, http.StatusOK)
		var r struct {
			Posts []struct {
				ID int64 `json:"id"`
			} `json:"posts"`
			Total int64 `json:"total"`
		}
		resp.decode(t, &r)
		if r.Total < 1 {
			t.Fatalf("list total should >= 1, got=%d", r.Total)
		}
		found := false
		for _, p := range r.Posts {
			if p.ID == postID {
				found = true
			}
		}
		if !found {
			t.Fatalf("list does not contain post %d", postID)
		}
	})

	// 4. 更新别人帖子 → 403
	t.Run("UpdateOthers_Forbidden", func(t *testing.T) {
		resp := apiCall(t, http.MethodPut, pathPost(postID), map[string]interface{}{
			"title":         "Hacked",
			"body_markdown": "hacked",
			"tags":          []string{"x"},
		}, bob.Token)
		assertStatus(t, resp, http.StatusForbidden)
		assertReason(t, resp, "POST_NOT_OWNED")
	})

	// 5. 作者自己更新 → 200
	t.Run("UpdateByAuthor", func(t *testing.T) {
		resp := apiCall(t, http.MethodPut, pathPost(postID), map[string]interface{}{
			"title":         "Hello Kratos v2",
			"body_markdown": "# updated",
			"tags":          []string{"golang"},
		}, alice.Token)
		assertStatus(t, resp, http.StatusOK)
	})

	// 6. 评论
	t.Run("CreateComment", func(t *testing.T) {
		resp := apiCall(t, http.MethodPost, pathComments(postID), map[string]interface{}{
			"content": "nice post",
		}, bob.Token)
		assertStatus(t, resp, http.StatusOK)
	})

	t.Run("ListComments", func(t *testing.T) {
		resp := apiCall(t, http.MethodGet, pathComments(postID), nil, "")
		assertStatus(t, resp, http.StatusOK)
		var r struct {
			Comments []struct {
				Content string `json:"content"`
			} `json:"comments"`
			Total int64 `json:"total"`
		}
		resp.decode(t, &r)
		if r.Total < 1 {
			t.Fatalf("comments total should >= 1")
		}
	})

	// 7. 点赞 & 幂等 & 取消
	t.Run("LikeIdempotent", func(t *testing.T) {
		r1 := apiCall(t, http.MethodPost, pathLike(postID), nil, bob.Token)
		assertStatus(t, r1, http.StatusOK)
		var v1 struct {
			LikesCount int64 `json:"likes_count"`
			Liked      bool  `json:"liked"`
		}
		r1.decode(t, &v1)
		if v1.LikesCount != 1 || !v1.Liked {
			t.Fatalf("after 1st like: likes_count=%d liked=%v", v1.LikesCount, v1.Liked)
		}

		// 幂等：再点一次还应该是 1
		r2 := apiCall(t, http.MethodPost, pathLike(postID), nil, bob.Token)
		assertStatus(t, r2, http.StatusOK)
		var v2 struct {
			LikesCount int64 `json:"likes_count"`
		}
		r2.decode(t, &v2)
		if v2.LikesCount != 1 {
			t.Fatalf("idempotent like: want 1 got %d", v2.LikesCount)
		}

		// 取消点赞
		r3 := apiCall(t, http.MethodDelete, pathLike(postID), nil, bob.Token)
		assertStatus(t, r3, http.StatusOK)
		var v3 struct {
			LikesCount int64 `json:"likes_count"`
			Liked      bool  `json:"liked"`
		}
		r3.decode(t, &v3)
		if v3.LikesCount != 0 || v3.Liked {
			t.Fatalf("after unlike: likes_count=%d liked=%v", v3.LikesCount, v3.Liked)
		}
	})

	// 8. 删帖 & 404
	t.Run("DeleteByAuthor_Then404", func(t *testing.T) {
		resp := apiCall(t, http.MethodDelete, pathPost(postID), nil, alice.Token)
		assertStatus(t, resp, http.StatusOK)

		// 再查询应 404
		r2 := apiCall(t, http.MethodGet, pathPost(postID), nil, "")
		assertStatus(t, r2, http.StatusNotFound)
		assertReason(t, r2, "POST_NOT_FOUND")
	})
}
