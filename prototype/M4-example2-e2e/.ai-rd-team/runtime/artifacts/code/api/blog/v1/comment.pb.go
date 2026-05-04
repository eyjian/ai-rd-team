// Code hand-written by architect (minimal subset of protoc-gen-go output).
// Source: comment.proto

package v1

import (
	context "context"

	"google.golang.org/protobuf/reflect/protoreflect"
	timestamppb "google.golang.org/protobuf/types/known/timestamppb"
)

type Comment struct {
	Id        int64                  `json:"id,omitempty"`
	PostId    int64                  `json:"post_id,omitempty"`
	AuthorId  int64                  `json:"author_id,omitempty"`
	Content   string                 `json:"content,omitempty"`
	CreatedAt *timestamppb.Timestamp `json:"created_at,omitempty"`
}

func (m *Comment) Reset()                              { *m = Comment{} }
func (m *Comment) String() string                      { return "Comment" }
func (*Comment) ProtoMessage()                         {}
func (m *Comment) ProtoReflect() protoreflect.Message  { return nil }

func (m *Comment) GetId() int64 {
	if m == nil {
		return 0
	}
	return m.Id
}
func (m *Comment) GetPostId() int64 {
	if m == nil {
		return 0
	}
	return m.PostId
}
func (m *Comment) GetAuthorId() int64 {
	if m == nil {
		return 0
	}
	return m.AuthorId
}
func (m *Comment) GetContent() string {
	if m == nil {
		return ""
	}
	return m.Content
}
func (m *Comment) GetCreatedAt() *timestamppb.Timestamp {
	if m == nil {
		return nil
	}
	return m.CreatedAt
}

type CreateCommentRequest struct {
	PostId  int64  `json:"post_id,omitempty"`
	Content string `json:"content,omitempty"`
}

func (m *CreateCommentRequest) Reset()                              { *m = CreateCommentRequest{} }
func (m *CreateCommentRequest) String() string                      { return "CreateCommentRequest" }
func (*CreateCommentRequest) ProtoMessage()                         {}
func (m *CreateCommentRequest) ProtoReflect() protoreflect.Message  { return nil }

func (m *CreateCommentRequest) GetPostId() int64 {
	if m == nil {
		return 0
	}
	return m.PostId
}
func (m *CreateCommentRequest) GetContent() string {
	if m == nil {
		return ""
	}
	return m.Content
}

type ListCommentsRequest struct {
	PostId int64 `json:"post_id,omitempty"`
	Page   int32 `json:"page,omitempty"`
	Size   int32 `json:"size,omitempty"`
}

func (m *ListCommentsRequest) Reset()                              { *m = ListCommentsRequest{} }
func (m *ListCommentsRequest) String() string                      { return "ListCommentsRequest" }
func (*ListCommentsRequest) ProtoMessage()                         {}
func (m *ListCommentsRequest) ProtoReflect() protoreflect.Message  { return nil }

func (m *ListCommentsRequest) GetPostId() int64 {
	if m == nil {
		return 0
	}
	return m.PostId
}
func (m *ListCommentsRequest) GetPage() int32 {
	if m == nil {
		return 0
	}
	return m.Page
}
func (m *ListCommentsRequest) GetSize() int32 {
	if m == nil {
		return 0
	}
	return m.Size
}

type ListCommentsReply struct {
	Items []*Comment `json:"items,omitempty"`
	Total int64      `json:"total,omitempty"`
}

func (m *ListCommentsReply) Reset()                              { *m = ListCommentsReply{} }
func (m *ListCommentsReply) String() string                      { return "ListCommentsReply" }
func (*ListCommentsReply) ProtoMessage()                         {}
func (m *ListCommentsReply) ProtoReflect() protoreflect.Message  { return nil }

func (m *ListCommentsReply) GetItems() []*Comment {
	if m == nil {
		return nil
	}
	return m.Items
}
func (m *ListCommentsReply) GetTotal() int64 {
	if m == nil {
		return 0
	}
	return m.Total
}

// ----------------------------- Service -------------------------------------

type CommentServiceServer interface {
	CreateComment(ctx context.Context, req *CreateCommentRequest) (*Comment, error)
	ListComments(ctx context.Context, req *ListCommentsRequest) (*ListCommentsReply, error)
}

type UnimplementedCommentServiceServer struct{}

func (UnimplementedCommentServiceServer) CreateComment(context.Context, *CreateCommentRequest) (*Comment, error) {
	return nil, errNotImpl("CreateComment")
}
func (UnimplementedCommentServiceServer) ListComments(context.Context, *ListCommentsRequest) (*ListCommentsReply, error) {
	return nil, errNotImpl("ListComments")
}
