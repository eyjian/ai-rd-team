package biz

import (
	"context"
	"time"

	"github.com/go-kratos/kratos/v2/log"
)

// Comment 评论领域实体。AuthorNickname 冗余便于展示。
type Comment struct {
	ID             int64
	PostID         int64
	AuthorID       int64
	AuthorNickname string
	Content        string
	CreatedAt      time.Time
}

// CommentRepo 评论 + 点赞仓储接口。
type CommentRepo interface {
	// Create 新增评论。
	Create(ctx context.Context, postID, authorID int64, content string) (*Comment, error)
	// List 分页查询评论（按 created_at 倒序）。
	// page<=0 视为 1，size<=0 视为 20。
	List(ctx context.Context, postID int64, page, size int32) (items []*Comment, total int64, err error)

	// Like 幂等点赞：插入 post_likes，若实际新增一行则 likes_count+1。
	// 返回操作完成后的 likes_count 以及当前用户的 liked 状态（始终 true）。
	Like(ctx context.Context, postID, userID int64) (likesCount int64, liked bool, err error)
	// Unlike 幂等取消点赞：删除 post_likes，若确实删了一行则 likes_count-1。
	// 返回操作完成后的 likes_count 以及当前用户的 liked 状态（始终 false）。
	Unlike(ctx context.Context, postID, userID int64) (likesCount int64, liked bool, err error)
}

// CommentUsecase 评论用例。依赖 CommentRepo 操作评论/点赞；
// 依赖 PostRepo 用于校验目标文章是否存在。
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

// Create 发表评论。先校验文章存在（不存在返回 ErrPostNotFound）。
func (uc *CommentUsecase) Create(ctx context.Context, postID, authorID int64, content string) (*Comment, error) {
	if _, err := uc.pr.GetByID(ctx, postID); err != nil {
		return nil, err
	}
	c, err := uc.cr.Create(ctx, postID, authorID, content)
	if err != nil {
		return nil, err
	}
	uc.log.WithContext(ctx).Infof("comment created id=%d post=%d author=%d", c.ID, postID, authorID)
	return c, nil
}

// List 评论分页列表。文章不存在返回 ErrPostNotFound。
func (uc *CommentUsecase) List(ctx context.Context, postID int64, page, size int32) ([]*Comment, int64, error) {
	if _, err := uc.pr.GetByID(ctx, postID); err != nil {
		return nil, 0, err
	}
	return uc.cr.List(ctx, postID, page, size)
}

// Like 点赞（幂等）。文章不存在返回 ErrPostNotFound。
func (uc *CommentUsecase) Like(ctx context.Context, postID, userID int64) (int64, bool, error) {
	if _, err := uc.pr.GetByID(ctx, postID); err != nil {
		return 0, false, err
	}
	return uc.cr.Like(ctx, postID, userID)
}

// Unlike 取消点赞（幂等）。文章不存在返回 ErrPostNotFound。
func (uc *CommentUsecase) Unlike(ctx context.Context, postID, userID int64) (int64, bool, error) {
	if _, err := uc.pr.GetByID(ctx, postID); err != nil {
		return 0, false, err
	}
	return uc.cr.Unlike(ctx, postID, userID)
}
