//go:build wireinject
// +build wireinject

// wire.go 定义依赖图；实际由 wire 命令生成 wire_gen.go。
// 本项目为原型，直接手写等价 wire_gen.go。该文件仅作为参考与 wire 工具入口。
package main

import (
	"blog/internal/biz"
	"blog/internal/conf"
	"blog/internal/data"
	"blog/internal/server"
	"blog/internal/service"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/google/wire"
)

// wireApp init kratos application.
func wireApp(*conf.Server, *conf.Data, *conf.Auth, log.Logger) (*kratos.App, func(), error) {
	panic(wire.Build(
		data.ProviderSet,
		biz.ProviderSet,
		service.ProviderSet,
		server.ProviderSet,
		wire.Value([]kratos.Option(nil)),
		NewApp,
	))
}
