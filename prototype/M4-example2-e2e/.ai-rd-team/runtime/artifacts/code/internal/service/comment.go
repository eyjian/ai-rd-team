package service

import (
	"context"

	v1 "blog/api/blog/v1"
	"blog/internal/biz"
	"blog/internal/pkg/auth"

	"github.com/go-kratos/kratos/v2/log"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// CommentService 评论协议层
type CommentService struct {
	v1.UnimplementedCommentServer

	uc  *biz.CommentUsecase
	log *log.Helper
}

func NewCommentService(uc *biz.CommentUsecase, logger log.Logger) *CommentService {
	return &CommentService{uc: uc, log: log.NewHelper(logger)}
}

func commentToReply(c *biz.Comment) *v1.CommentReply {
	if c == nil {
		return nil
	}
	return &v1.CommentReply{
		Id:        c.ID,
		PostId:    c.PostID,
		AuthorId:  c.AuthorID,
		Body:      c.Body,
		CreatedAt: timestamppb.New(c.CreatedAt),
	}
}

func (s *CommentService) Create(ctx context.Context, req *v1.CreateCommentRequest) (*v1.CommentReply, error) {
	uid, err := auth.MustUserIDFromContext(ctx)
	if err != nil {
		return nil, err
	}
	if req.PostId <= 0 {
		return nil, v1.ErrorValidationFailed("invalid post_id")
	}
	if req.Body == "" {
		return nil, v1.ErrorValidationFailed("body required")
	}
	c, err := s.uc.Create(ctx, req.PostId, uid, req.Body)
	if err != nil {
		return nil, err
	}
	return commentToReply(c), nil
}

func (s *CommentService) List(ctx context.Context, req *v1.ListCommentRequest) (*v1.ListCommentReply, error) {
	if req.PostId <= 0 {
		return nil, v1.ErrorValidationFailed("invalid post_id")
	}
	list, err := s.uc.ListByPost(ctx, req.PostId)
	if err != nil {
		return nil, err
	}
	items := make([]*v1.CommentReply, 0, len(list))
	for _, c := range list {
		items = append(items, commentToReply(c))
	}
	return &v1.ListCommentReply{Items: items}, nil
}
