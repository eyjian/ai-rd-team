// Package biz 提供核心业务用例（Usecase）与 Repo 接口定义。
// 严格要求：本包禁止 import gorm 等基础设施依赖，仅依赖 repo 接口与纯 DO 结构。
package biz

import (
	"context"

	"github.com/google/wire"
)

// ProviderSet is biz providers.
var ProviderSet = wire.NewSet(
	NewUserUsecase,
	NewPostUsecase,
	NewCommentUsecase,
)

// ctxKey 用于在 context 中保存 user_id 等认证信息的私有 key 类型。
type ctxKey string

// UserIDCtxKey 是 context 中 user_id 的 key（int64）。
// 约定：HTTP/GRPC 中间件解析 JWT 后调用 context.WithValue(ctx, biz.UserIDCtxKey, userID)。
const UserIDCtxKey ctxKey = "biz.user_id"

// UserIDFromContext 从 ctx 读取已认证的 user_id。
// 未认证或类型错误时返回 (0, false)。
func UserIDFromContext(ctx context.Context) (int64, bool) {
	v := ctx.Value(UserIDCtxKey)
	if v == nil {
		return 0, false
	}
	id, ok := v.(int64)
	return id, ok
}
