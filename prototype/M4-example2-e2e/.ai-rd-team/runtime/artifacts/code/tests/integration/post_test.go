package integration

import (
	"fmt"
	"net/http"
	"net/url"
	"testing"
)

// postDTO mirrors the JSON shape of a Post returned by the API. Only the
// fields the tests actually assert on are declared; unknown fields are
// ignored by encoding/json so the suite is tolerant of additional columns
// (e.g. updated_at) being added later.
type postDTO struct {
	Id           int64    `json:"id"`
	AuthorId     int64    `json:"author_id"`
	Title        string   `json:"title"`
	BodyMarkdown string   `json:"body_markdown"`
	Tags         []string `json:"tags"`
	LikesCount   int64    `json:"likes_count"`
}

type postListDTO struct {
	Items []postDTO `json:"items"`
	Total int64     `json:"total"`
}

// TestPost_CRUD covers the full CRUD happy-path on /v1/posts plus the
// author-only authorization rule defined in data-interfaces.yaml.
func TestPost_CRUD(t *testing.T) {
	_ = setupTestDB(t)
	client := newAPIClient(t)

	author := createTestUser(t, client, uniqueEmail(t, "post-author"), "pw-aaaaaaa1", "author")
	other := createTestUser(t, client, uniqueEmail(t, "post-other"), "pw-aaaaaaa1", "other")
	authed := client.withToken(author.Token)
	otherAuthed := client.withToken(other.Token)

	// --- Create -----------------------------------------------------------
	var created postDTO
	t.Run("create by authed user returns 200 and populated post", func(t *testing.T) {
		resp := authed.apiCall(http.MethodPost, "/v1/posts", map[string]interface{}{
			"title":         "Hello Kratos",
			"body_markdown": "# intro\nbody",
			"tags":          []string{"go", "kratos"},
		}, nil)
		if resp.Status != http.StatusOK && resp.Status != http.StatusCreated {
			t.Fatalf("want 200/201, got %d body=%s", resp.Status, resp.Body)
		}
		if err := resp.decode(&created); err != nil {
			t.Fatalf("decode: %v (%s)", err, resp.Body)
		}
		if created.Id == 0 || created.AuthorId != author.ID {
			t.Errorf("unexpected created: %+v (author want %d)", created, author.ID)
		}
		if len(created.Tags) != 2 {
			t.Errorf("tags lost: %+v", created.Tags)
		}
	})

	t.Run("create without token -> 401 UNAUTHORIZED", func(t *testing.T) {
		resp := client.apiCall(http.MethodPost, "/v1/posts", map[string]interface{}{
			"title": "x", "body_markdown": "y", "tags": []string{},
		}, nil)
		if resp.Status != http.StatusUnauthorized {
			t.Fatalf("want 401, got %d body=%s", resp.Status, resp.Body)
		}
	})

	// --- Read -------------------------------------------------------------
	t.Run("GET /v1/posts/{id} is public", func(t *testing.T) {
		resp := client.apiCall(http.MethodGet, fmt.Sprintf("/v1/posts/%d", created.Id), nil, nil)
		if resp.Status != http.StatusOK {
			t.Fatalf("want 200, got %d body=%s", resp.Status, resp.Body)
		}
		var got postDTO
		if err := resp.decode(&got); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if got.Id != created.Id || got.Title != "Hello Kratos" {
			t.Errorf("round-trip mismatch: %+v", got)
		}
	})

	t.Run("GET non-existent post -> 404 POST_NOT_FOUND", func(t *testing.T) {
		resp := client.apiCall(http.MethodGet, "/v1/posts/99999999", nil, nil)
		if resp.Status != http.StatusNotFound {
			t.Fatalf("want 404, got %d body=%s", resp.Status, resp.Body)
		}
		assertErrorReason(t, resp, "POST_NOT_FOUND")
	})

	// --- Update -----------------------------------------------------------
	t.Run("update by author succeeds", func(t *testing.T) {
		resp := authed.apiCall(http.MethodPut, fmt.Sprintf("/v1/posts/%d", created.Id),
			map[string]interface{}{
				"title":         "Hello Kratos v2",
				"body_markdown": "# updated",
				"tags":          []string{"go"},
			}, nil)
		if resp.Status != http.StatusOK {
			t.Fatalf("want 200, got %d body=%s", resp.Status, resp.Body)
		}
		var got postDTO
		if err := resp.decode(&got); err != nil {
			t.Fatalf("decode: %v", err)
		}
		if got.Title != "Hello Kratos v2" || len(got.Tags) != 1 {
			t.Errorf("update not reflected: %+v", got)
		}
	})

	t.Run("update by non-author -> 403 FORBIDDEN", func(t *testing.T) {
		resp := otherAuthed.apiCall(http.MethodPut, fmt.Sprintf("/v1/posts/%d", created.Id),
			map[string]interface{}{
				"title":         "hijack",
				"body_markdown": "nope",
				"tags":          []string{},
			}, nil)
		if resp.Status != http.StatusForbidden {
			t.Fatalf("want 403, got %d body=%s", resp.Status, resp.Body)
		}
		assertErrorReason(t, resp, "FORBIDDEN")
	})

	// --- Delete -----------------------------------------------------------
	t.Run("delete by non-author -> 403", func(t *testing.T) {
		resp := otherAuthed.apiCall(http.MethodDelete,
			fmt.Sprintf("/v1/posts/%d", created.Id), nil, nil)
		if resp.Status != http.StatusForbidden {
			t.Fatalf("want 403, got %d body=%s", resp.Status, resp.Body)
		}
	})

	t.Run("delete by author succeeds and subsequent GET returns 404", func(t *testing.T) {
		resp := authed.apiCall(http.MethodDelete,
			fmt.Sprintf("/v1/posts/%d", created.Id), nil, nil)
		if resp.Status != http.StatusOK && resp.Status != http.StatusNoContent {
			t.Fatalf("want 200/204, got %d body=%s", resp.Status, resp.Body)
		}

		get := client.apiCall(http.MethodGet,
			fmt.Sprintf("/v1/posts/%d", created.Id), nil, nil)
		if get.Status != http.StatusNotFound {
			t.Fatalf("want 404 after delete, got %d body=%s", get.Status, get.Body)
		}
	})
}

