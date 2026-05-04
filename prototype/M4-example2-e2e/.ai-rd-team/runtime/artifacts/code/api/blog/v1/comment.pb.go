package v1

import (
	"context"

	"github.com/go-kratos/kratos/v2/transport/http"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// --- Messages ---

type CreateCommentRequest struct {
	PostId int64  `json:"post_id,omitempty"`
	Body   string `json:"body,omitempty"`
}

type ListCommentRequest struct {
	PostId int64 `json:"post_id,omitempty"`
}

type ListCommentReply struct {
	Items []*CommentReply `json:"items,omitempty"`
}

type CommentReply struct {
	Id        int64                  `json:"id,omitempty"`
	PostId    int64                  `json:"post_id,omitempty"`
	AuthorId  int64                  `json:"author_id,omitempty"`
	Body      string                 `json:"body,omitempty"`
	CreatedAt *timestamppb.Timestamp `json:"created_at,omitempty"`
}

// --- Service interface ---

type CommentServer interface {
	Create(context.Context, *CreateCommentRequest) (*CommentReply, error)
	List(context.Context, *ListCommentRequest) (*ListCommentReply, error)
}

type UnimplementedCommentServer struct{}

func (UnimplementedCommentServer) Create(context.Context, *CreateCommentRequest) (*CommentReply, error) {
	return nil, ErrorInternalError("method Create not implemented")
}
func (UnimplementedCommentServer) List(context.Context, *ListCommentRequest) (*ListCommentReply, error) {
	return nil, ErrorInternalError("method List not implemented")
}

// --- HTTP registration ---

const OperationCommentCreate = "/blog.v1.Comment/Create"
const OperationCommentList = "/blog.v1.Comment/List"

func RegisterCommentHTTPServer(s *http.Server, srv CommentServer) {
	r := s.Route("/")
	r.POST("/v1/posts/{post_id}/comments", _Comment_Create0_HTTP_Handler(srv))
	r.GET("/v1/posts/{post_id}/comments", _Comment_List0_HTTP_Handler(srv))
}

func _Comment_Create0_HTTP_Handler(srv CommentServer) func(http.Context) error {
	return func(ctx http.Context) error {
		var in CreateCommentRequest
		if err := ctx.Bind(&in); err != nil {
			return err
		}
		postID, err := parsePathInt64(ctx, "post_id")
		if err != nil {
			return err
		}
		in.PostId = postID
		http.SetOperation(ctx, OperationCommentCreate)
		h := ctx.Middleware(func(c context.Context, req any) (any, error) {
			return srv.Create(c, req.(*CreateCommentRequest))
		})
		out, err := h(ctx, &in)
		if err != nil {
			return err
		}
		return ctx.Result(200, out.(*CommentReply))
	}
}

func _Comment_List0_HTTP_Handler(srv CommentServer) func(http.Context) error {
	return func(ctx http.Context) error {
		postID, err := parsePathInt64(ctx, "post_id")
		if err != nil {
			return err
		}
		in := &ListCommentRequest{PostId: postID}
		http.SetOperation(ctx, OperationCommentList)
		h := ctx.Middleware(func(c context.Context, req any) (any, error) {
			return srv.List(c, req.(*ListCommentRequest))
		})
		out, err := h(ctx, in)
		if err != nil {
			return err
		}
		return ctx.Result(200, out.(*ListCommentReply))
	}
}
