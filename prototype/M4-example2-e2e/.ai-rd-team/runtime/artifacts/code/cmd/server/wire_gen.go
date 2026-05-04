//go:build !wireinject
// +build !wireinject

// Code generated manually (equivalent to wire output). DO NOT EDIT lightly.
package main

import (
	"blog/internal/biz"
	"blog/internal/conf"
	"blog/internal/data"
	"blog/internal/server"
	"blog/internal/service"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/log"
)

// wireApp 手写等价 wire_gen 输出
//
// 注入链：
//
//	Bootstrap -> Data(GORM *gorm.DB) -> Repo -> Usecase -> Service -> HTTPServer+GRPCServer -> kratos.App
func wireApp(sc *conf.Server, dc *conf.Data, ac *conf.Auth, logger log.Logger) (*kratos.App, func(), error) {
	// data 层
	d, cleanupData, err := data.NewData(dc, logger)
	if err != nil {
		return nil, nil, err
	}

	userRepo := data.NewUserRepo(d, logger)
	postRepo := data.NewPostRepo(d, logger)
	commentRepo := data.NewCommentRepo(d, logger)
	postLikeRepo := data.NewPostLikeRepo(d, logger)

	// biz 层
	userUC := biz.NewUserUsecase(userRepo, ac, logger)
	postUC := biz.NewPostUsecase(postRepo, postLikeRepo, logger)
	commentUC := biz.NewCommentUsecase(commentRepo, postRepo, logger)

	// service 层
	userSvc := service.NewUserService(userUC, logger)
	postSvc := service.NewPostService(postUC, logger)
	commentSvc := service.NewCommentService(commentUC, logger)

	// server 层
	httpSrv := server.NewHTTPServer(sc, ac, userSvc, postSvc, commentSvc, logger)
	grpcSrv := server.NewGRPCServer(sc, logger)

	app := NewApp(logger, httpSrv, grpcSrv)

	cleanup := func() {
		cleanupData()
	}

	return app, cleanup, nil
}

// WireApp 对外导出的 AppFactory，tester 的 app_factory_real.go 可直接调用
func WireApp(sc *conf.Server, dc *conf.Data, ac *conf.Auth, logger log.Logger) (*kratos.App, func(), error) {
	return wireApp(sc, dc, ac, logger)
}

// NewAppFactory 返回符合 tester 约定的工厂函数（签名: func(*conf.Bootstrap, log.Logger) (*kratos.App, func(), error)）
func NewAppFactory() func(bc *conf.Bootstrap, logger log.Logger) (*kratos.App, func(), error) {
	return func(bc *conf.Bootstrap, logger log.Logger) (*kratos.App, func(), error) {
		return wireApp(bc.Server, bc.Data, bc.Auth, logger)
	}
}
