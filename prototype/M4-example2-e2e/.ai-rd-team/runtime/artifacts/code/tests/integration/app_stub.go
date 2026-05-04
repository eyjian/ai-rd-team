// Package integration 集成测试入口（占位钩子）
//
// 设计要点：
//  1. 本包**不直接 import** internal/* 或 cmd/*，保证 dev_2 的 wireApp
//     还没好时，`go build ./tests/...` 也能编译通过。
//  2. 真实的 App 构造通过 AppFactory 变量注入（见 app_factory_real.go）。
//     当 AppFactory == nil 时，测试会 t.Skip，不会真正运行。
//  3. Skip 行为保证 `go test ./...` 在 CI 早期（wire 还没生成时）也不红。
package integration

import (
	"context"
	"net"

	"github.com/go-kratos/kratos/v2"
)

// AppBuilder 返回一个启动好的 kratos.App、用于优雅停止的 cleanup 函数、
// 以及 HTTP 服务监听地址（如 "127.0.0.1:18080"）。
//
// dev_2 完成 cmd/server/wire_gen.go 后，在 app_factory_real.go 里把
// AppFactory 赋值为一个真正调用 wireApp(...) 的构造器即可，测试无需改动。
type AppBuilder func(ctx context.Context, dsn string, jwtSecret string) (app *kratos.App, httpAddr string, cleanup func(), err error)

// AppFactory 由具体实现文件（app_factory_real.go）在 init() 中注入。
// 未注入时为 nil，integration 测试会自动 skip。
var AppFactory AppBuilder

// pickFreePort 返回一个随机可用的 TCP 端口，避免并发测试端口冲突。
func pickFreePort() (int, error) {
	l, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, err
	}
	defer l.Close()
	return l.Addr().(*net.TCPAddr).Port, nil
}
