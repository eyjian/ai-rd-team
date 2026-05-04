package biz

import (
	"context"
	"testing"
	"time"

	"github.com/go-kratos/kratos/v2/errors"
	"github.com/go-kratos/kratos/v2/log"
)

func newTestPostUsecase(pr PostRepo, lr PostLikeRepo) *PostUsecase {
	if lr == nil {
		lr = newMockPostLikeRepo()
	}
	return NewPostUsecase(pr, lr, log.DefaultLogger)
}

func TestPost_Create_Success(t *testing.T) {
	var captured *Post
	pr := &mockPostRepo{
		createFn: func(ctx context.Context, p *Post) (*Post, error) {
			p.ID = 10
			p.CreatedAt = time.Now()
			p.UpdatedAt = p.CreatedAt
			captured = p
			return p, nil
		},
	}
	uc := newTestPostUsecase(pr, nil)
	p, err := uc.Create(context.Background(), 1, " hello ", "body", []string{"go", "", "go", " k "})
	if err != nil {
		t.Fatalf("unexpected: %v", err)
	}
	if p.ID != 10 {
		t.Fatalf("want ID=10, got %d", p.ID)
	}
	if captured.Title != "hello" {
		t.Fatalf("title should be trimmed, got %q", captured.Title)
	}
	if len(captured.Tags) != 2 || captured.Tags[0] != "go" || captured.Tags[1] != "k" {
		t.Fatalf("tags should be normalized+deduped, got %v", captured.Tags)
	}
}

func TestPost_Create_ValidationFailed(t *testing.T) {
	uc := newTestPostUsecase(&mockPostRepo{}, nil)
	_, err := uc.Create(context.Background(), 1, "   ", "body", nil)
	if err == nil {
		t.Fatal("expected validation error")
	}
	if errors.FromError(err).Reason != "VALIDATION_FAILED" {
		t.Fatalf("want VALIDATION_FAILED, got %q", errors.FromError(err).Reason)
	}
}

func TestPost_List_TagFilter(t *testing.T) {
	var gotTag string
	pr := &mockPostRepo{
		listFn: func(ctx context.Context, page, size int32, tag string) ([]*Post, int64, error) {
			gotTag = tag
			return []*Post{{ID: 1}}, 1, nil
		},
	}
	uc := newTestPostUsecase(pr, nil)
	posts, total, err := uc.List(context.Background(), 0, 0, " go ")
	if err != nil {
		t.Fatalf("unexpected: %v", err)
	}
	if total != 1 || len(posts) != 1 {
		t.Fatalf("want 1 post, got total=%d len=%d", total, len(posts))
	}
	if gotTag != "go" {
		t.Fatalf("tag should be trimmed, got %q", gotTag)
	}
}

func TestPost_Update_NonAuthorForbidden(t *testing.T) {
	pr := &mockPostRepo{
		getByIDFn: func(ctx context.Context, id int64) (*Post, error) {
			return &Post{ID: id, AuthorID: 1, Title: "t"}, nil
		},
	}
	uc := newTestPostUsecase(pr, nil)
	_, err := uc.Update(context.Background(), 2, 100, "new-title", "body", nil)
	if err == nil {
		t.Fatal("expected forbidden")
	}
	if errors.FromError(err).Reason != "POST_FORBIDDEN" {
		t.Fatalf("want POST_FORBIDDEN, got %q", errors.FromError(err).Reason)
	}
}

func TestPost_Update_NotFound(t *testing.T) {
	pr := &mockPostRepo{
		getByIDFn: func(ctx context.Context, id int64) (*Post, error) {
			return nil, ErrPostNotFound
		},
	}
	uc := newTestPostUsecase(pr, nil)
	_, err := uc.Update(context.Background(), 1, 100, "t", "b", nil)
	if err == nil {
		t.Fatal("expected not found")
	}
	if errors.FromError(err).Reason != "POST_NOT_FOUND" {
		t.Fatalf("want POST_NOT_FOUND, got %q", errors.FromError(err).Reason)
	}
}

func TestPost_Delete_AuthorSuccess(t *testing.T) {
	deleted := false
	pr := &mockPostRepo{
		getByIDFn: func(ctx context.Context, id int64) (*Post, error) {
			return &Post{ID: id, AuthorID: 1}, nil
		},
		deleteFn: func(ctx context.Context, id int64) error {
			deleted = true
			return nil
		},
	}
	uc := newTestPostUsecase(pr, nil)
	if err := uc.Delete(context.Background(), 1, 100); err != nil {
		t.Fatalf("unexpected: %v", err)
	}
	if !deleted {
		t.Fatal("Delete should be called")
	}
}

// TestPost_Like_Idempotent 点赞幂等：连续 Add 两次只 +1。
func TestPost_Like_Idempotent(t *testing.T) {
	pr := &mockPostRepo{
		getByIDFn: func(ctx context.Context, id int64) (*Post, error) {
			return &Post{ID: id, AuthorID: 9}, nil
		},
	}
	lr := newMockPostLikeRepo()
	uc := newTestPostUsecase(pr, lr)

	if err := uc.Like(context.Background(), 100, 1); err != nil {
		t.Fatalf("first like: %v", err)
	}
	if err := uc.Like(context.Background(), 100, 1); err != nil {
		t.Fatalf("second like: %v", err)
	}
	if len(lr.likes) != 1 {
		t.Fatalf("want 1 like record (idempotent), got %d", len(lr.likes))
	}
}

// TestPost_Unlike_Idempotent 取消点赞幂等：未点过赞也不报错。
func TestPost_Unlike_Idempotent(t *testing.T) {
	pr := &mockPostRepo{
		getByIDFn: func(ctx context.Context, id int64) (*Post, error) {
			return &Post{ID: id}, nil
		},
	}
	lr := newMockPostLikeRepo()
	uc := newTestPostUsecase(pr, lr)
	// 未点过也不应报错
	if err := uc.Unlike(context.Background(), 100, 1); err != nil {
		t.Fatalf("unlike on non-existing: %v", err)
	}
	// 点一次再取消
	_ = uc.Like(context.Background(), 100, 1)
	if err := uc.Unlike(context.Background(), 100, 1); err != nil {
		t.Fatalf("unlike existing: %v", err)
	}
	// 再取消仍然无错
	if err := uc.Unlike(context.Background(), 100, 1); err != nil {
		t.Fatalf("double unlike: %v", err)
	}
	if len(lr.likes) != 0 {
		t.Fatalf("want 0 likes, got %d", len(lr.likes))
	}
}

func TestPost_Like_PostNotFound(t *testing.T) {
	pr := &mockPostRepo{
		getByIDFn: func(ctx context.Context, id int64) (*Post, error) {
			return nil, ErrPostNotFound
		},
	}
	uc := newTestPostUsecase(pr, newMockPostLikeRepo())
	err := uc.Like(context.Background(), 1, 1)
	if err == nil {
		t.Fatal("expected POST_NOT_FOUND")
	}
	if errors.FromError(err).Reason != "POST_NOT_FOUND" {
		t.Fatalf("want POST_NOT_FOUND, got %q", errors.FromError(err).Reason)
	}
}
