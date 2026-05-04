//go:build integration_real
// +build integration_real

// 当 dev_2 完成 cmd/server/wire_gen.go 后，将本文件从 build tag 切换为默认编译：
// 把文件顶部的 `//go:build integration_real` 删除即可。
//
// 切换前：测试包能编译但 AppFactory == nil -> 测试会 Skip。
// 切换后：AppFactory 注入到真实 wireApp，testcontainers 拉 PG 真跑测试。
package integration

import (
	"context"
	"fmt"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/log"

	// TODO(tester): 下面两个 import 在 dev_2 完成后放开。
	// 为避免 dev_2 未完成时编译失败，此文件通过 build tag `integration_real` 禁用。
	// cmdserver "blog/cmd/server"
	// "blog/internal/conf"
)

func init() {
	AppFactory = buildRealApp
}

// buildRealApp 使用 dev_2 暴露的 wireApp 构造真实 kratos.App。
// 约定：dev_2 的 cmd/server 包对外导出 WireApp（或等价工厂函数）。
func buildRealApp(ctx context.Context, dsn, jwtSecret string) (*kratos.App, string, func(), error) {
	// 预留实现点，切换 build tag 后按下述骨架填充：
	//
	// port, err := pickFreePort()
	// if err != nil { return nil, "", nil, err }
	// httpAddr := fmt.Sprintf("127.0.0.1:%d", port)
	//
	// bc := &conf.Bootstrap{
	//     Server: &conf.Server{Http: &conf.Server_HTTP{Addr: httpAddr, Timeout: 10 * time.Second}},
	//     Data:   &conf.Data{Database: &conf.Data_Database{Driver: "postgres", Source: dsn}},
	//     Auth:   &conf.Auth{JwtSecret: jwtSecret, Expire: 24 * time.Hour},
	// }
	// app, cleanup, err := cmdserver.WireApp(bc.Server, bc.Data, bc.Auth, log.DefaultLogger)
	// if err != nil { return nil, "", nil, err }
	// go app.Run()
	// return app, httpAddr, cleanup, nil
	_ = log.DefaultLogger
	return nil, "", nil, fmt.Errorf("buildRealApp not yet wired; fill in after dev_2 finishes wire_gen.go")
}
