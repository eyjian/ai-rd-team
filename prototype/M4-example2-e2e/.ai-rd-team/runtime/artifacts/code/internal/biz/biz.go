// Package biz 汇总业务层 Usecase 与 Repo 接口。
//
// 依赖原则：
//   - biz 层只依赖标准库、kratos 基础包和 domain 内部定义的接口；
//   - 严禁 import `gorm.io/gorm` / `database/sql` / 具体存储实现；
//   - 对外只暴露领域模型（User/Post/Comment）和 *Usecase 聚合根。
package biz

import "github.com/google/wire"

// ProviderSet 用于 wire 依赖注入，集中导出本层的构造函数。
//
// 注意：Repo 接口的实现由 internal/data 提供并在顶层 wire 中绑定，
// 这里只负责把 Usecase 构造函数登记进 ProviderSet。
var ProviderSet = wire.NewSet(
	NewUserUsecase,
	NewPostUsecase,
	NewCommentUsecase,
)
