// app_stub.go 是一个"可替换"的 app 启动钩子。
//
// 目前 developer_2 的 cmd/blog/wireApp 尚未就位，
// 所以 startApp 默认返回 ready=false，所有依赖 baseURL 的用例会自动跳过。
//
// 一旦 wireApp 完成：
//  1. 把本文件重命名为 app_wired.go（或直接替换实现）；
//  2. 在 startApp 中用 wireApp 构造 kratos.App，后台 goroutine 跑 Start；
//  3. 通过 conf.Bootstrap 注入随机 HTTP 端口（server.http.addr=127.0.0.1:0），
//     等待端口就绪后填充 baseURL；
//  4. 返回 shutdown = func() { app.Stop() }；ready=true。
//
// 这样测试文件无需改动，即可自动从"骨架模式"切换到"端到端模式"。
package integration

// startApp 返回：
//   - baseURL：形如 http://127.0.0.1:PORT，如果未启动则为 ""
//   - shutdown：关闭 app 的函数，可为 nil
//   - ready：app 是否已启动
//   - err：致命错误（只在 ready=true 路径下才应非 nil）
var startApp = func(dsn string) (baseURL string, shutdown func(), ready bool, err error) {
	// stub: dev_2 接入后替换此函数
	return "", nil, false, nil
}
