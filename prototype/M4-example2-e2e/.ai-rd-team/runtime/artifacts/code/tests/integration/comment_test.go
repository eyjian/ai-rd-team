package integration

import (
	"fmt"
	"net/http"
	"net/url"
	"testing"
)

type commentDTO struct {
	Id       int64  `json:"id"`
	PostId   int64  `json:"post_id"`
	AuthorId int64  `json:"author_id"`
	Content  string `json:"content"`
}

type commentListDTO struct {
	Items []commentDTO `json:"items"`
	Total int64        `json:"total"`
}

type likeRespDTO struct {
	LikesCount int64 `json:"likes_count"`
}

// TestComment_Create covers POST /v1/posts/{id}/comments and its auth /
// validation rules.
func TestComment_Create(t *testing.T) {
	_ = setupTestDB(t)
	client := newAPIClient(t)

	author := createTestUser(t, client, uniqueEmail(t, "c-author"), "pw-aaaaaaa1", "author")
	commenter := createTestUser(t, client, uniqueEmail(t, "c-user"), "pw-aaaaaaa1", "commenter")
	authored := client.withToken(author.Token)
	commAuthed := client.withToken(commenter.Token)

	// Fixture: one published post.
	var post postDTO
	{
		resp := authored.apiCall(http.MethodPost, "/v1/posts", map[string]interface{}{
			"title":         "Discuss me",
			"body_markdown": "body",
			"tags":          []string{"meta"},
		}, nil)
		if resp.Status < 200 || resp.Status >= 300 {
			t.Fatalf("seed post: %d %s", resp.Status, resp.Body)
		}
		if err := resp.decode(&post); err != nil {
			t.Fatalf("decode seed: %v", err)
		}
	}

	t.Run("create comment without token -> 401", func(t *testing.T) {
		resp := client.apiCall(http.MethodPost,
			fmt.Sprintf("/v1/posts/%d/comments", post.Id),
			map[string]string{"content": "hi"}, nil)
		if resp.Status != http.StatusUnauthorized {
			t.Fatalf("want 401, got %d %s", resp.Status, resp.Body)
		}
	})

	t.Run("create comment with token returns created comment", func(t *testing.T) {
		resp := commAuthed.apiCall(http.MethodPost,
			fmt.Sprintf("/v1/posts/%d/comments", post.Id),
			map[string]string{"content": "first!"}, nil)
		if resp.Status != http.StatusOK && resp.Status != http.StatusCreated {
			t.Fatalf("want 200/201, got %d %s", resp.Status, resp.Body)
		}
		var got commentDTO
		if err := resp.decode(&got); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if got.Id == 0 || got.PostId != post.Id || got.AuthorId != commenter.ID || got.Content != "first!" {
			t.Errorf("bad comment: %+v", got)
		}
	})

	t.Run("create comment on missing post -> 404 POST_NOT_FOUND", func(t *testing.T) {
		resp := commAuthed.apiCall(http.MethodPost,
			"/v1/posts/99999999/comments",
			map[string]string{"content": "ghost"}, nil)
		if resp.Status != http.StatusNotFound {
			t.Fatalf("want 404, got %d %s", resp.Status, resp.Body)
		}
		assertErrorReason(t, resp, "POST_NOT_FOUND")
	})

	t.Run("empty content -> 400 VALIDATION_FAILED", func(t *testing.T) {
		resp := commAuthed.apiCall(http.MethodPost,
			fmt.Sprintf("/v1/posts/%d/comments", post.Id),
			map[string]string{"content": ""}, nil)
		if resp.Status != http.StatusBadRequest {
			t.Fatalf("want 400, got %d %s", resp.Status, resp.Body)
		}
		assertErrorReason(t, resp, "VALIDATION_FAILED")
	})
}

// TestComment_List verifies the public listing endpoint plus pagination.
func TestComment_List(t *testing.T) {
	_ = setupTestDB(t)
	client := newAPIClient(t)

	author := createTestUser(t, client, uniqueEmail(t, "cl-author"), "pw-aaaaaaa1", "author")
	authored := client.withToken(author.Token)

	var post postDTO
	{
		resp := authored.apiCall(http.MethodPost, "/v1/posts", map[string]interface{}{
			"title": "chatty", "body_markdown": "b", "tags": []string{},
		}, nil)
		if err := resp.decode(&post); err != nil {
			t.Fatalf("decode: %v", err)
		}
	}

	// Seed 7 comments by the same author (auth rules allow self-commenting).
	for i := 0; i < 7; i++ {
		r := authored.apiCall(http.MethodPost,
			fmt.Sprintf("/v1/posts/%d/comments", post.Id),
			map[string]string{"content": fmt.Sprintf("msg-%d", i)}, nil)
		if r.Status < 200 || r.Status >= 300 {
			t.Fatalf("seed comment %d: %d %s", i, r.Status, r.Body)
		}
	}

	t.Run("list is public (no token) and returns total=7", func(t *testing.T) {
		resp := client.apiCall(http.MethodGet,
			fmt.Sprintf("/v1/posts/%d/comments", post.Id), nil, nil)
		if resp.Status != http.StatusOK {
			t.Fatalf("want 200, got %d %s", resp.Status, resp.Body)
		}
		var list commentListDTO
		if err := resp.decode(&list); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if list.Total != 7 {
			t.Errorf("total: got %d want 7", list.Total)
		}
		if len(list.Items) != 7 {
			t.Errorf("items: got %d want 7", len(list.Items))
		}
	})

	t.Run("list with size=3&page=2 -> 3 items", func(t *testing.T) {
		resp := client.apiCall(http.MethodGet,
			fmt.Sprintf("/v1/posts/%d/comments", post.Id),
			nil, url.Values{"size": {"3"}, "page": {"2"}})
		if resp.Status != http.StatusOK {
			t.Fatalf("want 200, got %d %s", resp.Status, resp.Body)
		}
		var list commentListDTO
		if err := resp.decode(&list); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if list.Total != 7 || len(list.Items) != 3 {
			t.Errorf("total=%d items=%d, want total=7 items=3", list.Total, len(list.Items))
		}
	})
}

