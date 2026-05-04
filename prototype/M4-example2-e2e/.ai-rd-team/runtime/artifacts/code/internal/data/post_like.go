package data

import (
	"context"

	"blog/internal/biz"

	"github.com/go-kratos/kratos/v2/log"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type postLikeRepo struct {
	data *Data
	log  *log.Helper
}

// NewPostLikeRepo 构造 PostLikeRepo 实现。
func NewPostLikeRepo(d *Data, logger log.Logger) biz.PostLikeRepo {
	return &postLikeRepo{
		data: d,
		log:  log.NewHelper(log.With(logger, "module", "data/post_like")),
	}
}

// Add 新增点赞（幂等）：
//   - 使用 ON CONFLICT DO NOTHING，若 RowsAffected==1 表示本次新增，事务内 like_count+=1；
//   - 否则 RowsAffected==0，表示已存在，不更新计数，返回 added=false。
func (r *postLikeRepo) Add(ctx context.Context, postID, userID int64) (bool, error) {
	added := false
	err := r.data.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		res := tx.Clauses(clause.OnConflict{DoNothing: true}).
			Create(&postLikePO{PostID: postID, UserID: userID})
		if res.Error != nil {
			return res.Error
		}
		if res.RowsAffected == 0 {
			added = false
			return nil
		}
		added = true
		return tx.Model(&postPO{}).
			Where("id = ?", postID).
			UpdateColumn("like_count", gorm.Expr("like_count + 1")).Error
	})
	if err != nil {
		return false, err
	}
	return added, nil
}

// Remove 取消点赞（幂等）：
//   - DELETE 命中 1 行则 like_count-=1（下限为 0，防御性）；
//   - 否则 removed=false，不更新计数。
func (r *postLikeRepo) Remove(ctx context.Context, postID, userID int64) (bool, error) {
	removed := false
	err := r.data.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
		res := tx.Where("post_id = ? AND user_id = ?", postID, userID).
			Delete(&postLikePO{})
		if res.Error != nil {
			return res.Error
		}
		if res.RowsAffected == 0 {
			removed = false
			return nil
		}
		removed = true
		// 防御性：like_count 减到 0 就不再减
		return tx.Model(&postPO{}).
			Where("id = ? AND like_count > 0", postID).
			UpdateColumn("like_count", gorm.Expr("like_count - 1")).Error
	})
	if err != nil {
		return false, err
	}
	return removed, nil
}
