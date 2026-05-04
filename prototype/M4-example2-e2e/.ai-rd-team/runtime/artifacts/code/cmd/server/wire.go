package main

import (
	"blog/internal/biz"
	"blog/internal/conf"
	"blog/internal/data"
	"blog/internal/pkg/auth"
	"blog/internal/server"
	"blog/internal/service"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/log"
)

// wireApp is the hand-written dependency injector (equivalent to wire_gen.go).
// It composes: data -> repos -> usecases -> services -> servers -> app.
func wireApp(bs *conf.Bootstrap, logger log.Logger) (*kratos.App, func(), error) {
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

	app := newApp(logger, httpSrv, grpcSrv)
	return app, cleanup, nil
}
