// Code hand-written by architect (minimal subset of protoc-gen-go output).
// Source: post.proto

package v1

import (
	context "context"

	"google.golang.org/protobuf/reflect/protoreflect"
	emptypb "google.golang.org/protobuf/types/known/emptypb"
	timestamppb "google.golang.org/protobuf/types/known/timestamppb"
)

// ----------------------------- Messages ------------------------------------

type Post struct {
	Id           int64                  `json:"id,omitempty"`
	AuthorId     int64                  `json:"author_id,omitempty"`
	Title        string                 `json:"title,omitempty"`
	BodyMarkdown string                 `json:"body_markdown,omitempty"`
	Tags         []string               `json:"tags,omitempty"`
	LikesCount   int64                  `json:"likes_count,omitempty"`
	CreatedAt    *timestamppb.Timestamp `json:"created_at,omitempty"`
	UpdatedAt    *timestamppb.Timestamp `json:"updated_at,omitempty"`
}

func (m *Post) Reset()                              { *m = Post{} }
func (m *Post) String() string                      { return "Post" }
func (*Post) ProtoMessage()                         {}
func (m *Post) ProtoReflect() protoreflect.Message  { return nil }

func (m *Post) GetId() int64 {
	if m == nil {
		return 0
	}
	return m.Id
}
func (m *Post) GetAuthorId() int64 {
	if m == nil {
		return 0
	}
	return m.AuthorId
}
func (m *Post) GetTitle() string {
	if m == nil {
		return ""
	}
	return m.Title
}
func (m *Post) GetBodyMarkdown() string {
	if m == nil {
		return ""
	}
	return m.BodyMarkdown
}
func (m *Post) GetTags() []string {
	if m == nil {
		return nil
	}
	return m.Tags
}
func (m *Post) GetLikesCount() int64 {
	if m == nil {
		return 0
	}
	return m.LikesCount
}
func (m *Post) GetCreatedAt() *timestamppb.Timestamp {
	if m == nil {
		return nil
	}
	return m.CreatedAt
}
func (m *Post) GetUpdatedAt() *timestamppb.Timestamp {
	if m == nil {
		return nil
	}
	return m.UpdatedAt
}

type CreatePostRequest struct {
	Title        string   `json:"title,omitempty"`
	BodyMarkdown string   `json:"body_markdown,omitempty"`
	Tags         []string `json:"tags,omitempty"`
}

func (m *CreatePostRequest) Reset()                              { *m = CreatePostRequest{} }
func (m *CreatePostRequest) String() string                      { return "CreatePostRequest" }
func (*CreatePostRequest) ProtoMessage()                         {}
func (m *CreatePostRequest) ProtoReflect() protoreflect.Message  { return nil }

func (m *CreatePostRequest) GetTitle() string {
	if m == nil {
		return ""
	}
	return m.Title
}
func (m *CreatePostRequest) GetBodyMarkdown() string {
	if m == nil {
		return ""
	}
	return m.BodyMarkdown
}
func (m *CreatePostRequest) GetTags() []string {
	if m == nil {
		return nil
	}
	return m.Tags
}

type GetPostRequest struct {
	Id int64 `json:"id,omitempty"`
}

func (m *GetPostRequest) Reset()                              { *m = GetPostRequest{} }
func (m *GetPostRequest) String() string                      { return "GetPostRequest" }
func (*GetPostRequest) ProtoMessage()                         {}
func (m *GetPostRequest) ProtoReflect() protoreflect.Message  { return nil }

func (m *GetPostRequest) GetId() int64 {
	if m == nil {
		return 0
	}
	return m.Id
}

type DeletePostRequest struct {
	Id int64 `json:"id,omitempty"`
}

func (m *DeletePostRequest) Reset()                              { *m = DeletePostRequest{} }
func (m *DeletePostRequest) String() string                      { return "DeletePostRequest" }
func (*DeletePostRequest) ProtoMessage()                         {}
func (m *DeletePostRequest) ProtoReflect() protoreflect.Message  { return nil }

func (m *DeletePostRequest) GetId() int64 {
	if m == nil {
		return 0
	}
	return m.Id
}

type UpdatePostRequest struct {
	Id           int64    `json:"id,omitempty"`
	Title        string   `json:"title,omitempty"`
	BodyMarkdown string   `json:"body_markdown,omitempty"`
	Tags         []string `json:"tags,omitempty"`
}

func (m *UpdatePostRequest) Reset()                              { *m = UpdatePostRequest{} }
func (m *UpdatePostRequest) String() string                      { return "UpdatePostRequest" }
func (*UpdatePostRequest) ProtoMessage()                         {}
func (m *UpdatePostRequest) ProtoReflect() protoreflect.Message  { return nil }

func (m *UpdatePostRequest) GetId() int64 {
	if m == nil {
		return 0
	}
	return m.Id
}
func (m *UpdatePostRequest) GetTitle() string {
	if m == nil {
		return ""
	}
	return m.Title
}
func (m *UpdatePostRequest) GetBodyMarkdown() string {
	if m == nil {
		return ""
	}
	return m.BodyMarkdown
}
func (m *UpdatePostRequest) GetTags() []string {
	if m == nil {
		return nil
	}
	return m.Tags
}

