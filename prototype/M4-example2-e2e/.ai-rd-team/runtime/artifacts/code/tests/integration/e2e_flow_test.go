package integration

import (
	"fmt"
	"net/http"
	"net/url"
	"testing"
)

// TestE2E_BlogFlow walks a single user through the full product journey
// described in data-interfaces.yaml §tests.e2e:
//
//   register → login → create post → get post → list (filtered by tag)
//   → like (twice, idempotent) → comment → list comments → delete post
//   → verify 404
//
// The goal is NOT to re-assert every single rule (each unit file covers
// those) but to confirm the pieces hang together as seen by a real client.
func TestE2E_BlogFlow(t *testing.T) {
	_ = setupTestDB(t)
	client := newAPIClient(t)

	// --- 1. register + login ---------------------------------------------
	u := createTestUser(t, client, uniqueEmail(t, "e2e"), "pw-e2e-1234", "e2e-user")
	authed := client.withToken(u.Token)

	// GET /v1/users/me must succeed now that we have a token.
	meResp := authed.apiCall(http.MethodGet, "/v1/users/me", nil, nil)
	if meResp.Status != http.StatusOK {
		t.Fatalf("GET /v1/users/me: %d %s", meResp.Status, meResp.Body)
	}

	// --- 2. create post --------------------------------------------------
	createResp := authed.apiCall(http.MethodPost, "/v1/posts", map[string]interface{}{
		"title":         "My first post",
		"body_markdown": "# hi\nworld",
		"tags":          []string{"intro", "hello"},
	}, nil)
	if createResp.Status != http.StatusOK && createResp.Status != http.StatusCreated {
		t.Fatalf("create post: %d %s", createResp.Status, createResp.Body)
	}
	var post postDTO
	if err := createResp.decode(&post); err != nil {
		t.Fatalf("decode post: %v", err)
	}
	if post.Id == 0 {
		t.Fatalf("post id is 0: %+v", post)
	}

	// --- 3. get post (public) --------------------------------------------
	getResp := client.apiCall(http.MethodGet, fmt.Sprintf("/v1/posts/%d", post.Id), nil, nil)
	if getResp.Status != http.StatusOK {
		t.Fatalf("get post: %d %s", getResp.Status, getResp.Body)
	}

	// --- 4. list with tag filter -----------------------------------------
	listResp := client.apiCall(http.MethodGet, "/v1/posts", nil,
		url.Values{"tag": {"intro"}})
	if listResp.Status != http.StatusOK {
		t.Fatalf("list posts: %d %s", listResp.Status, listResp.Body)
	}
	var list postListDTO
	if err := listResp.decode(&list); err != nil {
		t.Fatalf("decode list: %v", err)
	}
	if list.Total < 1 {
		t.Errorf("expected tag=intro to match at least 1, total=%d", list.Total)
	}
	foundOurs := false
	for _, p := range list.Items {
		if p.Id == post.Id {
			foundOurs = true
			break
		}
	}
	if !foundOurs {
		t.Errorf("our post %d not in tag=intro list: %+v", post.Id, list.Items)
	}

	// --- 5. like + like (idempotent) -------------------------------------
	likePath := fmt.Sprintf("/v1/posts/%d/like", post.Id)
	if r := authed.apiCall(http.MethodPost, likePath, nil, nil); r.Status != http.StatusOK {
		t.Fatalf("first like: %d %s", r.Status, r.Body)
	}
	if r := authed.apiCall(http.MethodPost, likePath, nil, nil); r.Status != http.StatusOK {
		t.Fatalf("second like (idempotent): %d %s", r.Status, r.Body)
	}
	// Verify count = 1 (idempotency).
	getResp2 := client.apiCall(http.MethodGet, fmt.Sprintf("/v1/posts/%d", post.Id), nil, nil)
	var post2 postDTO
	_ = getResp2.decode(&post2)
	if post2.LikesCount != 1 {
		t.Errorf("likes_count after two likes by same user: got %d want 1", post2.LikesCount)
	}

	// --- 6. comment + list comments --------------------------------------
	cResp := authed.apiCall(http.MethodPost,
		fmt.Sprintf("/v1/posts/%d/comments", post.Id),
		map[string]string{"content": "nice post"}, nil)
	if cResp.Status != http.StatusOK && cResp.Status != http.StatusCreated {
		t.Fatalf("create comment: %d %s", cResp.Status, cResp.Body)
	}

	clResp := client.apiCall(http.MethodGet,
		fmt.Sprintf("/v1/posts/%d/comments", post.Id), nil, nil)
	if clResp.Status != http.StatusOK {
		t.Fatalf("list comments: %d %s", clResp.Status, clResp.Body)
	}
	var cList commentListDTO
	if err := clResp.decode(&cList); err != nil {
		t.Fatalf("decode comments: %v", err)
	}
	if cList.Total != 1 {
		t.Errorf("comments total: got %d want 1", cList.Total)
	}

	// --- 7. delete post + verify 404 + cascade ---------------------------
	delResp := authed.apiCall(http.MethodDelete,
		fmt.Sprintf("/v1/posts/%d", post.Id), nil, nil)
	if delResp.Status != http.StatusOK && delResp.Status != http.StatusNoContent {
		t.Fatalf("delete post: %d %s", delResp.Status, delResp.Body)
	}

	verifyResp := client.apiCall(http.MethodGet,
		fmt.Sprintf("/v1/posts/%d", post.Id), nil, nil)
	if verifyResp.Status != http.StatusNotFound {
		t.Fatalf("post still exists after delete: %d %s", verifyResp.Status, verifyResp.Body)
	}
	assertErrorReason(t, verifyResp, "POST_NOT_FOUND")

	// Comments should have been cascaded away — listing a deleted post's
	// comments is allowed to return either 404 (post not found) or an
	// empty list. Both are acceptable per the spec (not explicitly
	// pinned); we just verify it's *not* still returning the stale row.
	verifyCResp := client.apiCall(http.MethodGet,
		fmt.Sprintf("/v1/posts/%d/comments", post.Id), nil, nil)
	switch verifyCResp.Status {
	case http.StatusNotFound:
		// ok
	case http.StatusOK:
		var l commentListDTO
		if err := verifyCResp.decode(&l); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if l.Total != 0 {
			t.Errorf("cascade failed: %d comments remain", l.Total)
		}
	default:
		t.Errorf("unexpected status listing deleted post's comments: %d %s",
			verifyCResp.Status, verifyCResp.Body)
	}
}
