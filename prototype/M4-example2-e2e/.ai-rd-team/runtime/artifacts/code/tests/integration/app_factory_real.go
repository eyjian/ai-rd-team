// Package integration — real app factory wiring BlogAPI for end-to-end tests.
//
// This file is produced by developer_2 to bridge the test harness stub
// (app_stub.go) to the real production wiring. It lives in the tests/integration
// package so it can reach both the stub types (AppConfig/AppRunner/AppFactory)
// and the internal packages.
package integration

import (
	"context"
	"time"

	"blog/internal/biz"
	"blog/internal/conf"
	"blog/internal/data"
	"blog/internal/pkg/auth"
	"blog/internal/server"
	"blog/internal/service"

	khttp "github.com/go-kratos/kratos/v2/transport/http"

	"github.com/go-kratos/kratos/v2/log"
)

func init() {
	AppFactory = realAppFactory
}

// realAppFactory constructs a BlogAPI instance suitable for integration tests.
// It builds each layer manually (equivalent to cmd/server/wire.go) because
// wireApp lives in the main package and isn't importable here.
func realAppFactory(cfg AppConfig, logger log.Logger) (AppRunner, func(), error) {
	bs := translateConfig(cfg)

	d, cleanup, err := data.NewData(bs.GetData(), logger)
	if err != nil {
		return nil, nil, err
	}

	userRepo := data.NewUserRepo(d, logger)
	postRepo := data.NewPostRepo(d, logger)
	commentRepo := data.NewCommentRepo(d, logger)

	jwt := auth.NewJWTIssuer(bs.GetAuth())

	userUC := biz.NewUserUsecase(userRepo, jwt, logger)
	postUC := biz.NewPostUsecase(postRepo, userRepo, logger)
	commentUC := biz.NewCommentUsecase(commentRepo, postRepo, logger)

	userSvc := service.NewUserService(userUC)
	postSvc := service.NewPostService(postUC)
	commentSvc := service.NewCommentService(commentUC)

	httpSrv := server.NewHTTPServer(bs.GetServer(), userSvc, postSvc, commentSvc, jwt, logger)
	grpcSrv := server.NewGRPCServer(bs.GetServer(), logger)

	return &kratosRunner{http: httpSrv, grpc: grpcSrv}, cleanup, nil
}

// compile-time assertion kratosRunner implements AppRunner.
var _ AppRunner = (*kratosRunner)(nil)

func translateConfig(cfg AppConfig) *conf.Bootstrap {
	httpAddr := cfg.HTTPAddr
	if httpAddr == "" {
		httpAddr = "127.0.0.1:0"
	}
	grpcAddr := cfg.GRPCAddr
	if grpcAddr == "" {
		grpcAddr = "127.0.0.1:0"
	}
	timeout := cfg.ServerTimeout
	if timeout <= 0 {
		timeout = 10 * time.Second
	}
	ttl := cfg.AccessTTL
	if ttl <= 0 {
		ttl = 168 * time.Hour
	}
	return &conf.Bootstrap{
		Server: &conf.Server{
			Http: &conf.Server_HTTP{Addr: httpAddr, Timeout: timeout},
			Grpc: &conf.Server_GRPC{Addr: grpcAddr, Timeout: timeout},
		},
		Data: &conf.Data{
			Database: &conf.Data_Database{Driver: "postgres", Source: cfg.PostgresDSN},
			LogLevel: cfg.LogLevel,
		},
		Auth: &conf.Auth{
			JwtSecret: cfg.JWTSecret,
			AccessTtl: ttl,
		},
	}
}

// kratosRunner adapts *khttp.Server (+ optional gRPC) into AppRunner.
//
// The gRPC server is started alongside HTTP for parity with production,
// but the integration tests only call HTTPAddr() and hit HTTP endpoints.
type kratosRunner struct {
	http *khttp.Server
	grpc kratosGRPCServer // interface for Start/Stop, allows nil
	addr string
}

// kratosGRPCServer is the minimal surface needed from *kgrpc.Server.
type kratosGRPCServer interface {
	Start(context.Context) error
	Stop(context.Context) error
}

// HTTPAddr returns the actual bound HTTP address. It triggers listener setup
// eagerly via Endpoint() so that callers using port "0" get a real port.
func (r *kratosRunner) HTTPAddr() string {
	if r.addr != "" {
		return r.addr
	}
	ep, err := r.http.Endpoint()
	if err != nil || ep == nil {
		return ""
	}
	r.addr = ep.Host
	return r.addr
}

// Start launches both transports. It blocks until the server stops or errors.
// The integration suite invokes this in a goroutine and polls HTTPAddr() to
// confirm readiness.
func (r *kratosRunner) Start(ctx context.Context) error {
	// Trigger HTTP listener to bind immediately so HTTPAddr() is stable.
	if _, err := r.http.Endpoint(); err != nil {
		return err
	}
	errCh := make(chan error, 2)
	go func() { errCh <- r.http.Start(ctx) }()
	if r.grpc != nil {
		go func() { errCh <- r.grpc.Start(ctx) }()
	}
	select {
	case err := <-errCh:
		return err
	case <-ctx.Done():
		return ctx.Err()
	}
}

// Stop gracefully shuts down both transports.
func (r *kratosRunner) Stop(ctx context.Context) error {
	var firstErr error
	if err := r.http.Stop(ctx); err != nil {
		firstErr = err
	}
	if r.grpc != nil {
		if err := r.grpc.Stop(ctx); err != nil && firstErr == nil {
			firstErr = err
		}
	}
	return firstErr
}
