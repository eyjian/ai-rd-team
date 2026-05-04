package biz

import (
	"context"
	"strings"
	"testing"

	kerrors "github.com/go-kratos/kratos/v2/errors"
)

func setupCommentUC(t *testing.T) (*CommentUsecase, *PostUsecase, int64) {
	t.Helper()
	ur := newFakeUserRepo()
	pr := newFakePostRepo()
	cr := newFakeCommentRepo()

	postUC := NewPostUsecase(pr, ur, testLogger())
	cuc := NewCommentUsecase(cr, pr, testLogger())
	userUC := NewUserUsecase(ur, &stubTokenIssuer{}, testLogger())

	u, err := userUC.Register(context.Background(), "a@b.com", "secret1", "a")
	if err != nil {
		t.Fatal(err)
	}
	return cuc, postUC, u.ID
}

func TestCommentUsecase_Create_Success(t *testing.T) {
	cuc, puc, authorID := setupCommentUC(t)
	p, err := puc.Create(context.Background(), authorID, "t", "b", nil)
	if err != nil {
		t.Fatal(err)
	}
	c, err := cuc.Create(context.Background(), p.ID, authorID, "  nice post  ")
	if err != nil {
		t.Fatal(err)
	}
	if c.Content != "nice post" {
		t.Fatalf("content not trimmed: %q", c.Content)
	}
	if c.ID == 0 {
		t.Fatalf("id not assigned")
	}
}

func TestCommentUsecase_Create_Validation(t *testing.T) {
	cuc, puc, authorID := setupCommentUC(t)
	p, _ := puc.Create(context.Background(), authorID, "t", "b", nil)

	_, err := cuc.Create(context.Background(), p.ID, authorID, "")
	if err == nil || kerrors.Reason(err) != "VALIDATION_FAILED" {
		t.Fatalf("expected VALIDATION_FAILED, got %v", err)
	}

	_, err = cuc.Create(context.Background(), p.ID, authorID, strings.Repeat("x", 2001))
	if err == nil || kerrors.Reason(err) != "VALIDATION_FAILED" {
		t.Fatalf("expected VALIDATION_FAILED on too long, got %v", err)
	}
}

func TestCommentUsecase_Create_PostMissing(t *testing.T) {
	cuc, _, authorID := setupCommentUC(t)
	_, err := cuc.Create(context.Background(), 9999, authorID, "hi")
	if err == nil || kerrors.Reason(err) != "POST_NOT_FOUND" {
		t.Fatalf("expected POST_NOT_FOUND, got %v", err)
	}
}

func TestCommentUsecase_ListByPost(t *testing.T) {
	cuc, puc, authorID := setupCommentUC(t)
	p, _ := puc.Create(context.Background(), authorID, "t", "b", nil)

	for i := 0; i < 3; i++ {
		if _, err := cuc.Create(context.Background(), p.ID, authorID, "c"); err != nil {
			t.Fatal(err)
		}
	}

	items, total, err := cuc.ListByPost(context.Background(), p.ID, 1, 10)
	if err != nil {
		t.Fatal(err)
	}
	if total != 3 || len(items) != 3 {
		t.Fatalf("total=%d items=%d", total, len(items))
	}

	_, _, err = cuc.ListByPost(context.Background(), 9999, 1, 10)
	if err == nil || kerrors.Reason(err) != "POST_NOT_FOUND" {
		t.Fatalf("expected POST_NOT_FOUND, got %v", err)
	}
}
