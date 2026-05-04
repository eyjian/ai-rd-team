// Package service adapts Kratos/proto transport calls to biz Usecases.
package service

import "github.com/google/wire"

// ProviderSet is used by top-level wire to construct all services.
var ProviderSet = wire.NewSet(
	NewUserService,
	NewPostService,
	NewCommentService,
)
