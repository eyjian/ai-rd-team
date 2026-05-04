package data

import (
	"context"
	"time"

	"blog/internal/biz"

	"github.com/go-kratos/kratos/v2/log"
)

// commentPO 为 comments 表的 GORM 映射。
type commentPO struct {
	ID        int64     `gorm:"column:id;primaryKey;autoIncrement"`
	PostID    int64     `gorm:"column:post_id;not null;index:idx_comments_post,priority:1"`
	AuthorID  int64     `gorm:"column:author_id;not null"`
	Content   string    `gorm:"column:content;type:text;not null"`
	CreatedAt time.Time `gorm:"column:created_at;autoCreateTime;index:idx_comments_post,sort:desc,priority:2"`
}

func (commentPO) TableName() string { return "comments" }

func (po *commentPO) toBiz() *biz.Comment {
	return &biz.Comment{
		ID:        po.ID,
		PostID:    po.PostID,
		AuthorID:  po.AuthorID,
		Content:   po.Content,
		CreatedAt: po.CreatedAt,
	}
}

type commentRepo struct {
	data *Data
	log  *log.Helper
}

// NewCommentRepo 实现 biz.CommentRepo。
func NewCommentRepo(d *Data, logger log.Logger) biz.CommentRepo {
	return &commentRepo{data: d, log: log.NewHelper(log.With(logger, "module", "data/comment"))}
}

func (r *commentRepo) Create(ctx context.Context, c *biz.Comment) (*biz.Comment, error) {
	po := &commentPO{
		PostID:   c.PostID,
		AuthorID: c.AuthorID,
		Content:  c.Content,
	}
	if err := r.data.DB.WithContext(ctx).Create(po).Error; err != nil {
		return nil, err
	}
	return po.toBiz(), nil
}

func (r *commentRepo) ListByPost(ctx context.Context, postID int64, page, size int32) ([]*biz.Comment, int64, error) {
	if page < 1 {
		page = 1
	}
	if size < 1 {
		size = 20
	}

	q := r.data.DB.WithContext(ctx).Model(&commentPO{}).Where("post_id = ?", postID)

	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	if total == 0 {
		return []*biz.Comment{}, 0, nil
	}

	var pos []commentPO
	offset := int((page - 1) * size)
	if err := q.Order("created_at DESC").Limit(int(size)).Offset(offset).Find(&pos).Error; err != nil {
		return nil, 0, err
	}
	out := make([]*biz.Comment, 0, len(pos))
	for i := range pos {
		out = append(out, pos[i].toBiz())
	}
	return out, total, nil
}