// TestPost_ListAndTagFilter covers pagination bounds and the `tag` query
// filter described in the spec (§4.4 and data-interfaces http_routes).
//
// Strategy: seed N posts with mixed tags in a single fresh DB, then hit
// /v1/posts with various query combos and verify (a) total is correct,
// (b) page size is honoured, (c) default size == 20, (d) max size == 100.
func TestPost_ListAndTagFilter(t *testing.T) {
	_ = setupTestDB(t)
	client := newAPIClient(t)

	author := createTestUser(t, client, uniqueEmail(t, "lister"), "pw-aaaaaaa1", "lister")
	authed := client.withToken(author.Token)

	// Seed 25 posts: 10 tagged "go", 10 tagged "py", 5 tagged both.
	seed := func(title string, tags []string) {
		resp := authed.apiCall(http.MethodPost, "/v1/posts", map[string]interface{}{
			"title":         title,
			"body_markdown": "body-" + title,
			"tags":          tags,
		}, nil)
		if resp.Status < 200 || resp.Status >= 300 {
			t.Fatalf("seed %q: status=%d body=%s", title, resp.Status, resp.Body)
		}
	}
	for i := 0; i < 10; i++ {
		seed(fmt.Sprintf("go-only-%d", i), []string{"go"})
	}
	for i := 0; i < 10; i++ {
		seed(fmt.Sprintf("py-only-%d", i), []string{"py"})
	}
	for i := 0; i < 5; i++ {
		seed(fmt.Sprintf("both-%d", i), []string{"go", "py"})
	}

	cases := []struct {
		name      string
		query     url.Values
		wantTotal int64
		wantItems int // items in this page
	}{
		{
			name:      "no params -> default size 20, total 25",
			query:     url.Values{},
			wantTotal: 25,
			wantItems: 20,
		},
		{
			name:      "page=2 with default size -> remaining 5",
			query:     url.Values{"page": {"2"}},
			wantTotal: 25,
			wantItems: 5,
		},
		{
			name:      "custom size=10",
			query:     url.Values{"size": {"10"}},
			wantTotal: 25,
			wantItems: 10,
		},
		{
			name:      "tag=go -> 15 (10 go-only + 5 both)",
			query:     url.Values{"tag": {"go"}, "size": {"100"}},
			wantTotal: 15,
			wantItems: 15,
		},
		{
			name:      "tag=py -> 15",
			query:     url.Values{"tag": {"py"}, "size": {"100"}},
			wantTotal: 15,
			wantItems: 15,
		},
		{
			name:      "tag=missing -> empty",
			query:     url.Values{"tag": {"does-not-exist"}},
			wantTotal: 0,
			wantItems: 0,
		},
		{
			name:      "size>100 clamped to 100",
			query:     url.Values{"size": {"500"}},
			wantTotal: 25,
			wantItems: 25, // only 25 seeded, so still 25
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			resp := client.apiCall(http.MethodGet, "/v1/posts", nil, tc.query)
			if resp.Status != http.StatusOK {
				t.Fatalf("want 200, got %d body=%s", resp.Status, resp.Body)
			}
			var list postListDTO
			if err := resp.decode(&list); err != nil {
				t.Fatalf("decode: %v (%s)", err, resp.Body)
			}
			if list.Total != tc.wantTotal {
				t.Errorf("total: got %d want %d", list.Total, tc.wantTotal)
			}
			if len(list.Items) != tc.wantItems {
				t.Errorf("items: got %d want %d", len(list.Items), tc.wantItems)
			}
		})
	}
}
