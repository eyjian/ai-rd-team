package biz

import (
	"context"
	"errors"
	"strings"
	"time"

	v1 "blog/api/blog/v1"

	"github.com/go-kratos/kratos/v2/log"
)

// Comment 为评论 DO。
type Comment struct {
	ID        int64
	PostID    int64
	AuthorID  int64
	Body      string
	CreatedAt time.Time
}

// CommentRepo 由 data 层实现。
type CommentRepo interface {
	Create(ctx context.Context, c *Comment) (*Comment, error)
	ListByPost(ctx context.Context, postID int64) ([]*Comment, error)
}

// CommentUsecase 封装评论相关用例。
type CommentUsecase struct {
	cr  CommentRepo
	pr  PostRepo
	log *log.Helper
}

// NewCommentUsecase 构造 CommentUsecase。
func NewCommentUsecase(cr CommentRepo, pr PostRepo, logger log.Logger) *CommentUsecase {
	return &CommentUsecase{
		cr:  cr,
		pr:  pr,
		log: log.NewHelper(log.With(logger, "module", "biz/comment")),
	}
}

// Create 在某篇文章下发表评论。
func (uc *CommentUsecase) Create(ctx context.Context, postID, authorID int64, body string) (*Comment, error) {
	if authorID <= 0 {
		return nil, v1.ErrorUserUnauthenticated("author required")
	}
	if postID <= 0 {
		return nil, v1.ErrorValidationFailed("post id must be positive")
	}
	body = strings.TrimSpace(body)
	if body == "" {
		return nil, v1.ErrorValidationFailed("body required")
	}

	// 校验文章存在
	if _, err := uc.pr.GetByID(ctx, postID); err != nil {
		if errors.Is(err, ErrPostNotFound) {
			return nil, v1.ErrorPostNotFound("post %d not found", postID)
		}
		return nil, err
	}

	c := &Comment{
		PostID:   postID,
		AuthorID: authorID,
		Body:     body,
	}
	return uc.cr.Create(ctx, c)
}

// ListByPost 查询文章下的评论（按时间升序）。
func (uc *CommentUsecase) ListByPost(ctx context.Context, postID int64) ([]*Comment, error) {
	if postID <= 0 {
		return nil, v1.ErrorValidationFailed("post id must be positive")
	}
	// 校验文章存在
	if _, err := uc.pr.GetByID(ctx, postID); err != nil {
		if errors.Is(err, ErrPostNotFound) {
			return nil, v1.ErrorPostNotFound("post %d not found", postID)
		}
		return nil, err
	}
	return uc.cr.ListByPost(ctx, postID)
}
