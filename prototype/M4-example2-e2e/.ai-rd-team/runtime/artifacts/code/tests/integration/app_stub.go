// Package integration provides end-to-end integration tests for the BlogAPI.
//
// app_stub.go holds the decoupling hook between the test harness and the
// real application wiring that lives in cmd/server/wire_gen.go.
//
// developer_2 is expected to register a real factory into AppFactory in an
// init() from a file like `tests/integration/app_factory_real.go` (or via a
// `_test.go` file that imports cmd/server) once the wire graph is ready.
//
// Until then, AppFactory stays nil and all tests that rely on it will be
// skipped via requireAppFactory(t). This keeps `go build ./...` green even
// before the server side is finished.
package integration

import (
	"context"
	"time"

	"github.com/go-kratos/kratos/v2/log"
)

// AppConfig is the minimal slice of Bootstrap config the integration suite
// passes into the real wireApp. It intentionally uses plain types (no proto
// messages, no google.protobuf.Duration) so this file does NOT depend on
// `blog/internal/conf` — that package is produced by developer_2 and we do
// not want to couple the test harness to its concrete field layout.
//
// developer_2's adapter is expected to translate AppConfig into the real
// confv1.Bootstrap before calling WireApp.
type AppConfig struct {
	// HTTPAddr is the listen address for the HTTP server. Tests normally
	// pass "127.0.0.1:0" so the kernel picks a free port.
	HTTPAddr string
	// GRPCAddr is optional — tests only exercise HTTP, but the server
	// boots both by default, so we must offer a free gRPC port too.
	GRPCAddr string
	// ServerTimeout is the per-request timeout for the transport layer.
	ServerTimeout time.Duration

	// PostgresDSN points at the testcontainer-managed instance.
	PostgresDSN string
	// LogLevel controls the internal log verbosity.
	LogLevel string

	// JWTSecret + AccessTTL must match what the suite later uses to forge
	// or validate tokens.
	JWTSecret string
	AccessTTL time.Duration
}

// AppRunner is the minimal surface the integration suite needs from a
// running BlogAPI instance.
//
// It is intentionally narrower than *kratos.App: the tests only need to
//
//   1) know the HTTP address where the server is listening, and
//   2) be able to stop the server at the end of the suite.
//
// developer_2's real factory wraps *kratos.App into this interface.
type AppRunner interface {
	// HTTPAddr returns the concrete HTTP listen address, e.g. "127.0.0.1:43211".
	// It must be the address actually bound after Start, not the raw config value,
	// so that tests using port "0" can still hit the server.
	HTTPAddr() string

	// Start launches the server. It must return only after the HTTP listener
	// is ready to accept connections (or after returning a non-nil error).
	Start(ctx context.Context) error

	// Stop shuts the server down gracefully.
	Stop(ctx context.Context) error
}

// AppFactory builds a ready-to-start AppRunner from the test config and
// the test logger.
//
// It MUST be non-nil for any test that calls requireApp(t) to run;
// otherwise the test is skipped with a clear message.
//
// Expected adapter pattern from developer_2 (placed in
// tests/integration/app_factory_real.go with a build tag if desired):
//
//	func init() {
//	    integration.AppFactory = func(cfg integration.AppConfig, logger log.Logger) (integration.AppRunner, func(), error) {
//	        bc := &confv1.Bootstrap{ ... translate cfg ... }
//	        app, cleanup, err := server.WireApp(bc.Server, bc.Data, bc.Auth, logger)
//	        if err != nil { return nil, nil, err }
//	        return kratosRunnerAdapter{app: app, addr: boundAddr}, cleanup, nil
//	    }
//	}
var AppFactory func(cfg AppConfig, logger log.Logger) (AppRunner, func(), error)
