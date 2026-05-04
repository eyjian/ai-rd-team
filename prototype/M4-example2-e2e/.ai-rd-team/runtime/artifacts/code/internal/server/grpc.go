package server

import (
	"blog/internal/conf"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/logging"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	kgrpc "github.com/go-kratos/kratos/v2/transport/grpc"
)

// NewGRPCServer builds a minimal kratos gRPC server.
// Services are not individually registered here — HTTP is the primary transport for BlogAPI.
// Starting the gRPC server allows future rpc-only clients to attach via stubs.
func NewGRPCServer(c *conf.Server, logger log.Logger) *kgrpc.Server {
	var opts []kgrpc.ServerOption
	opts = append(opts, kgrpc.Middleware(
		recovery.Recovery(),
		logging.Server(logger),
	))
	if c != nil && c.GetGrpc() != nil {
		if addr := c.GetGrpc().GetAddr(); addr != "" {
			opts = append(opts, kgrpc.Address(addr))
		}
		if to := c.GetGrpc().GetTimeout(); to > 0 {
			opts = append(opts, kgrpc.Timeout(to))
		}
	}
	return kgrpc.NewServer(opts...)
}
