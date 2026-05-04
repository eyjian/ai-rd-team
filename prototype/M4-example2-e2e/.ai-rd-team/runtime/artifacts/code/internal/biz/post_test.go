package biz

import (
	"context"
	"testing"

	kerrors "github.com/go-kratos/kratos/v2/errors"
)

func setupPostUC(t *testing.T) (*PostUsecase, *fakeUserRepo, *fakePostRepo, int64) {
	t.Helper()
	ur := newFakeUserRepo()
	pr := newFakePostRepo()
	uc := NewPostUsecase(pr, ur, testLogger())

	userUC := NewUserUsecase(ur, &stubTokenIssuer{}, testLogger())
	u, err := userUC.Register(context.Background(), "author@b.com", "secret1", "author")
	if err != nil {
		t.Fatal(err)
	}
	return uc, ur, pr, u.ID
}

func TestPostUsecase_Create_Success(t *testing.T) {
	uc, _, _, authorID := setupPostUC(t)
	p, err := uc.Create(context.Background(), authorID, " Hello ", "body", []string{"Go", " go ", "", "web"})
	if err != nil {
		t.Fatal(err)
	}
	if p.Title != "Hello" {
		t.Fatalf("title not trimmed, got %q", p.Title)
	}
	if len(p.Tags) != 2 || p.Tags[0] != "go" || p.Tags[1] != "web" {
		t.Fatalf("tags not normalized: %v", p.Tags)
	}
}

func TestPostUsecase_Create_Validation(t *testing.T) {
	uc, _, _, authorID := setupPostUC(t)
	_, err := uc.Create(context.Background(), authorID, "", "body", nil)
	if err == nil || kerrors.Reason(err) != "VALIDATION_FAILED" {
		t.Fatalf("expected VALIDATION_FAILED for empty title, got %v", err)
	}
	_, err = uc.Create(context.Background(), authorID, "t", "", nil)
	if err == nil || kerrors.Reason(err) != "VALIDATION_FAILED" {
		t.Fatalf("expected VALIDATION_FAILED for empty body, got %v", err)
	}
}

func TestPostUsecase_Create_AuthorMissing(t *testing.T) {
	uc, _, _, _ := setupPostUC(t)
	_, err := uc.Create(context.Background(), 9999, "t", "b", nil)
	if err == nil || kerrors.Reason(err) != "USER_NOT_FOUND" {
		t.Fatalf("expected USER_NOT_FOUND, got %v", err)
	}
}

func TestPostUsecase_Get_NotFound(t *testing.T) {
	uc, _, _, _ := setupPostUC(t)
	_, err := uc.Get(context.Background(), 9999)
	if err == nil || kerrors.Reason(err) != "POST_NOT_FOUND" {
		t.Fatalf("expected POST_NOT_FOUND, got %v", err)
	}
}

func TestPostUsecase_Update_ForbiddenForNonAuthor(t *testing.T) {
	uc, ur, _, authorID := setupPostUC(t)
	p, err := uc.Create(context.Background(), authorID, "t", "b", nil)
	if err != nil {
		t.Fatal(err)
	}
	// 造一个另一个用户
	other, err := ur.Create(context.Background(), &User{Email: "other@b.com", PasswordHash: "x", Nickname: "o"})
	if err != nil {
		t.Fatal(err)
	}

	_, err = uc.Update(context.Background(), other.ID, p.ID, "t2", "b2", []string{"t"})
	if err == nil || kerrors.Reason(err) != "FORBIDDEN" {
		t.Fatalf("expected FORBIDDEN, got %v", err)
	}
}

