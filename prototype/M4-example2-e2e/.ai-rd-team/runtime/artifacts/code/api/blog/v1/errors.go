// Shared helpers for the hand-written *.pb.go files.
package v1

import (
	kerr "github.com/go-kratos/kratos/v2/errors"
)

// errNotImpl is returned by UnimplementedXxxServer stubs.
func errNotImpl(method string) error {
	return kerr.New(501, "NOT_IMPLEMENTED", method+" not implemented")
}

// ---- Standard kratos error reasons used across services ----
const (
	ReasonValidationFailed   = "VALIDATION_FAILED"
	ReasonUnauthorized       = "UNAUTHORIZED"
	ReasonInvalidCredentials = "INVALID_CREDENTIALS"
	ReasonForbidden          = "FORBIDDEN"
	ReasonUserNotFound       = "USER_NOT_FOUND"
	ReasonPostNotFound       = "POST_NOT_FOUND"
	ReasonCommentNotFound    = "COMMENT_NOT_FOUND"
	ReasonUserEmailExists    = "USER_EMAIL_EXISTS"
)
