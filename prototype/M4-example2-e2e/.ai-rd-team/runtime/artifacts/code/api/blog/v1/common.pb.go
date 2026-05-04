// Code equivalent to protoc-gen-go output (hand-written for prototype).
package v1

import (
	"google.golang.org/protobuf/types/known/timestamppb"
)

// Ensure timestamppb is referenced (other files may depend on it).
var _ = (*timestamppb.Timestamp)(nil)

// PageRequest 通用分页
type PageRequest struct {
	Page int32  `json:"page,omitempty"`
	Size int32  `json:"size,omitempty"`
	Tag  string `json:"tag,omitempty"`
}

// Empty 通用空消息
type Empty struct{}
