package server

import (
	"blog/internal/conf"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/transport/grpc"
)

// NewGRPCServer 构造 gRPC server（本期仅提供空壳，未注册任何业务服务，
// 因为 proto 手写等价仅覆盖 HTTP 注册；kratos.App 仍可持有它以满足依赖图）
func NewGRPCServer(c *conf.Server, logger log.Logger) *grpc.Server {
	opts := []grpc.ServerOption{
		grpc.Middleware(recovery.Recovery()),
	}
	if c.GRPC.Network != "" {
		opts = append(opts, grpc.Network(c.GRPC.Network))
	}
	if c.GRPC.Addr != "" {
		opts = append(opts, grpc.Address(c.GRPC.Addr))
	}
	if c.GRPC.Timeout > 0 {
		opts = append(opts, grpc.Timeout(c.GRPC.Timeout))
	}
	return grpc.NewServer(opts...)
}