type ListPostsRequest struct {
	Page int32  `json:"page,omitempty"`
	Size int32  `json:"size,omitempty"`
	Tag  string `json:"tag,omitempty"`
}

func (m *ListPostsRequest) Reset()                              { *m = ListPostsRequest{} }
func (m *ListPostsRequest) String() string                      { return "ListPostsRequest" }
func (*ListPostsRequest) ProtoMessage()                         {}
func (m *ListPostsRequest) ProtoReflect() protoreflect.Message  { return nil }

func (m *ListPostsRequest) GetPage() int32 {
	if m == nil {
		return 0
	}
	return m.Page
}
func (m *ListPostsRequest) GetSize() int32 {
	if m == nil {
		return 0
	}
	return m.Size
}
func (m *ListPostsRequest) GetTag() string {
	if m == nil {
		return ""
	}
	return m.Tag
}

type ListPostsReply struct {
	Items []*Post `json:"items,omitempty"`
	Total int64   `json:"total,omitempty"`
}

func (m *ListPostsReply) Reset()                              { *m = ListPostsReply{} }
func (m *ListPostsReply) String() string                      { return "ListPostsReply" }
func (*ListPostsReply) ProtoMessage()                         {}
func (m *ListPostsReply) ProtoReflect() protoreflect.Message  { return nil }

func (m *ListPostsReply) GetItems() []*Post {
	if m == nil {
		return nil
	}
	return m.Items
}
func (m *ListPostsReply) GetTotal() int64 {
	if m == nil {
		return 0
	}
	return m.Total
}

type LikePostRequest struct {
	Id int64 `json:"id,omitempty"`
}

func (m *LikePostRequest) Reset()                              { *m = LikePostRequest{} }
func (m *LikePostRequest) String() string                      { return "LikePostRequest" }
func (*LikePostRequest) ProtoMessage()                         {}
func (m *LikePostRequest) ProtoReflect() protoreflect.Message  { return nil }

func (m *LikePostRequest) GetId() int64 {
	if m == nil {
		return 0
	}
	return m.Id
}

type UnlikePostRequest struct {
	Id int64 `json:"id,omitempty"`
}

func (m *UnlikePostRequest) Reset()                              { *m = UnlikePostRequest{} }
func (m *UnlikePostRequest) String() string                      { return "UnlikePostRequest" }
func (*UnlikePostRequest) ProtoMessage()                         {}
func (m *UnlikePostRequest) ProtoReflect() protoreflect.Message  { return nil }

func (m *UnlikePostRequest) GetId() int64 {
	if m == nil {
		return 0
	}
	return m.Id
}

type LikePostReply struct {
	LikesCount int64 `json:"likes_count,omitempty"`
}

func (m *LikePostReply) Reset()                              { *m = LikePostReply{} }
func (m *LikePostReply) String() string                      { return "LikePostReply" }
func (*LikePostReply) ProtoMessage()                         {}
func (m *LikePostReply) ProtoReflect() protoreflect.Message  { return nil }

func (m *LikePostReply) GetLikesCount() int64 {
	if m == nil {
		return 0
	}
	return m.LikesCount
}

// ----------------------------- Service -------------------------------------

// PostServiceServer is implemented by internal/service.PostService.
type PostServiceServer interface {
	CreatePost(ctx context.Context, req *CreatePostRequest) (*Post, error)
	GetPost(ctx context.Context, req *GetPostRequest) (*Post, error)
	UpdatePost(ctx context.Context, req *UpdatePostRequest) (*Post, error)
	DeletePost(ctx context.Context, req *DeletePostRequest) (*emptypb.Empty, error)
	ListPosts(ctx context.Context, req *ListPostsRequest) (*ListPostsReply, error)
	LikePost(ctx context.Context, req *LikePostRequest) (*LikePostReply, error)
	UnlikePost(ctx context.Context, req *UnlikePostRequest) (*LikePostReply, error)
}

type UnimplementedPostServiceServer struct{}

func (UnimplementedPostServiceServer) CreatePost(context.Context, *CreatePostRequest) (*Post, error) {
	return nil, errNotImpl("CreatePost")
}
func (UnimplementedPostServiceServer) GetPost(context.Context, *GetPostRequest) (*Post, error) {
	return nil, errNotImpl("GetPost")
}
func (UnimplementedPostServiceServer) UpdatePost(context.Context, *UpdatePostRequest) (*Post, error) {
	return nil, errNotImpl("UpdatePost")
}
func (UnimplementedPostServiceServer) DeletePost(context.Context, *DeletePostRequest) (*emptypb.Empty, error) {
	return nil, errNotImpl("DeletePost")
}
func (UnimplementedPostServiceServer) ListPosts(context.Context, *ListPostsRequest) (*ListPostsReply, error) {
	return nil, errNotImpl("ListPosts")
}
func (UnimplementedPostServiceServer) LikePost(context.Context, *LikePostRequest) (*LikePostReply, error) {
	return nil, errNotImpl("LikePost")
}
func (UnimplementedPostServiceServer) UnlikePost(context.Context, *UnlikePostRequest) (*LikePostReply, error) {
	return nil, errNotImpl("UnlikePost")
}
