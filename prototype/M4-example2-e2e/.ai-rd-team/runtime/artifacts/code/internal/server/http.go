package server

import (
	v1 "blog/api/blog/v1"
	"blog/internal/conf"
	"blog/internal/pkg/auth"
	"blog/internal/service"

	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/middleware/recovery"
	"github.com/go-kratos/kratos/v2/transport/http"
)

// NewHTTPServer 构造 HTTP server，注册全部 v1 路由并挂 JWT middleware（白名单外需 JWT）
func NewHTTPServer(
	c *conf.Server,
	ac *conf.Auth,
	us *service.UserService,
	ps *service.PostService,
	cs *service.CommentService,
	logger log.Logger,
) *http.Server {
	// 不需要鉴权的路由（与 spec-design.md 第 5 节对齐）
	skipOps := map[string]struct{}{
		v1.OperationUserRegister: {},
		v1.OperationUserLogin:    {},
		v1.OperationPostGet:      {},
		v1.OperationPostList:     {},
		v1.OperationCommentList:  {},
	}

	opts := []http.ServerOption{
		http.Middleware(
			recovery.Recovery(),
			auth.JWTMiddleware(ac.JWTSecret, skipOps),
		),
	}
	if c.HTTP.Network != "" {
		opts = append(opts, http.Network(c.HTTP.Network))
	}
	if c.HTTP.Addr != "" {
		opts = append(opts, http.Address(c.HTTP.Addr))
	}
	if c.HTTP.Timeout > 0 {
		opts = append(opts, http.Timeout(c.HTTP.Timeout))
	}

	srv := http.NewServer(opts...)
	v1.RegisterUserHTTPServer(srv, us)
	v1.RegisterPostHTTPServer(srv, ps)
	v1.RegisterCommentHTTPServer(srv, cs)
	return srv
}
