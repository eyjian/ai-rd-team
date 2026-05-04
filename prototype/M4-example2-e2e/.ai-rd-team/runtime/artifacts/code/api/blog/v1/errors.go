package v1

import (
	"fmt"

	"github.com/go-kratos/kratos/v2/errors"
)

// Error reason constants
const (
	ReasonUserNotFound          = "USER_NOT_FOUND"
	ReasonUserAlreadyExists     = "USER_ALREADY_EXISTS"
	ReasonUserCredentialInvalid = "USER_CREDENTIAL_INVALID"
	ReasonUserUnauthenticated   = "USER_UNAUTHENTICATED"
	ReasonPostNotFound          = "POST_NOT_FOUND"
	ReasonPostForbidden         = "POST_FORBIDDEN"
	ReasonCommentNotFound       = "COMMENT_NOT_FOUND"
	ReasonValidationFailed      = "VALIDATION_FAILED"
	ReasonInternalError         = "INTERNAL_ERROR"
)

// IsXxx helpers
func IsUserNotFound(err error) bool         { return errors.Code(err) == 404 && errors.Reason(err) == ReasonUserNotFound }
func IsUserAlreadyExists(err error) bool    { return errors.Reason(err) == ReasonUserAlreadyExists }
func IsUserCredentialInvalid(err error) bool{ return errors.Reason(err) == ReasonUserCredentialInvalid }
func IsUserUnauthenticated(err error) bool  { return errors.Reason(err) == ReasonUserUnauthenticated }
func IsPostNotFound(err error) bool         { return errors.Reason(err) == ReasonPostNotFound }
func IsPostForbidden(err error) bool        { return errors.Reason(err) == ReasonPostForbidden }
func IsCommentNotFound(err error) bool      { return errors.Reason(err) == ReasonCommentNotFound }
func IsValidationFailed(err error) bool     { return errors.Reason(err) == ReasonValidationFailed }

// Constructors
func ErrorUserNotFound(format string, a ...any) *errors.Error {
	return errors.New(404, ReasonUserNotFound, fmt.Sprintf(format, a...))
}
func ErrorUserAlreadyExists(format string, a ...any) *errors.Error {
	return errors.New(409, ReasonUserAlreadyExists, fmt.Sprintf(format, a...))
}
func ErrorUserCredentialInvalid(format string, a ...any) *errors.Error {
	return errors.New(401, ReasonUserCredentialInvalid, fmt.Sprintf(format, a...))
}
func ErrorUserUnauthenticated(format string, a ...any) *errors.Error {
	return errors.New(401, ReasonUserUnauthenticated, fmt.Sprintf(format, a...))
}
func ErrorPostNotFound(format string, a ...any) *errors.Error {
	return errors.New(404, ReasonPostNotFound, fmt.Sprintf(format, a...))
}
func ErrorPostForbidden(format string, a ...any) *errors.Error {
	return errors.New(403, ReasonPostForbidden, fmt.Sprintf(format, a...))
}
func ErrorCommentNotFound(format string, a ...any) *errors.Error {
	return errors.New(404, ReasonCommentNotFound, fmt.Sprintf(format, a...))
}
func ErrorValidationFailed(format string, a ...any) *errors.Error {
	return errors.New(400, ReasonValidationFailed, fmt.Sprintf(format, a...))
}
func ErrorInternalError(format string, a ...any) *errors.Error {
	return errors.New(500, ReasonInternalError, fmt.Sprintf(format, a...))
}
