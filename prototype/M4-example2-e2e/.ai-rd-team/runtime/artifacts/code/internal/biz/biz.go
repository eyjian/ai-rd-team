// Package biz 实现博客系统的纯业务用例层。
//
// 本包定义领域实体（User/Post/Comment）、仓储接口（UserRepo/PostRepo/CommentRepo）
// 以及用例（UserUsecase/PostUsecase/CommentUsecase）。
//
// 硬约束：
//   - 本包不得 import gorm.io/gorm 或 kratos/transport
//   - 仓储接口由 internal/data 层实现，运行期通过 wire 注入
//   - 对外暴露的错误以 Err* 形式的哨兵错误给出，由 service 层转为 kratos errors
package biz

import "github.com/google/wire"

// ProviderSet 暴露给 wire 的依赖集合。
var ProviderSet = wire.NewSet(
	NewUserUsecase,
	NewPostUsecase,
	NewCommentUsecase,
)
