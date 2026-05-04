package service

import (
	"context"

	v1 "blog/api/blog/v1"
	"blog/internal/biz"
	"blog/internal/pkg/auth"

	"google.golang.org/protobuf/types/known/emptypb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// PostService adapts v1.PostServiceServer to biz.PostUsecase.
type PostService struct {
	v1.UnimplementedPostServiceServer
	uc *biz.PostUsecase
}

// NewPostService constructor.
func NewPostService(uc *biz.PostUsecase) *PostService {
	return &PostService{uc: uc}
}

func (s *PostService) CreatePost(ctx context.Context, req *v1.CreatePostRequest) (*v1.Post, error) {
	uid, ok := auth.UserIDFromContext(ctx)
	if !ok {
		return nil, auth.ErrUnauthorized(v1.ReasonUnauthorized)
	}
	p, err := s.uc.Create(ctx, uid, req.GetTitle(), req.GetBodyMarkdown(), req.GetTags())
	if err != nil {
		return nil, err
	}
	return toPBPost(p), nil
}

func (s *PostService) GetPost(ctx context.Context, req *v1.GetPostRequest) (*v1.Post, error) {
	p, err := s.uc.Get(ctx, req.GetId())
	if err != nil {
		return nil, err
	}
	return toPBPost(p), nil
}

func (s *PostService) ListPosts(ctx context.Context, req *v1.ListPostsRequest) (*v1.ListPostsReply, error) {
	page, size := req.GetPage(), req.GetSize()
	list, total, err := s.uc.List(ctx, page, size, req.GetTag())
	if err != nil {
		return nil, err
	}
	items := make([]*v1.Post, 0, len(list))
	for _, p := range list {
		items = append(items, toPBPost(p))
	}
	return &v1.ListPostsReply{Items: items, Total: total}, nil
}

func (s *PostService) UpdatePost(ctx context.Context, req *v1.UpdatePostRequest) (*v1.Post, error) {
	uid, ok := auth.UserIDFromContext(ctx)
	if !ok {
		return nil, auth.ErrUnauthorized(v1.ReasonUnauthorized)
	}
	p, err := s.uc.Update(ctx, uid, req.GetId(), req.GetTitle(), req.GetBodyMarkdown(), req.GetTags())
	if err != nil {
		return nil, err
	}
	return toPBPost(p), nil
}

func (s *PostService) DeletePost(ctx context.Context, req *v1.DeletePostRequest) (*emptypb.Empty, error) {
	uid, ok := auth.UserIDFromContext(ctx)
	if !ok {
		return nil, auth.ErrUnauthorized(v1.ReasonUnauthorized)
	}
	if err := s.uc.Delete(ctx, uid, req.GetId()); err != nil {
		return nil, err
	}
	return &emptypb.Empty{}, nil
}

func (s *PostService) LikePost(ctx context.Context, req *v1.LikePostRequest) (*v1.LikePostReply, error) {
	uid, ok := auth.UserIDFromContext(ctx)
	if !ok {
		return nil, auth.ErrUnauthorized(v1.ReasonUnauthorized)
	}
	if err := s.uc.Like(ctx, req.GetId(), uid); err != nil {
		return nil, err
	}
	p, err := s.uc.Get(ctx, req.GetId())
	if err != nil {
		return nil, err
	}
	return &v1.LikePostReply{LikesCount: p.LikesCount}, nil
}

func (s *PostService) UnlikePost(ctx context.Context, req *v1.UnlikePostRequest) (*v1.LikePostReply, error) {
	uid, ok := auth.UserIDFromContext(ctx)
	if !ok {
		return nil, auth.ErrUnauthorized(v1.ReasonUnauthorized)
	}
	if err := s.uc.Unlike(ctx, req.GetId(), uid); err != nil {
		return nil, err
	}
	p, err := s.uc.Get(ctx, req.GetId())
	if err != nil {
		return nil, err
	}
	return &v1.LikePostReply{LikesCount: p.LikesCount}, nil
}

func toPBPost(p *biz.Post) *v1.Post {
	if p == nil {
		return nil
	}
	return &v1.Post{
		Id:           p.ID,
		AuthorId:     p.AuthorID,
		Title:        p.Title,
		BodyMarkdown: p.BodyMarkdown,
		Tags:         p.Tags,
		LikesCount:   p.LikesCount,
		CreatedAt:    timestamppb.New(p.CreatedAt),
		UpdatedAt:    timestamppb.New(p.UpdatedAt),
	}
}
