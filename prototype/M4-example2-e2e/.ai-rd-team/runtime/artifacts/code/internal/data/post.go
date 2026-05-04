package data

import (
	"context"
	"errors"
	"time"

	"blog/internal/biz"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/lib/pq"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// postPO 为 posts 表的 GORM 映射。tags 使用 pq.StringArray 对应 TEXT[]。
type postPO struct {
	ID           int64          `gorm:"column:id;primaryKey;autoIncrement"`
	AuthorID     int64          `gorm:"column:author_id;not null;index:idx_posts_author"`
	Title        string         `gorm:"column:title;size:200;not null"`
	BodyMarkdown string         `gorm:"column:body_markdown;type:text;not null"`
	Tags         pq.StringArray `gorm:"column:tags;type:text[]"`
	LikesCount   int64          `gorm:"column:likes_count;not null;default:0"`
	CreatedAt    time.Time      `gorm:"column:created_at;autoCreateTime"`
	UpdatedAt    time.Time      `gorm:"column:updated_at;autoUpdateTime"`
}

func (postPO) TableName() string { return "posts" }

func (po *postPO) toBiz() *biz.Post {
	tags := make([]string, len(po.Tags))
	copy(tags, po.Tags)
	return &biz.Post{
		ID:           po.ID,
		AuthorID:     po.AuthorID,
		Title:        po.Title,
		BodyMarkdown: po.BodyMarkdown,
		Tags:         tags,
		LikesCount:   po.LikesCount,
		CreatedAt:    po.CreatedAt,
		UpdatedAt:    po.UpdatedAt,
	}
}

// postLikePO 为 post_likes 表的 GORM 映射（复合主键）。
type postLikePO struct {
	PostID    int64     `gorm:"column:post_id;primaryKey"`
	UserID    int64     `gorm:"column:user_id;primaryKey"`
	CreatedAt time.Time `gorm:"column:created_at;autoCreateTime"`
}

func (postLikePO) TableName() string { return "post_likes" }

type postRepo struct {
	data *Data
	log  *log.Helper
}

// NewPostRepo 实现 biz.PostRepo。
func NewPostRepo(d *Data, logger log.Logger) biz.PostRepo {
	return &postRepo{data: d, log: log.NewHelper(log.With(logger, "module", "data/post"))}
}

func (r *postRepo) Create(ctx context.Context, p *biz.Post) (*biz.Post, error) {
	po := &postPO{
		AuthorID:     p.AuthorID,
		Title:        p.Title,
		BodyMarkdown: p.BodyMarkdown,
		Tags:         pq.StringArray(p.Tags),
	}
	if err := r.data.DB.WithContext(ctx).Create(po).Error; err != nil {
		return nil, err
	}
	return po.toBiz(), nil
}

func (r *postRepo) GetByID(ctx context.Context, id int64) (*biz.Post, error) {
	var po postPO
	if err := r.data.DB.WithContext(ctx).Where("id = ?", id).First(&po).Error; err != nil {
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil, biz.ErrPostNotFound
		}
		return nil, err
	}
	return po.toBiz(), nil
}

func (r *postRepo) Update(ctx context.Context, p *biz.Post) (*biz.Post, error) {
	// 只更新业务字段，避免覆盖 likes_count / created_at。
	updates := map[string]interface{}{
		"title":         p.Title,
		"body_markdown": p.BodyMarkdown,
		"tags":          pq.StringArray(p.Tags),
	}
	res := r.data.DB.WithContext(ctx).Model(&postPO{}).Where("id = ?", p.ID).Updates(updates)
	if res.Error != nil {
		return nil, res.Error
	}
	if res.RowsAffected == 0 {
		return nil, biz.ErrPostNotFound
	}
	return r.GetByID(ctx, p.ID)
}

func (r *postRepo) Delete(ctx context.Context, id int64) error {
	res := r.data.DB.WithContext(ctx).Where("id = ?", id).Delete(&postPO{})
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
		size = 20
	}

	q := r.data.DB.WithContext(ctx).Model(&postPO{})
	if tag != "" {
		// 利用 TEXT[] 的 GIN 索引
		q = q.Where("? = ANY(tags)", tag)
	}

	var total int64
	if err := q.Count(&total).Error; err != nil {
		return nil, 0, err
	}
	if total == 0 {
		return []*biz.Post{}, 0, nil
	}

	var pos []postPO
	offset := int((page - 1) * size)
	if err := q.Order("created_at DESC").Limit(int(size)).Offset(offset).Find(&pos).Error; err != nil {
		return nil, 0, err
	}
	out := make([]*biz.Post, 0, len(pos))
	for i := range pos {
		out = append(out, pos[i].toBiz())
	}
	return out, total, nil
}

// AddLike 幂等点赞：ON CONFLICT DO NOTHING + 事务内同步 likes_count。
func (r *postRepo) AddLike(ctx context.Context, postID, userID int64) (bool, error) {
	added := false
	err := r.data.DB.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		res := tx.Clauses(clause.OnConflict{DoNothing: true}).Create(&postLikePO{
			PostID: postID,
			UserID: userID,
		})
		if res.Error != nil {
			return res.Error
		}
		if res.RowsAffected == 0 {
			// 已点过赞，幂等返回
			return nil
		}
		upd := tx.Model(&postPO{}).Where("id = ?", postID).
			UpdateColumn("likes_count", gorm.Expr("likes_count + 1"))
		if upd.Error != nil {
			return upd.Error
		}
		if upd.RowsAffected == 0 {
			return biz.ErrPostNotFound
		}
		added = true
		return nil
	})
	return added, err
}

// RemoveLike 幂等取消点赞。
func (r *postRepo) RemoveLike(ctx context.Context, postID, userID int64) (bool, error) {
	removed := false
	err := r.data.DB.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		res := tx.Where("post_id = ? AND user_id = ?", postID, userID).Delete(&postLikePO{})
		if res.Error != nil {
			return res.Error
		}
		if res.RowsAffected == 0 {
			return nil
		}
		upd := tx.Model(&postPO{}).Where("id = ? AND likes_count > 0", postID).
			UpdateColumn("likes_count", gorm.Expr("likes_count - 1"))
		if upd.Error != nil {
			return upd.Error
		}
		removed = true
		return nil
	})
	return removed, err
}
