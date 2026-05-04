// Code hand-written by architect (equivalent to protoc-gen-go output, minimal subset).
// Source: common.proto

package v1

import (
	reflect "reflect"

	protoreflect "google.golang.org/protobuf/reflect/protoreflect"
)

// PageRequest mirrors blog.v1.PageRequest.
type PageRequest struct {
	Page int32 `json:"page,omitempty"`
	Size int32 `json:"size,omitempty"`
}

func (m *PageRequest) Reset()         { *m = PageRequest{} }
func (m *PageRequest) String() string { return "PageRequest" }
func (*PageRequest) ProtoMessage()    {}
func (m *PageRequest) ProtoReflect() protoreflect.Message {
	return nil
}

func (m *PageRequest) GetPage() int32 {
	if m == nil {
		return 0
	}
	return m.Page
}

func (m *PageRequest) GetSize() int32 {
	if m == nil {
		return 0
	}
	return m.Size
}

// avoid unused import warnings
var _ = reflect.TypeOf
