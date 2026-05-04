package biz

import (
	"context"
	"errors"
	"sync"
	"time"

	"github.com/go-kratos/kratos/v2/log"
)

// ---------------------------------------------------------------------------
// Shared test doubles for biz package unit tests.
//
// 不依赖任何 mocking 框架：在内存里手写 stub，便于 tester 复用。
// 每个 stub 都实现对应 biz.Repo 接口。
// ---------------------------------------------------------------------------

// fakeUserRepo 用 map 模拟用户存储，生成自增 ID。
type fakeUserRepo struct {
	mu       sync.Mutex
	nextID   int64
	byID     map[int64]*User
	byEmail  map[string]*User
	failNext error // 下一次调用时返回该错误（用于错误路径测试）
}

func newFakeUserRepo() *fakeUserRepo {
	return &fakeUserRepo{
		nextID:  0,
		byID:    make(map[int64]*User),
		byEmail: make(map[string]*User),
	}
}

func (f *fakeUserRepo) Create(_ context.Context, u *User) (*User, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.failNext != nil {
		err := f.failNext
		f.failNext = nil
		return nil, err
	}
	if _, ok := f.byEmail[u.Email]; ok {
		return nil, errors.New("unique violation")
	}
	f.nextID++
	copy := *u
	copy.ID = f.nextID
	copy.CreatedAt = time.Now()
	copy.UpdatedAt = copy.CreatedAt
	f.byID[copy.ID] = &copy
	f.byEmail[copy.Email] = &copy
	return &copy, nil
}

func (f *fakeUserRepo) GetByID(_ context.Context, id int64) (*User, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	u, ok := f.byID[id]
	if !ok {
		return nil, ErrUserNotFound
	}
	copy := *u
	return &copy, nil
}

func (f *fakeUserRepo) GetByEmail(_ context.Context, email string) (*User, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	u, ok := f.byEmail[email]
	if !ok {
		return nil, ErrUserNotFound
	}
	copy := *u
	return &copy, nil
}

// stubTokenIssuer 固定返回配置好的 token / err，便于断言。
type stubTokenIssuer struct {
	token string
	err   error
}

func (s *stubTokenIssuer) Sign(userID int64) (string, error) {
	if s.err != nil {
		return "", s.err
	}
	return s.token, nil
}

// fakePostRepo 内存版文章仓库，支持点赞幂等语义。
type fakePostRepo struct {
	mu     sync.Mutex
	nextID int64
	byID   map[int64]*Post
	likes  map[int64]map[int64]struct{} // postID -> set(userID)
}

func newFakePostRepo() *fakePostRepo {
	return &fakePostRepo{
		byID:  make(map[int64]*Post),
		likes: make(map[int64]map[int64]struct{}),
	}
}

func (f *fakePostRepo) Create(_ context.Context, p *Post) (*Post, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.nextID++
	c := *p
	c.ID = f.nextID
	c.CreatedAt = time.Now()
	c.UpdatedAt = c.CreatedAt
	if c.Tags == nil {
		c.Tags = []string{}
	}
	f.byID[c.ID] = &c
	f.likes[c.ID] = make(map[int64]struct{})
	return &c, nil
}

func (f *fakePostRepo) GetByID(_ context.Context, id int64) (*Post, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	p, ok := f.byID[id]
	if !ok {
		return nil, ErrPostNotFound
	}
	c := *p
	return &c, nil
}

func (f *fakePostRepo) Update(_ context.Context, p *Post) (*Post, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	existing, ok := f.byID[p.ID]
	if !ok {
		return nil, ErrPostNotFound
	}
	existing.Title = p.Title
	existing.BodyMarkdown = p.BodyMarkdown
	existing.Tags = append([]string(nil), p.Tags...)
	existing.UpdatedAt = time.Now()
	c := *existing
	return &c, nil
}

func (f *fakePostRepo) Delete(_ context.Context, id int64) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if _, ok := f.byID[id]; !ok {
		return ErrPostNotFound
	}
	delete(f.byID, id)
	delete(f.likes, id)
	return nil
}

func (f *fakePostRepo) List(_ context.Context, page, size int32, tag string) ([]*Post, int64, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	matched := make([]*Post, 0, len(f.byID))
	for _, p := range f.byID {
		if tag != "" {
			hit := false
			for _, t := range p.Tags {
				if t == tag {
					hit = true
					break
				}
			}
			if !hit {
				continue
			}
		}
		c := *p
		matched = append(matched, &c)
	}
	total := int64(len(matched))
	// 简单分页
	start := int((page - 1) * size)
	if start > len(matched) {
		return []*Post{}, total, nil
	}
	end := start + int(size)
	if end > len(matched) {
		end = len(matched)
	}
	return matched[start:end], total, nil
}

func (f *fakePostRepo) AddLike(_ context.Context, postID, userID int64) (bool, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	set, ok := f.likes[postID]
	if !ok {
		return false, ErrPostNotFound
	}
	if _, exists := set[userID]; exists {
		return false, nil
	}
	set[userID] = struct{}{}
	f.byID[postID].LikesCount++
	return true, nil
}

func (f *fakePostRepo) RemoveLike(_ context.Context, postID, userID int64) (bool, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	set, ok := f.likes[postID]
	if !ok {
		return false, ErrPostNotFound
	}
	if _, exists := set[userID]; !exists {
		return false, nil
	}
	delete(set, userID)
	f.byID[postID].LikesCount--
	return true, nil
}

// fakeCommentRepo 内存版评论仓库。
type fakeCommentRepo struct {
	mu     sync.Mutex
	nextID int64
	items  []*Comment
}

func newFakeCommentRepo() *fakeCommentRepo {
	return &fakeCommentRepo{items: make([]*Comment, 0)}
}

func (f *fakeCommentRepo) Create(_ context.Context, c *Comment) (*Comment, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.nextID++
	cp := *c
	cp.ID = f.nextID
	cp.CreatedAt = time.Now()
	f.items = append(f.items, &cp)
	ret := cp
	return &ret, nil
}

func (f *fakeCommentRepo) ListByPost(_ context.Context, postID int64, page, size int32) ([]*Comment, int64, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	matched := make([]*Comment, 0)
	for _, it := range f.items {
		if it.PostID == postID {
			c := *it
			matched = append(matched, &c)
		}
	}
	total := int64(len(matched))
	start := int((page - 1) * size)
	if start > len(matched) {
		return []*Comment{}, total, nil
	}
	end := start + int(size)
	if end > len(matched) {
		end = len(matched)
	}
	return matched[start:end], total, nil
}

// testLogger 返回一个静默 logger。
func testLogger() log.Logger { return log.NewStdLogger(nopWriter{}) }

type nopWriter struct{}

func (nopWriter) Write(p []byte) (int, error) { return len(p), nil }
