package biz

import (
	"context"
	"errors"
	"strings"
	"time"

	kerrors "github.com/go-kratos/kratos/v2/errors"
	"github.com/go-kratos/kratos/v2/log"
)

// Comment 评论领域模型。
type Comment struct {
	ID        int64
	PostID    int64
	AuthorID  int64
	Content   string
	CreatedAt time.Time
}

// ErrCommentNotFound data 层内部哨兵值。
var ErrCommentNotFound = errors.New("comment not found")

// CommentRepo 由 data 层实现。
type CommentRepo interface {
	Create(ctx context.Context, c *Comment) (*Comment, error)
	ListByPost(ctx context.Context, postID int64, page, size int32) ([]*Comment, int64, error)
}

// CommentUsecase 评论用例。
type CommentUsecase struct {
	cr  CommentRepo
	pr  PostRepo
	log *log.Helper
}

// NewCommentUsecase 构造函数。
func NewCommentUsecase(cr CommentRepo, pr PostRepo, logger log.Logger) *CommentUsecase {
	return &CommentUsecase{
		cr:  cr,
		pr:  pr,
		log: log.NewHelper(log.With(logger, "module", "biz/comment")),
	}
}

// Create 发表评论：校验内容 + 校验文章存在。
func (uc *CommentUsecase) Create(ctx context.Context, postID, authorID int64, content string) (*Comment, error) {
	content = strings.TrimSpace(content)
	if content == "" || len(content) > 2000 {
		return nil, kerrors.BadRequest("VALIDATION_FAILED", "content length 1..2000")
	}
	if _, err := uc.pr.GetByID(ctx, postID); err != nil {
		if errors.Is(err, ErrPostNotFound) || kerrors.IsNotFound(err) {
			return nil, kerrors.NotFound("POST_NOT_FOUND", "post not found")
		}
		return nil, err
	}
	c := &Comment{
		PostID:   postID,
		AuthorID: authorID,
		Content:  content,
	}
	return uc.cr.Create(ctx, c)
}

// ListByPost 按文章分页列出评论。
func (uc *CommentUsecase) ListByPost(ctx context.Context, postID int64, page, size int32) ([]*Comment, int64, error) {
	if page < 1 {
		page = 1
	}
	if size < 1 {
		size = 20
	}
	if size > 100 {
		size = 100
	}
	// 先确认文章存在，语义更清晰。
	if _, err := uc.pr.GetByID(ctx, postID); err != nil {
		if errors.Is(err, ErrPostNotFound) || kerrors.IsNotFound(err) {
			return nil, 0, kerrors.NotFound("POST_NOT_FOUND", "post not found")
		}
		return nil, 0, err
	}
	return uc.cr.ListByPost(ctx, postID, page, size)
}
