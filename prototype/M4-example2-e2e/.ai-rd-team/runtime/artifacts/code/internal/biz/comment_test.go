package biz

import (
	"context"
	"testing"

	"github.com/go-kratos/kratos/v2/errors"
	"github.com/go-kratos/kratos/v2/log"
)

func newTestCommentUsecase(cr CommentRepo, pr PostRepo) *CommentUsecase {
	return NewCommentUsecase(cr, pr, log.DefaultLogger)
}

func TestComment_Create_PostNotFound(t *testing.T) {
	pr := &mockPostRepo{
		getByIDFn: func(ctx context.Context, id int64) (*Post, error) {
			return nil, ErrPostNotFound
		},
	}
	uc := newTestCommentUsecase(&mockCommentRepo{}, pr)
	_, err := uc.Create(context.Background(), 100, 1, "nice")
	if err == nil {
		t.Fatal("expected POST_NOT_FOUND")
	}
	if errors.FromError(err).Reason != "POST_NOT_FOUND" {
		t.Fatalf("want POST_NOT_FOUND, got %q", errors.FromError(err).Reason)
	}
}

func TestComment_Create_Success(t *testing.T) {
	pr := &mockPostRepo{
		getByIDFn: func(ctx context.Context, id int64) (*Post, error) {
			return &Post{ID: id}, nil
		},
	}
	var captured *Comment
	cr := &mockCommentRepo{
		createFn: func(ctx context.Context, c *Comment) (*Comment, error) {
			c.ID = 55
			captured = c
			return c, nil
		},
	}
	uc := newTestCommentUsecase(cr, pr)
	c, err := uc.Create(context.Background(), 100, 1, "  nice post  ")
	if err != nil {
		t.Fatalf("unexpected: %v", err)
	}
	if c.ID != 55 {
		t.Fatalf("want ID=55, got %d", c.ID)
	}
	if captured.Body != "nice post" {
		t.Fatalf("body should be trimmed, got %q", captured.Body)
	}
}

func TestComment_Create_EmptyBodyValidation(t *testing.T) {
	pr := &mockPostRepo{
		getByIDFn: func(ctx context.Context, id int64) (*Post, error) {
			return &Post{ID: id}, nil
		},
	}
	uc := newTestCommentUsecase(&mockCommentRepo{}, pr)
	_, err := uc.Create(context.Background(), 100, 1, "   ")
	if err == nil {
		t.Fatal("expected VALIDATION_FAILED")
	}
	if errors.FromError(err).Reason != "VALIDATION_FAILED" {
		t.Fatalf("want VALIDATION_FAILED, got %q", errors.FromError(err).Reason)
	}
}

func TestComment_ListByPost_PostNotFound(t *testing.T) {
	pr := &mockPostRepo{
		getByIDFn: func(ctx context.Context, id int64) (*Post, error) {
			return nil, ErrPostNotFound
		},
	}
	uc := newTestCommentUsecase(&mockCommentRepo{}, pr)
	_, err := uc.ListByPost(context.Background(), 999)
	if err == nil {
		t.Fatal("expected POST_NOT_FOUND")
	}
	if errors.FromError(err).Reason != "POST_NOT_FOUND" {
		t.Fatalf("want POST_NOT_FOUND, got %q", errors.FromError(err).Reason)
	}
}

func TestComment_ListByPost_Success(t *testing.T) {
	pr := &mockPostRepo{
		getByIDFn: func(ctx context.Context, id int64) (*Post, error) {
			return &Post{ID: id}, nil
		},
	}
	cr := &mockCommentRepo{
		listByPostFn: func(ctx context.Context, postID int64) ([]*Comment, error) {
			return []*Comment{{ID: 1, PostID: postID, Body: "a"}, {ID: 2, PostID: postID, Body: "b"}}, nil
		},
	}
	uc := newTestCommentUsecase(cr, pr)
	list, err := uc.ListByPost(context.Background(), 1)
	if err != nil {
		t.Fatalf("unexpected: %v", err)
	}
	if len(list) != 2 {
		t.Fatalf("want 2 comments, got %d", len(list))
	}
}
