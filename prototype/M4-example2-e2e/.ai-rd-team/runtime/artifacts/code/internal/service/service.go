package service

import "github.com/google/wire"

// ProviderSet service 层 wire set
var ProviderSet = wire.NewSet(NewUserService, NewPostService, NewCommentService)
