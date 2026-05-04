package biz

import (
	"context"
	"errors"
	"strings"
	"time"

	kerrors "github.com/go-kratos/kratos/v2/errors"
	"github.com/go-kratos/kratos/v2/log"
)

// Post 为文章聚合根的领域模型。
type Post struct {
	ID           int64
	AuthorID     int64
	Title        string
	BodyMarkdown string
	Tags         []string
	LikesCount   int64
	CreatedAt    time.Time
	UpdatedAt    time.Time
}

// ErrPostNotFound 作为 data 层向 biz 层传递 "文章未找到" 的内部哨兵值。
var ErrPostNotFound = errors.New("post not found")

// PostRepo 由 data 层实现。
//
// AddLike / RemoveLike 需保证幂等：
//   - AddLike 已点赞返回 added=false 且不报错，新增则 added=true 且在同事务内 +1；
//   - RemoveLike 同理。
type PostRepo interface {
	Create(ctx context.Context, p *Post) (*Post, error)
	GetByID(ctx context.Context, id int64) (*Post, error)
	Update(ctx context.Context, p *Post) (*Post, error)
	Delete(ctx context.Context, id int64) error
	List(ctx context.Context, page, size int32, tag string) ([]*Post, int64, error)
	AddLike(ctx context.Context, postID, userID int64) (added bool, err error)
	RemoveLike(ctx context.Context, postID, userID int64) (removed bool, err error)
}

// PostUsecase 文章用例。
type PostUsecase struct {
	pr  PostRepo
	ur  UserRepo
	log *log.Helper
}

// NewPostUsecase 构造函数。
func NewPostUsecase(pr PostRepo, ur UserRepo, logger log.Logger) *PostUsecase {
	return &PostUsecase{
		pr:  pr,
		ur:  ur,
		log: log.NewHelper(log.With(logger, "module", "biz/post")),
	}
}

func validatePostInput(title, body string) error {
	title = strings.TrimSpace(title)
	if title == "" || len(title) > 200 {
		return kerrors.BadRequest("VALIDATION_FAILED", "title length 1..200")
	}
	if strings.TrimSpace(body) == "" {
		return kerrors.BadRequest("VALIDATION_FAILED", "body_markdown required")
	}
	return nil
}

// normalizeTags 去重 + 去空 + 小写，保证在 tags 数组列中的稳定性。
func normalizeTags(tags []string) []string {
	seen := make(map[string]struct{}, len(tags))
	out := make([]string, 0, len(tags))
	for _, t := range tags {
		t = strings.ToLower(strings.TrimSpace(t))
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

// Create 新建文章。
func (uc *PostUsecase) Create(ctx context.Context, authorID int64, title, body string, tags []string) (*Post, error) {
	if err := validatePostInput(title, body); err != nil {
		return nil, err
	}
	// 校验作者存在，失败时返回 USER_NOT_FOUND
	if _, err := uc.ur.GetByID(ctx, authorID); err != nil {
		if errors.Is(err, ErrUserNotFound) || kerrors.IsNotFound(err) {
			return nil, kerrors.NotFound("USER_NOT_FOUND", "author not found")
		}
		return nil, err
	}
	p := &Post{
		AuthorID:     authorID,
		Title:        strings.TrimSpace(title),
		BodyMarkdown: body,
		Tags:         normalizeTags(tags),
	}
	return uc.pr.Create(ctx, p)
}

// Get 获取文章详情。
func (uc *PostUsecase) Get(ctx context.Context, id int64) (*Post, error) {
	p, err := uc.pr.GetByID(ctx, id)
	if err != nil {
		if errors.Is(err, ErrPostNotFound) || kerrors.IsNotFound(err) {
			return nil, kerrors.NotFound("POST_NOT_FOUND", "post not found")
		}
		return nil, err
	}
	return p, nil
}

// Update 更新文章，仅作者本人可以操作。
func (uc *PostUsecase) Update(ctx context.Context, operatorID, postID int64, title, body string, tags []string) (*Post, error) {
	if err := validatePostInput(title, body); err != nil {
		return nil, err
	}
	existing, err := uc.pr.GetByID(ctx, postID)
	if err != nil {
		if errors.Is(err, ErrPostNotFound) || kerrors.IsNotFound(err) {
			return nil, kerrors.NotFound("POST_NOT_FOUND", "post not found")
		}
		return nil, err
	}
	if existing.AuthorID != operatorID {
		return nil, kerrors.Forbidden("FORBIDDEN", "only author can update")
	}
	existing.Title = strings.TrimSpace(title)
	existing.BodyMarkdown = body
	existing.Tags = normalizeTags(tags)
	return uc.pr.Update(ctx, existing)
}

// Delete 删除文章，仅作者本人可以操作。
func (uc *PostUsecase) Delete(ctx context.Context, operatorID, postID int64) error {
	existing, err := uc.pr.GetByID(ctx, postID)
	if err != nil {
		if errors.Is(err, ErrPostNotFound) || kerrors.IsNotFound(err) {
			return kerrors.NotFound("POST_NOT_FOUND", "post not found")
		}
		return err
	}
	if existing.AuthorID != operatorID {
		return kerrors.Forbidden("FORBIDDEN", "only author can delete")
	}
	return uc.pr.Delete(ctx, postID)
}

// List 分页列出文章，可选 tag 过滤。
func (uc *PostUsecase) List(ctx context.Context, page, size int32, tag string) ([]*Post, int64, error) {
	if page < 1 {
		page = 1
	}
	if size < 1 {
		size = 20
	}
	if size > 100 {
		size = 100
	}
	tag = strings.ToLower(strings.TrimSpace(tag))
	return uc.pr.List(ctx, page, size, tag)
}

// Like 点赞文章，幂等：已点赞再调用不报错。
func (uc *PostUsecase) Like(ctx context.Context, postID, userID int64) error {
	// 先确认文章存在，避免 repo 层把 "post 不存在" 吞成 "已点过赞"。
	if _, err := uc.pr.GetByID(ctx, postID); err != nil {
		if errors.Is(err, ErrPostNotFound) || kerrors.IsNotFound(err) {
			return kerrors.NotFound("POST_NOT_FOUND", "post not found")
		}
		return err
	}
	_, err := uc.pr.AddLike(ctx, postID, userID)
	return err
}

// Unlike 取消点赞，幂等。
func (uc *PostUsecase) Unlike(ctx context.Context, postID, userID int64) error {
	if _, err := uc.pr.GetByID(ctx, postID); err != nil {
		if errors.Is(err, ErrPostNotFound) || kerrors.IsNotFound(err) {
			return kerrors.NotFound("POST_NOT_FOUND", "post not found")
		}
		return err
	}
	_, err := uc.pr.RemoveLike(ctx, postID, userID)
	return err
}
