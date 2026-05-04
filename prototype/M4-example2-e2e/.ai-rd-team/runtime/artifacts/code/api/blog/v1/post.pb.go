package v1

import (
	"context"
	"strconv"

	"github.com/go-kratos/kratos/v2/transport/http"
	"google.golang.org/protobuf/types/known/emptypb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// --- Messages ---

type CreatePostRequest struct {
	Title string   `json:"title,omitempty"`
	Body  string   `json:"body,omitempty"`
	Tags  []string `json:"tags,omitempty"`
}

type GetPostRequest struct {
	Id int64 `json:"id,omitempty"`
}

type ListPostRequest struct {
	Page int32  `json:"page,omitempty"`
	Size int32  `json:"size,omitempty"`
	Tag  string `json:"tag,omitempty"`
}

type ListPostReply struct {
	Items []*PostReply `json:"items,omitempty"`
	Total int64        `json:"total,omitempty"`
}

type UpdatePostRequest struct {
	Id    int64    `json:"id,omitempty"`
	Title string   `json:"title,omitempty"`
	Body  string   `json:"body,omitempty"`
	Tags  []string `json:"tags,omitempty"`
}

type DeletePostRequest struct {
	Id int64 `json:"id,omitempty"`
}

type LikeRequest struct {
	Id int64 `json:"id,omitempty"`
}

type PostReply struct {
	Id        int64                  `json:"id,omitempty"`
	AuthorId  int64                  `json:"author_id,omitempty"`
	Title     string                 `json:"title,omitempty"`
	Body      string                 `json:"body,omitempty"`
	Tags      []string               `json:"tags,omitempty"`
	LikeCount int64                  `json:"like_count,omitempty"`
	CreatedAt *timestamppb.Timestamp `json:"created_at,omitempty"`
	UpdatedAt *timestamppb.Timestamp `json:"updated_at,omitempty"`
}

// --- Service interface ---

type PostServer interface {
	Create(context.Context, *CreatePostRequest) (*PostReply, error)
	Get(context.Context, *GetPostRequest) (*PostReply, error)
	List(context.Context, *ListPostRequest) (*ListPostReply, error)
	Update(context.Context, *UpdatePostRequest) (*PostReply, error)
	Delete(context.Context, *DeletePostRequest) (*emptypb.Empty, error)
	Like(context.Context, *LikeRequest) (*emptypb.Empty, error)
	Unlike(context.Context, *LikeRequest) (*emptypb.Empty, error)
}

type UnimplementedPostServer struct{}

func (UnimplementedPostServer) Create(context.Context, *CreatePostRequest) (*PostReply, error) {
	return nil, ErrorInternalError("method Create not implemented")
}
func (UnimplementedPostServer) Get(context.Context, *GetPostRequest) (*PostReply, error) {
	return nil, ErrorInternalError("method Get not implemented")
}
func (UnimplementedPostServer) List(context.Context, *ListPostRequest) (*ListPostReply, error) {
	return nil, ErrorInternalError("method List not implemented")
}
func (UnimplementedPostServer) Update(context.Context, *UpdatePostRequest) (*PostReply, error) {
	return nil, ErrorInternalError("method Update not implemented")
}
func (UnimplementedPostServer) Delete(context.Context, *DeletePostRequest) (*emptypb.Empty, error) {
	return nil, ErrorInternalError("method Delete not implemented")
}
func (UnimplementedPostServer) Like(context.Context, *LikeRequest) (*emptypb.Empty, error) {
	return nil, ErrorInternalError("method Like not implemented")
}
func (UnimplementedPostServer) Unlike(context.Context, *LikeRequest) (*emptypb.Empty, error) {
	return nil, ErrorInternalError("method Unlike not implemented")
}

// --- HTTP registration ---

const OperationPostCreate = "/blog.v1.Post/Create"
const OperationPostGet = "/blog.v1.Post/Get"
const OperationPostList = "/blog.v1.Post/List"
const OperationPostUpdate = "/blog.v1.Post/Update"
const OperationPostDelete = "/blog.v1.Post/Delete"
const OperationPostLike = "/blog.v1.Post/Like"
const OperationPostUnlike = "/blog.v1.Post/Unlike"

func RegisterPostHTTPServer(s *http.Server, srv PostServer) {
	r := s.Route("/")
	r.POST("/v1/posts", _Post_Create0_HTTP_Handler(srv))
	r.GET("/v1/posts/{id}", _Post_Get0_HTTP_Handler(srv))
	r.GET("/v1/posts", _Post_List0_HTTP_Handler(srv))
	r.PUT("/v1/posts/{id}", _Post_Update0_HTTP_Handler(srv))
	r.DELETE("/v1/posts/{id}", _Post_Delete0_HTTP_Handler(srv))
	r.POST("/v1/posts/{id}/like", _Post_Like0_HTTP_Handler(srv))
	r.DELETE("/v1/posts/{id}/like", _Post_Unlike0_HTTP_Handler(srv))
}

func parsePathInt64(ctx http.Context, key string) (int64, error) {
	v := ctx.Vars().Get(key)
	if v == "" {
		return 0, ErrorValidationFailed("missing path param %s", key)
	}
	n, err := strconv.ParseInt(v, 10, 64)
	if err != nil {
		return 0, ErrorValidationFailed("invalid path param %s: %s", key, v)
	}
	return n, nil
}

func _Post_Create0_HTTP_Handler(srv PostServer) func(http.Context) error {
	return func(ctx http.Context) error {
		var in CreatePostRequest
		if err := ctx.Bind(&in); err != nil {
			return err
		}
		http.SetOperation(ctx, OperationPostCreate)
		h := ctx.Middleware(func(c context.Context, req any) (any, error) {
			return srv.Create(c, req.(*CreatePostRequest))
		})
		out, err := h(ctx, &in)
		if err != nil {
			return err
		}
		return ctx.Result(200, out.(*PostReply))
	}
}

func _Post_Get0_HTTP_Handler(srv PostServer) func(http.Context) error {
	return func(ctx http.Context) error {
		id, err := parsePathInt64(ctx, "id")
		if err != nil {
			return err
		}
		in := &GetPostRequest{Id: id}
		http.SetOperation(ctx, OperationPostGet)
		h := ctx.Middleware(func(c context.Context, req any) (any, error) {
			return srv.Get(c, req.(*GetPostRequest))
		})
		out, err := h(ctx, in)
		if err != nil {
			return err
		}
		return ctx.Result(200, out.(*PostReply))
	}
}

func _Post_List0_HTTP_Handler(srv PostServer) func(http.Context) error {
	return func(ctx http.Context) error {
		var in ListPostRequest
		if err := ctx.BindQuery(&in); err != nil {
			return err
		}
		http.SetOperation(ctx, OperationPostList)
		h := ctx.Middleware(func(c context.Context, req any) (any, error) {
			return srv.List(c, req.(*ListPostRequest))
		})
		out, err := h(ctx, &in)
		if err != nil {
			return err
		}
		return ctx.Result(200, out.(*ListPostReply))
	}
}

func _Post_Update0_HTTP_Handler(srv PostServer) func(http.Context) error {
	return func(ctx http.Context) error {
		var in UpdatePostRequest
		if err := ctx.Bind(&in); err != nil {
			return err
		}
		id, err := parsePathInt64(ctx, "id")
		if err != nil {
			return err
		}
		in.Id = id
		http.SetOperation(ctx, OperationPostUpdate)
		h := ctx.Middleware(func(c context.Context, req any) (any, error) {
			return srv.Update(c, req.(*UpdatePostRequest))
		})
		out, err := h(ctx, &in)
		if err != nil {
			return err
		}
		return ctx.Result(200, out.(*PostReply))
	}
}

func _Post_Delete0_HTTP_Handler(srv PostServer) func(http.Context) error {
	return func(ctx http.Context) error {
		id, err := parsePathInt64(ctx, "id")
		if err != nil {
			return err
		}
		in := &DeletePostRequest{Id: id}
		http.SetOperation(ctx, OperationPostDelete)
		h := ctx.Middleware(func(c context.Context, req any) (any, error) {
			return srv.Delete(c, req.(*DeletePostRequest))
		})
		out, err := h(ctx, in)
		if err != nil {
			return err
		}
		return ctx.Result(200, out.(*emptypb.Empty))
	}
}

func _Post_Like0_HTTP_Handler(srv PostServer) func(http.Context) error {
	return func(ctx http.Context) error {
		id, err := parsePathInt64(ctx, "id")
		if err != nil {
			return err
		}
		in := &LikeRequest{Id: id}
		http.SetOperation(ctx, OperationPostLike)
		h := ctx.Middleware(func(c context.Context, req any) (any, error) {
			return srv.Like(c, req.(*LikeRequest))
		})
		out, err := h(ctx, in)
		if err != nil {
			return err
		}
		return ctx.Result(200, out.(*emptypb.Empty))
	}
}

func _Post_Unlike0_HTTP_Handler(srv PostServer) func(http.Context) error {
	return func(ctx http.Context) error {
		id, err := parsePathInt64(ctx, "id")
		if err != nil {
			return err
		}
		in := &LikeRequest{Id: id}
		http.SetOperation(ctx, OperationPostUnlike)
		h := ctx.Middleware(func(c context.Context, req any) (any, error) {
			return srv.Unlike(c, req.(*LikeRequest))
		})
		out, err := h(ctx, in)
		if err != nil {
			return err
		}
		return ctx.Result(200, out.(*emptypb.Empty))
	}
}
