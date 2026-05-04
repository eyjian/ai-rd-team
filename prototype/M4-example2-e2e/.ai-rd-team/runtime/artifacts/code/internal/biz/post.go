package biz

import (
	"context"
	"errors"
	"time"

	"github.com/go-kratos/kratos/v2/log"
)

// 文章相关的哨兵错误。
var (
	// ErrPostNotFound 文章不存在。对应 POST_NOT_FOUND / 404。
	ErrPostNotFound = errors.New("biz: post not found")
	// ErrPostNotOwned 文章不属于当前用户。对应 POST_NOT_OWNED / 403。
	ErrPostNotOwned = errors.New("biz: post not owned")
)

// Post 文章领域实体。AuthorNickname 为冗余字段，便于列表展示。
type Post struct {
	ID             int64
	AuthorID       int64
	AuthorNickname string
	Title          string
	BodyMarkdown   string
	Tags           []string
	LikesCount     int64
	CreatedAt      time.Time
	UpdatedAt      time.Time
}

// PostRepo 文章仓储接口。
type PostRepo interface {
	// Create 新建文章。
	Create(ctx context.Context, authorID int64, title, body string, tags []string) (*Post, error)
	// GetByID 按 ID 查询。找不到返回 ErrPostNotFound。
	GetByID(ctx context.Context, id int64) (*Post, error)
	// List 分页列表；tag 非空时按 tag 过滤。
	// page<=0 视为 1，size<=0 视为 10，size 上限由 service 层校验（最大 100）。
	List(ctx context.Context, page, size int32, tag string) (items []*Post, total int64, err error)
	// Update 更新文章。若文章不存在返回 ErrPostNotFound；
	// 存在但 author_id 不匹配返回 ErrPostNotOwned。
	Update(ctx context.Context, id, authorID int64, title, body string, tags []string) (*Post, error)
	// Delete 删除文章；错误规则同 Update。
	Delete(ctx context.Context, id, authorID int64) error
}

// PostUsecase 文章用例。
type PostUsecase struct {
	repo PostRepo
	log  *log.Helper
}

// NewPostUsecase 构造函数。
func NewPostUsecase(repo PostRepo, logger log.Logger) *PostUsecase {
	return &PostUsecase{
		repo: repo,
		log:  log.NewHelper(log.With(logger, "module", "biz/post")),
	}
}

// Create 发布文章。tags 为 nil 时规范化为 empty slice。
func (uc *PostUsecase) Create(ctx context.Context, authorID int64, title, body string, tags []string) (*Post, error) {
	if tags == nil {
		tags = []string{}
	}
	p, err := uc.repo.Create(ctx, authorID, title, body, tags)
	if err != nil {
		return nil, err
	}
	uc.log.WithContext(ctx).Infof("post created id=%d author=%d", p.ID, authorID)
	return p, nil
}

// Get 查询单篇文章。
func (uc *PostUsecase) Get(ctx context.Context, id int64) (*Post, error) {
	return uc.repo.GetByID(ctx, id)
}

// List 分页列表；page/size 规范化（<=0 用默认值）在 repo 层完成。
func (uc *PostUsecase) List(ctx context.Context, page, size int32, tag string) ([]*Post, int64, error) {
	return uc.repo.List(ctx, page, size, tag)
}

// Update 更新文章；所有权校验由 data 层在同一 SQL 中完成。
func (uc *PostUsecase) Update(ctx context.Context, id, authorID int64, title, body string, tags []string) (*Post, error) {
	if tags == nil {
		tags = []string{}
	}
	p, err := uc.repo.Update(ctx, id, authorID, title, body, tags)
	if err != nil {
		return nil, err
	}
	uc.log.WithContext(ctx).Infof("post updated id=%d author=%d", p.ID, authorID)
	return p, nil
}

// Delete 删除文章。
func (uc *PostUsecase) Delete(ctx context.Context, id, authorID int64) error {
	if err := uc.repo.Delete(ctx, id, authorID); err != nil {
		return err
	}
	uc.log.WithContext(ctx).Infof("post deleted id=%d author=%d", id, authorID)
	return nil
}
