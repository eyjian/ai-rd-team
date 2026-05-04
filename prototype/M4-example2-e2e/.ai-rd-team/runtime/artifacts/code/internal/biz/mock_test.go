package biz

import (
	"context"
	"errors"
)

// =============== Mock UserRepo ===============

type mockUserRepo struct {
	createFn     func(ctx context.Context, u *User) (*User, error)
	getByIDFn    func(ctx context.Context, id int64) (*User, error)
	getByEmailFn func(ctx context.Context, email string) (*User, error)
}

func (m *mockUserRepo) Create(ctx context.Context, u *User) (*User, error) {
	if m.createFn != nil {
		return m.createFn(ctx, u)
	}
	return nil, errors.New("mock: Create not set")
}
func (m *mockUserRepo) GetByID(ctx context.Context, id int64) (*User, error) {
	if m.getByIDFn != nil {
		return m.getByIDFn(ctx, id)
	}
	return nil, ErrUserNotFound
}
func (m *mockUserRepo) GetByEmail(ctx context.Context, email string) (*User, error) {
	if m.getByEmailFn != nil {
		return m.getByEmailFn(ctx, email)
	}
	return nil, ErrUserNotFound
}

// =============== Mock PostRepo ===============

type mockPostRepo struct {
	createFn  func(ctx context.Context, p *Post) (*Post, error)
	getByIDFn func(ctx context.Context, id int64) (*Post, error)
	updateFn  func(ctx context.Context, p *Post) error
	deleteFn  func(ctx context.Context, id int64) error
	listFn    func(ctx context.Context, page, size int32, tag string) ([]*Post, int64, error)
}

func (m *mockPostRepo) Create(ctx context.Context, p *Post) (*Post, error) {
	if m.createFn != nil {
		return m.createFn(ctx, p)
	}
	return nil, errors.New("mock: Create not set")
}
func (m *mockPostRepo) GetByID(ctx context.Context, id int64) (*Post, error) {
	if m.getByIDFn != nil {
		return m.getByIDFn(ctx, id)
	}
	return nil, ErrPostNotFound
}
func (m *mockPostRepo) Update(ctx context.Context, p *Post) error {
	if m.updateFn != nil {
		return m.updateFn(ctx, p)
	}
	return nil
}
func (m *mockPostRepo) Delete(ctx context.Context, id int64) error {
	if m.deleteFn != nil {
		return m.deleteFn(ctx, id)
	}
	return nil
}
func (m *mockPostRepo) List(ctx context.Context, page, size int32, tag string) ([]*Post, int64, error) {
	if m.listFn != nil {
		return m.listFn(ctx, page, size, tag)
	}
	return nil, 0, nil
}

// =============== Mock PostLikeRepo ===============

type mockPostLikeRepo struct {
	likes    map[[2]int64]struct{} // (post_id, user_id) -> {}
	addErr   error
	removeFn func(ctx context.Context, postID, userID int64) (bool, error)
}

func newMockPostLikeRepo() *mockPostLikeRepo {
	return &mockPostLikeRepo{likes: map[[2]int64]struct{}{}}
}

func (m *mockPostLikeRepo) Add(ctx context.Context, postID, userID int64) (bool, error) {
	if m.addErr != nil {
		return false, m.addErr
	}
	k := [2]int64{postID, userID}
	if _, ok := m.likes[k]; ok {
		return false, nil
	}
	m.likes[k] = struct{}{}
	return true, nil
}
func (m *mockPostLikeRepo) Remove(ctx context.Context, postID, userID int64) (bool, error) {
	if m.removeFn != nil {
		return m.removeFn(ctx, postID, userID)
	}
	k := [2]int64{postID, userID}
	if _, ok := m.likes[k]; !ok {
		return false, nil
	}
	delete(m.likes, k)
	return true, nil
}

// =============== Mock CommentRepo ===============

type mockCommentRepo struct {
	createFn     func(ctx context.Context, c *Comment) (*Comment, error)
	listByPostFn func(ctx context.Context, postID int64) ([]*Comment, error)
}

func (m *mockCommentRepo) Create(ctx context.Context, c *Comment) (*Comment, error) {
	if m.createFn != nil {
		return m.createFn(ctx, c)
	}
	return c, nil
}
func (m *mockCommentRepo) ListByPost(ctx context.Context, postID int64) ([]*Comment, error) {
	if m.listByPostFn != nil {
		return m.listByPostFn(ctx, postID)
	}
	return nil, nil
}
