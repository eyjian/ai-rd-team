package data

import (
	"context"
	"errors"

	"blog/internal/biz"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/lib/pq"
	"gorm.io/gorm"
)

type postRepo struct {
	data *Data
	log  *log.Helper
}

// NewPostRepo 构造 PostRepo 实现。
func NewPostRepo(d *Data, logger log.Logger) biz.PostRepo {
	return &postRepo{
		data: d,
		log:  log.NewHelper(log.With(logger, "module", "data/post")),
	}
}

func toPostDO(po *postPO) *biz.Post {
	if po == nil {
		return nil
	}
	return &biz.Post{
		ID:        po.ID,
		AuthorID:  po.AuthorID,
		Title:     po.Title,
		Body:      po.Body,
		Tags:      []string(po.Tags),
		LikeCount: po.LikeCount,
		CreatedAt: po.CreatedAt,
		UpdatedAt: po.UpdatedAt,
	}
}

func (r *postRepo) Create(ctx context.Context, p *biz.Post) (*biz.Post, error) {
	po := &postPO{
		AuthorID: p.AuthorID,
		Title:    p.Title,
		Body:     p.Body,
		Tags:     pq.StringArray(p.Tags),
	}
	if err := r.data.db.WithContext(ctx).Create(po).Error; err != nil {
		return nil, err
	}
	return toPostDO(po), nil
}

func (r *postRepo) GetByID(ctx context.Context, id int64) (*biz.Post, error) {
	var po postPO
	err := r.data.db.WithContext(ctx).First(&po, "id = ?", id).Error
	if err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, biz.ErrPostNotFound
		}
		return nil, err
	}
	return toPostDO(&po), nil
}

func (r *postRepo) Update(ctx context.Context, p *biz.Post) error {
	res := r.data.db.WithContext(ctx).Model(&postPO{}).
		Where("id = ?", p.ID).
		Updates(map[string]any{
			"title": p.Title,
			"body":  p.Body,
			"tags":  pq.StringArray(p.Tags),
		})
	if res.Error != nil {
		return res.Error
	}
	if res.RowsAffected == 0 {
		return biz.ErrPostNotFound
	}
	return nil
}

func (r *postRepo) Delete(ctx context.Context, id int64) error {
	res := r.data.db.WithContext(ctx).Delete(&postPO{}, "id = ?", id)
	if res.Error != nil {
		return res.Error
	}
	if res.RowsAffected == 0 {
		return biz.ErrPostNotFound
	}
	return nil
}

func (r *postRepo) List(ctx context.Context, page, size int32, tag string) ([]*biz.Post, int64, error) {
	if page < 1 {
		page = 1
	}
	if size < 1 {
		size = 10
	}
	q := r.data.db.WithContext(ctx).Model(&postPO{})
	if tag != "" {
		// PostgreSQL text[] 包含查询
		q = q.Where("? = ANY(tags)", tag)
	}

	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, err
	}

	var pos []postPO
	err := q.Order("created_at DESC").
		Offset(int((page - 1) * size)).
		Limit(int(size)).
		Find(&pos).Error
	if err != nil {
		return nil, 0, err
	}

	out := make([]*biz.Post, 0, len(pos))
	for i := range pos {
		out = append(out, toPostDO(&pos[i]))
	}
	return out, total, nil
}