func TestPostUsecase_Update_SuccessByAuthor(t *testing.T) {
	uc, _, _, authorID := setupPostUC(t)
	p, err := uc.Create(context.Background(), authorID, "t", "b", nil)
	if err != nil {
		t.Fatal(err)
	}
	updated, err := uc.Update(context.Background(), authorID, p.ID, "t2", "b2", []string{"Go"})
	if err != nil {
		t.Fatal(err)
	}
	if updated.Title != "t2" || updated.BodyMarkdown != "b2" || len(updated.Tags) != 1 || updated.Tags[0] != "go" {
		t.Fatalf("update mismatch: %+v", updated)
	}
}

func TestPostUsecase_Delete_NonAuthor(t *testing.T) {
	uc, ur, _, authorID := setupPostUC(t)
	p, err := uc.Create(context.Background(), authorID, "t", "b", nil)
	if err != nil {
		t.Fatal(err)
	}
	other, _ := ur.Create(context.Background(), &User{Email: "x@x.com", PasswordHash: "x", Nickname: "x"})
	if err := uc.Delete(context.Background(), other.ID, p.ID); err == nil || kerrors.Reason(err) != "FORBIDDEN" {
		t.Fatalf("expected FORBIDDEN, got %v", err)
	}
}

func TestPostUsecase_Delete_Success(t *testing.T) {
	uc, _, _, authorID := setupPostUC(t)
	p, err := uc.Create(context.Background(), authorID, "t", "b", nil)
	if err != nil {
		t.Fatal(err)
	}
	if err := uc.Delete(context.Background(), authorID, p.ID); err != nil {
		t.Fatal(err)
	}
	if _, err := uc.Get(context.Background(), p.ID); err == nil || kerrors.Reason(err) != "POST_NOT_FOUND" {
		t.Fatalf("expected POST_NOT_FOUND after delete, got %v", err)
	}
}

func TestPostUsecase_List_Paging(t *testing.T) {
	uc, _, _, authorID := setupPostUC(t)
	for i := 0; i < 3; i++ {
		if _, err := uc.Create(context.Background(), authorID, "t", "b", []string{"go"}); err != nil {
			t.Fatal(err)
		}
	}
	items, total, err := uc.List(context.Background(), 1, 2, "go")
	if err != nil {
		t.Fatal(err)
	}
	if total != 3 {
		t.Fatalf("total=%d", total)
	}
	if len(items) != 2 {
		t.Fatalf("page size=%d", len(items))
	}
}

func TestPostUsecase_Like_Idempotent(t *testing.T) {
	uc, _, _, authorID := setupPostUC(t)
	p, err := uc.Create(context.Background(), authorID, "t", "b", nil)
	if err != nil {
		t.Fatal(err)
	}

	if err := uc.Like(context.Background(), p.ID, 42); err != nil {
		t.Fatal(err)
	}
	// 再点一次不应报错
	if err := uc.Like(context.Background(), p.ID, 42); err != nil {
		t.Fatal(err)
	}
	got, _ := uc.Get(context.Background(), p.ID)
	if got.LikesCount != 1 {
		t.Fatalf("likes_count=%d, want 1 (idempotent)", got.LikesCount)
	}

	// unlike 幂等
	if err := uc.Unlike(context.Background(), p.ID, 42); err != nil {
		t.Fatal(err)
	}
	if err := uc.Unlike(context.Background(), p.ID, 42); err != nil {
		t.Fatal(err)
	}
	got, _ = uc.Get(context.Background(), p.ID)
	if got.LikesCount != 0 {
		t.Fatalf("likes_count=%d, want 0", got.LikesCount)
	}
}

func TestPostUsecase_Like_PostMissing(t *testing.T) {
	uc, _, _, _ := setupPostUC(t)
	if err := uc.Like(context.Background(), 9999, 1); err == nil || kerrors.Reason(err) != "POST_NOT_FOUND" {
		t.Fatalf("expected POST_NOT_FOUND, got %v", err)
	}
	if err := uc.Unlike(context.Background(), 9999, 1); err == nil || kerrors.Reason(err) != "POST_NOT_FOUND" {
		t.Fatalf("expected POST_NOT_FOUND, got %v", err)
	}
}
