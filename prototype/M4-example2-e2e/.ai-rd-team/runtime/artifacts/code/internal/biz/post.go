package biz

import (
	"context"
	"errors"
	"strings"
	"time"

	v1 "blog/api/blog/v1"

	"github.com/go-kratos/kratos/v2/log"
)

// Post 为文章 DO。
type Post struct {
	ID        int64
	AuthorID  int64
	Title     string
	Body      string
	Tags      []string
	LikeCount int64
	CreatedAt time.Time
	UpdatedAt time.Time
}

// ErrPostNotFound 是 data 层在文章不存在时应返回的哨兵错误。
var ErrPostNotFound = errors.New("biz: post not found")

// PostRepo 由 data 层实现。
type PostRepo interface {
	Create(ctx context.Context, p *Post) (*Post, error)
	GetByID(ctx context.Context, id int64) (*Post, error)
	Update(ctx context.Context, p *Post) error
	Delete(ctx context.Context, id int64) error
	List(ctx context.Context, page, size int32, tag string) ([]*Post, int64, error)
}

// PostLikeRepo 封装点赞表操作，保证幂等。
type PostLikeRepo interface {
	// Add 新增点赞；返回 added=true 表示本次真正新增，false 表示已存在（幂等）。
	// 当 added=true 时，实现需在同一事务中 posts.like_count+=1。
	Add(ctx context.Context, postID, userID int64) (added bool, err error)
	// Remove 取消点赞；返回 removed=true 表示本次真正删除，false 表示本来就没有（幂等）。
	// 当 removed=true 时，实现需在同一事务中 posts.like_count-=1。
	Remove(ctx context.Context, postID, userID int64) (removed bool, err error)
}

// PostUsecase 封装文章相关用例。
type PostUsecase struct {
	pr  PostRepo
	lr  PostLikeRepo
	log *log.Helper
}

// NewPostUsecase 构造 PostUsecase。
func NewPostUsecase(pr PostRepo, lr PostLikeRepo, logger log.Logger) *PostUsecase {
	return &PostUsecase{
		pr:  pr,
		lr:  lr,
		log: log.NewHelper(log.With(logger, "module", "biz/post")),
	}
}

// Create 新建文章。
func (uc *PostUsecase) Create(ctx context.Context, authorID int64, title, body string, tags []string) (*Post, error) {
	if authorID <= 0 {
		return nil, v1.ErrorUserUnauthenticated("author required")
	}
	title = strings.TrimSpace(title)
	if title == "" {
		return nil, v1.ErrorValidationFailed("title required")
	}
	if len(title) > 256 {
		return nil, v1.ErrorValidationFailed("title too long (<=256)")
	}
	tags = normalizeTags(tags)

	p := &Post{
		AuthorID: authorID,
		Title:    title,
		Body:     body,
		Tags:     tags,
	}
	return uc.pr.Create(ctx, p)
}

// Get 查询单篇文章。
func (uc *PostUsecase) Get(ctx context.Context, id int64) (*Post, error) {
	if id <= 0 {
		return nil, v1.ErrorValidationFailed("id must be positive")
	}
	p, err := uc.pr.GetByID(ctx, id)
	if err != nil {
		if errors.Is(err, ErrPostNotFound) {
			return nil, v1.ErrorPostNotFound("post %d not found", id)
		}
		return nil, err
	}
	if p == nil {
		return nil, v1.ErrorPostNotFound("post %d not found", id)
	}
	return p, nil
}

// List 分页查询文章（可选按 tag 过滤）。
func (uc *PostUsecase) List(ctx context.Context, page, size int32, tag string) ([]*Post, int64, error) {
	if page < 1 {
		page = 1
	}
	if size < 1 {
		size = 10
	}
	if size > 50 {
		size = 50
	}
	tag = strings.TrimSpace(tag)
	return uc.pr.List(ctx, page, size, tag)
}

// Update 更新文章；仅作者可更新。
func (uc *PostUsecase) Update(ctx context.Context, authorID, id int64, title, body string, tags []string) (*Post, error) {
	if authorID <= 0 {
		return nil, v1.ErrorUserUnauthenticated("author required")
	}
	if id <= 0 {
		return nil, v1.ErrorValidationFailed("id must be positive")
	}
	title = strings.TrimSpace(title)
	if title == "" {
		return nil, v1.ErrorValidationFailed("title required")
	}

	existing, err := uc.pr.GetByID(ctx, id)
	if err != nil {
		if errors.Is(err, ErrPostNotFound) {
			return nil, v1.ErrorPostNotFound("post %d not found", id)
		}
		return nil, err
	}
	if existing == nil {
		return nil, v1.ErrorPostNotFound("post %d not found", id)
	}
	if existing.AuthorID != authorID {
		return nil, v1.ErrorPostForbidden("only author can update post %d", id)
	}

	existing.Title = title
	existing.Body = body
	existing.Tags = normalizeTags(tags)
	if err := uc.pr.Update(ctx, existing); err != nil {
		return nil, err
	}
	return existing, nil
}

// Delete 删除文章；仅作者可删除。
func (uc *PostUsecase) Delete(ctx context.Context, authorID, id int64) error {
	if authorID <= 0 {
		return v1.ErrorUserUnauthenticated("author required")
	}
	if id <= 0 {
		return v1.ErrorValidationFailed("id must be positive")
	}
	existing, err := uc.pr.GetByID(ctx, id)
	if err != nil {
		if errors.Is(err, ErrPostNotFound) {
			return v1.ErrorPostNotFound("post %d not found", id)
		}
		return err
	}
	if existing == nil {
		return v1.ErrorPostNotFound("post %d not found", id)
	}
	if existing.AuthorID != authorID {
		return v1.ErrorPostForbidden("only author can delete post %d", id)
	}
	return uc.pr.Delete(ctx, id)
}

// Like 点赞（幂等）。
func (uc *PostUsecase) Like(ctx context.Context, postID, userID int64) error {
	if userID <= 0 {
		return v1.ErrorUserUnauthenticated("user required")
	}
	if postID <= 0 {
		return v1.ErrorValidationFailed("post id must be positive")
	}
	// 先确认文章存在（便于返回 404）
	if _, err := uc.pr.GetByID(ctx, postID); err != nil {
		if errors.Is(err, ErrPostNotFound) {
			return v1.ErrorPostNotFound("post %d not found", postID)
		}
		return err
	}
	_, err := uc.lr.Add(ctx, postID, userID)
	return err
}

// Unlike 取消点赞（幂等）。
func (uc *PostUsecase) Unlike(ctx context.Context, postID, userID int64) error {
	if userID <= 0 {
		return v1.ErrorUserUnauthenticated("user required")
	}
	if postID <= 0 {
		return v1.ErrorValidationFailed("post id must be positive")
	}
	if _, err := uc.pr.GetByID(ctx, postID); err != nil {
		if errors.Is(err, ErrPostNotFound) {
			return v1.ErrorPostNotFound("post %d not found", postID)
		}
		return err
	}
	_, err := uc.lr.Remove(ctx, postID, userID)
	return err
}

// normalizeTags trim 每个 tag 并过滤空值，保持输入顺序，去重。
func normalizeTags(in []string) []string {
	if len(in) == 0 {
		return []string{}
	}
	out := make([]string, 0, len(in))
	seen := make(map[string]struct{}, len(in))
	for _, t := range in {
		t = strings.TrimSpace(t)
		if t == "" {
			continue
		}
		if _, ok := seen[t]; ok {
			continue
		}
		seen[t] = struct{}{}
		out = append(out, t)
	}
	return out
}
