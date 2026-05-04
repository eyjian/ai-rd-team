package service

import (
	"context"

	v1 "blog/api/blog/v1"
	"blog/internal/biz"
	"blog/internal/pkg/auth"

	"github.com/go-kratos/kratos/v2/log"
	"google.golang.org/protobuf/types/known/emptypb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// PostService 文章协议层
type PostService struct {
	v1.UnimplementedPostServer

	uc  *biz.PostUsecase
	log *log.Helper
}

func NewPostService(uc *biz.PostUsecase, logger log.Logger) *PostService {
	return &PostService{uc: uc, log: log.NewHelper(logger)}
}

func postToReply(p *biz.Post) *v1.PostReply {
	if p == nil {
		return nil
	}
	return &v1.PostReply{
		Id:        p.ID,
		AuthorId:  p.AuthorID,
		Title:     p.Title,
		Body:      p.Body,
		Tags:      p.Tags,
		LikeCount: p.LikeCount,
		CreatedAt: timestamppb.New(p.CreatedAt),
		UpdatedAt: timestamppb.New(p.UpdatedAt),
	}
}

func (s *PostService) Create(ctx context.Context, req *v1.CreatePostRequest) (*v1.PostReply, error) {
	uid, err := auth.MustUserIDFromContext(ctx)
	if err != nil {
		return nil, err
	}
	if req.Title == "" {
		return nil, v1.ErrorValidationFailed("title required")
	}
	p, err := s.uc.Create(ctx, uid, req.Title, req.Body, req.Tags)
	if err != nil {
		return nil, err
	}
	return postToReply(p), nil
}

func (s *PostService) Get(ctx context.Context, req *v1.GetPostRequest) (*v1.PostReply, error) {
	if req.Id <= 0 {
		return nil, v1.ErrorValidationFailed("invalid id")
	}
	p, err := s.uc.Get(ctx, req.Id)
	if err != nil {
		return nil, err
	}
	return postToReply(p), nil
}

func (s *PostService) List(ctx context.Context, req *v1.ListPostRequest) (*v1.ListPostReply, error) {
	page := req.Page
	if page <= 0 {
		page = 1
	}
	size := req.Size
	if size <= 0 {
		size = 10
	}
	if size > 50 {
		size = 50
	}
	list, total, err := s.uc.List(ctx, page, size, req.Tag)
	if err != nil {
		return nil, err
	}
	items := make([]*v1.PostReply, 0, len(list))
	for _, p := range list {
		items = append(items, postToReply(p))
	}
	return &v1.ListPostReply{Items: items, Total: total}, nil
}

func (s *PostService) Update(ctx context.Context, req *v1.UpdatePostRequest) (*v1.PostReply, error) {
	uid, err := auth.MustUserIDFromContext(ctx)
	if err != nil {
		return nil, err
	}
	if req.Id <= 0 {
		return nil, v1.ErrorValidationFailed("invalid id")
	}
	p, err := s.uc.Update(ctx, uid, req.Id, req.Title, req.Body, req.Tags)
	if err != nil {
		return nil, err
	}
	return postToReply(p), nil
}

func (s *PostService) Delete(ctx context.Context, req *v1.DeletePostRequest) (*emptypb.Empty, error) {
	uid, err := auth.MustUserIDFromContext(ctx)
	if err != nil {
		return nil, err
	}
	if req.Id <= 0 {
		return nil, v1.ErrorValidationFailed("invalid id")
	}
	if err := s.uc.Delete(ctx, uid, req.Id); err != nil {
		return nil, err
	}
	return &emptypb.Empty{}, nil
}

func (s *PostService) Like(ctx context.Context, req *v1.LikeRequest) (*emptypb.Empty, error) {
	uid, err := auth.MustUserIDFromContext(ctx)
	if err != nil {
		return nil, err
	}
	if req.Id <= 0 {
		return nil, v1.ErrorValidationFailed("invalid id")
	}
	if err := s.uc.Like(ctx, req.Id, uid); err != nil {
		return nil, err
	}
	return &emptypb.Empty{}, nil
}

func (s *PostService) Unlike(ctx context.Context, req *v1.LikeRequest) (*emptypb.Empty, error) {
	uid, err := auth.MustUserIDFromContext(ctx)
	if err != nil {
		return nil, err
	}
	if req.Id <= 0 {
		return nil, v1.ErrorValidationFailed("invalid id")
	}
	if err := s.uc.Unlike(ctx, req.Id, uid); err != nil {
		return nil, err
	}
	return &emptypb.Empty{}, nil
}
