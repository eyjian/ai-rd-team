// Package integration provides end-to-end tests for the Blog API.
//
// TestMain 负责：
//  1. 启动 postgres:15-alpine testcontainer；
//  2. 执行 configs/schema.sql 建表；
//  3. 调用 startApp(dsn) 启动 kratos App（由 dev_2 的 wireApp 提供）；
//  4. 将 baseURL 暴露给各子测试；
//  5. 测试结束后优雅关闭 App 和容器。
//
// 在 dev_2 产出 wireApp 之前，startApp 返回占位值，
// 用例通过 skipIfAppNotReady 自动跳过。
package integration

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"runtime"
	"testing"
	"time"

	_ "github.com/lib/pq"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/postgres"
	"github.com/testcontainers/testcontainers-go/wait"
)

// testEnv 暴露给所有子测试共享的运行时上下文。
var testEnv struct {
	dsn      string // 形如 postgres://user:pass@host:port/db?sslmode=disable
	baseURL  string // 形如 http://127.0.0.1:PORT
	appReady bool   // dev_2 的 wireApp 接入后设为 true
	shutdown func() // 关闭 app 的钩子
}

// TestMain 是整个 integration 包的入口。
func TestMain(m *testing.M) {
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()

	// 1. 启动 PostgreSQL 容器
	pgC, dsn, err := startPostgres(ctx)
	if err != nil {
		log.Fatalf("start postgres container failed: %v", err)
	}
	testEnv.dsn = dsn

	// 2. 执行 schema.sql
	if err := applySchema(ctx, dsn); err != nil {
		_ = pgC.Terminate(ctx)
		log.Fatalf("apply schema failed: %v", err)
	}

	// 3. 启动 app（由 dev_2 的 wireApp 接入，当前为占位）
	baseURL, shutdown, ready, err := startApp(dsn)
	if err != nil {
		_ = pgC.Terminate(ctx)
		log.Fatalf("start app failed: %v", err)
	}
	testEnv.baseURL = baseURL
	testEnv.shutdown = shutdown
	testEnv.appReady = ready

	if ready {
		log.Printf("integration env ready: dsn=%s baseURL=%s", dsn, baseURL)
	} else {
		log.Printf("integration env partial: dsn=%s (app NOT started, waiting for dev_2 wireApp)", dsn)
	}

	// 4. 执行测试
	code := m.Run()

	// 5. 清理
	if shutdown != nil {
		shutdown()
	}
	_ = pgC.Terminate(context.Background())
	os.Exit(code)
}

// startPostgres 启动 postgres:15-alpine 容器并返回可连接的 DSN。
func startPostgres(ctx context.Context) (testcontainers.Container, string, error) {
	pgC, err := postgres.Run(ctx,
		"postgres:15-alpine",
		postgres.WithDatabase("blog_test"),
		postgres.WithUsername("postgres"),
		postgres.WithPassword("postgres"),
		testcontainers.WithWaitStrategy(
			wait.ForLog("database system is ready to accept connections").
				WithOccurrence(2).
				WithStartupTimeout(60*time.Second),
		),
	)
	if err != nil {
		return nil, "", fmt.Errorf("run postgres: %w", err)
	}

	dsn, err := pgC.ConnectionString(ctx, "sslmode=disable")
	if err != nil {
		_ = pgC.Terminate(ctx)
		return nil, "", fmt.Errorf("connection string: %w", err)
	}
	return pgC, dsn, nil
}

// applySchema 把 configs/schema.sql 的 DDL 执行到容器数据库中。
func applySchema(ctx context.Context, dsn string) error {
	schemaPath, err := findSchemaSQL()
	if err != nil {
		return err
	}
	sqlBytes, err := os.ReadFile(schemaPath)
	if err != nil {
		return fmt.Errorf("read schema.sql: %w", err)
	}

	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return fmt.Errorf("open db: %w", err)
	}
	defer db.Close()

	if err := db.PingContext(ctx); err != nil {
		return fmt.Errorf("ping db: %w", err)
	}
	if _, err := db.ExecContext(ctx, string(sqlBytes)); err != nil {
		return fmt.Errorf("exec schema.sql: %w", err)
	}
	return nil
}

// findSchemaSQL 通过 runtime.Caller 定位到 ../../configs/schema.sql。
func findSchemaSQL() (string, error) {
	_, thisFile, _, ok := runtime.Caller(0)
	if !ok {
		return "", fmt.Errorf("runtime.Caller failed")
	}
	// tests/integration/main_test.go → ../../configs/schema.sql
	root := filepath.Dir(filepath.Dir(filepath.Dir(thisFile)))
	p := filepath.Join(root, "configs", "schema.sql")
	if _, err := os.Stat(p); err != nil {
		return "", fmt.Errorf("schema.sql not found at %s: %w", p, err)
	}
	return p, nil
}

// skipIfAppNotReady 在 dev_2 的 wireApp 尚未接入时跳过用例。
// 当 startApp 返回 ready=true 之后，所有测试会自动启用。
func skipIfAppNotReady(t *testing.T) {
	t.Helper()
	if !testEnv.appReady {
		t.Skip("app not started yet (waiting for developer_2 wireApp); DB container is up so schema smoke tests still run")
	}
}
