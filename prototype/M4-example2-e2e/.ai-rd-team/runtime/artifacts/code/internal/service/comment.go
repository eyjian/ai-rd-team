package service

import (
	"context"

	v1 "blog/api/blog/v1"
	"blog/internal/biz"
	"blog/internal/pkg/auth"

	"google.golang.org/protobuf/types/known/timestamppb"
)

// CommentService adapts v1.CommentServiceServer to biz.CommentUsecase.
type CommentService struct {
	v1.UnimplementedCommentServiceServer
	uc *biz.CommentUsecase
}

// NewCommentService constructor.
func NewCommentService(uc *biz.CommentUsecase) *CommentService {
	return &CommentService{uc: uc}
}

func (s *CommentService) CreateComment(ctx context.Context, req *v1.CreateCommentRequest) (*v1.Comment, error) {
	uid, ok := auth.UserIDFromContext(ctx)
	if !ok {
		return nil, auth.ErrUnauthorized(v1.ReasonUnauthorized)
	}
	c, err := s.uc.Create(ctx, req.GetPostId(), uid, req.GetContent())
	if err != nil {
		return nil, err
	}
	return toPBComment(c), nil
}

func (s *CommentService) ListComments(ctx context.Context, req *v1.ListCommentsRequest) (*v1.ListCommentsReply, error) {
	page, size := req.GetPage(), req.GetSize()
	list, total, err := s.uc.ListByPost(ctx, req.GetPostId(), page, size)
	if err != nil {
		return nil, err
	}
	items := make([]*v1.Comment, 0, len(list))
	for _, c := range list {
		items = append(items, toPBComment(c))
	}
	return &v1.ListCommentsReply{Items: items, Total: total}, nil
}

func toPBComment(c *biz.Comment) *v1.Comment {
	if c == nil {
		return nil
	}
	return &v1.Comment{
		Id:        c.ID,
		PostId:    c.PostID,
		AuthorId:  c.AuthorID,
		Content:   c.Content,
		CreatedAt: timestamppb.New(c.CreatedAt),
	}
}
