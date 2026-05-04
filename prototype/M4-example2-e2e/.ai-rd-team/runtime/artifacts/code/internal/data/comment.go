package data

import (
	"context"

	"blog/internal/biz"

	"github.com/go-kratos/kratos/v2/log"
)

type commentRepo struct {
	data *Data
	log  *log.Helper
}

// NewCommentRepo 构造 CommentRepo 实现。
func NewCommentRepo(d *Data, logger log.Logger) biz.CommentRepo {
	return &commentRepo{
		data: d,
		log:  log.NewHelper(log.With(logger, "module", "data/comment")),
	}
}

func toCommentDO(po *commentPO) *biz.Comment {
	if po == nil {
		return nil
	}
	return &biz.Comment{
		ID:        po.ID,
		PostID:    po.PostID,
		AuthorID:  po.AuthorID,
		Body:      po.Body,
		CreatedAt: po.CreatedAt,
	}
}

func (r *commentRepo) Create(ctx context.Context, c *biz.Comment) (*biz.Comment, error) {
	po := &commentPO{
		PostID:   c.PostID,
		AuthorID: c.AuthorID,
		Body:     c.Body,
	}
	if err := r.data.db.WithContext(ctx).Create(po).Error; err != nil {
		return nil, err
	}
	return toCommentDO(po), nil
}

func (r *commentRepo) ListByPost(ctx context.Context, postID int64) ([]*biz.Comment, error) {
	var pos []commentPO
	err := r.data.db.WithContext(ctx).
		Where("post_id = ?", postID).
		Order("created_at ASC").
		Find(&pos).Error
	if err != nil {
		return nil, err
	}
	out := make([]*biz.Comment, 0, len(pos))
	for i := range pos {
		out = append(out, toCommentDO(&pos[i]))
	}
	return out, nil
}