// TestLike_Idempotent covers the whole lifecycle of
// POST/DELETE /v1/posts/{id}/like including the crucial idempotency rule:
// liking twice must NOT double-count the post.
//
// Reason the test is here (not in post_test.go): the idempotency contract
// lives next to the comment tests in spec §5.3 (幂等 + 事务).
func TestLike_Idempotent(t *testing.T) {
	_ = setupTestDB(t)
	client := newAPIClient(t)

	author := createTestUser(t, client, uniqueEmail(t, "like-a"), "pw-aaaaaaa1", "author")
	liker := createTestUser(t, client, uniqueEmail(t, "like-u"), "pw-aaaaaaa1", "liker")
	other := createTestUser(t, client, uniqueEmail(t, "like-o"), "pw-aaaaaaa1", "other")
	authored := client.withToken(author.Token)
	likerA := client.withToken(liker.Token)
	otherA := client.withToken(other.Token)

	var post postDTO
	{
		resp := authored.apiCall(http.MethodPost, "/v1/posts", map[string]interface{}{
			"title": "like me", "body_markdown": "b", "tags": []string{},
		}, nil)
		if err := resp.decode(&post); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if post.LikesCount != 0 {
			t.Fatalf("initial likes_count must be 0, got %d", post.LikesCount)
		}
	}
	likePath := fmt.Sprintf("/v1/posts/%d/like", post.Id)

	assertLikeCount := func(t *testing.T, want int64) {
		t.Helper()
		r := client.apiCall(http.MethodGet,
			fmt.Sprintf("/v1/posts/%d", post.Id), nil, nil)
		if r.Status != http.StatusOK {
			t.Fatalf("get post: %d %s", r.Status, r.Body)
		}
		var p postDTO
		if err := r.decode(&p); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if p.LikesCount != want {
			t.Errorf("likes_count: got %d want %d", p.LikesCount, want)
		}
	}

	t.Run("liking without token -> 401", func(t *testing.T) {
		resp := client.apiCall(http.MethodPost, likePath, nil, nil)
		if resp.Status != http.StatusUnauthorized {
			t.Fatalf("want 401, got %d %s", resp.Status, resp.Body)
		}
	})

	t.Run("first like by liker -> count=1", func(t *testing.T) {
		resp := likerA.apiCall(http.MethodPost, likePath, nil, nil)
		if resp.Status != http.StatusOK {
			t.Fatalf("want 200, got %d %s", resp.Status, resp.Body)
		}
		var out likeRespDTO
		if err := resp.decode(&out); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if out.LikesCount != 1 {
			t.Errorf("resp likes_count: got %d want 1", out.LikesCount)
		}
		assertLikeCount(t, 1)
	})

	t.Run("second like by SAME user is a no-op (idempotent) -> count still 1", func(t *testing.T) {
		resp := likerA.apiCall(http.MethodPost, likePath, nil, nil)
		if resp.Status != http.StatusOK {
			t.Fatalf("want 200 on idempotent like, got %d %s", resp.Status, resp.Body)
		}
		var out likeRespDTO
		_ = resp.decode(&out)
		if out.LikesCount != 1 {
			t.Errorf("idempotent like bumped count: got %d want 1", out.LikesCount)
		}
		assertLikeCount(t, 1)
	})

	t.Run("like by other user -> count=2", func(t *testing.T) {
		resp := otherA.apiCall(http.MethodPost, likePath, nil, nil)
		if resp.Status != http.StatusOK {
			t.Fatalf("want 200, got %d %s", resp.Status, resp.Body)
		}
		assertLikeCount(t, 2)
	})

	t.Run("unlike by liker -> count=1", func(t *testing.T) {
		resp := likerA.apiCall(http.MethodDelete, likePath, nil, nil)
		if resp.Status != http.StatusOK {
			t.Fatalf("want 200, got %d %s", resp.Status, resp.Body)
		}
		var out likeRespDTO
		_ = resp.decode(&out)
		if out.LikesCount != 1 {
			t.Errorf("after unlike: got %d want 1", out.LikesCount)
		}
		assertLikeCount(t, 1)
	})

	t.Run("unlike again by same user is idempotent no-op", func(t *testing.T) {
		resp := likerA.apiCall(http.MethodDelete, likePath, nil, nil)
		if resp.Status != http.StatusOK {
			t.Fatalf("want 200 on idempotent unlike, got %d %s", resp.Status, resp.Body)
		}
		assertLikeCount(t, 1)
	})

	t.Run("like on missing post -> 404 POST_NOT_FOUND", func(t *testing.T) {
		resp := likerA.apiCall(http.MethodPost, "/v1/posts/99999999/like", nil, nil)
		if resp.Status != http.StatusNotFound {
			t.Fatalf("want 404, got %d %s", resp.Status, resp.Body)
		}
		assertErrorReason(t, resp, "POST_NOT_FOUND")
	})
}
