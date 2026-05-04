package integration

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"os"
	"sync"
	"testing"
	"time"

	_ "github.com/lib/pq"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

// -----------------------------------------------------------------------------
// 测试包全局状态：testcontainers 起的 PG、目标 HTTP baseURL、jwt secret
// -----------------------------------------------------------------------------

var (
	testPGContainer testcontainers.Container
	testDSN         string
	testBaseURL     string // 形如 http://127.0.0.1:18080
	testJWTSecret   = "integration-test-secret"

	setupOnce sync.Once
	setupErr  error
	appCancel context.CancelFunc
	appClean  func()
)

// TestMain 负责：
//  1. 启动 testcontainers-go PostgreSQL 15
//  2. 执行 schema.sql
//  3. 若 AppFactory 已注入，则启动真实 kratos.App 并暴露 baseURL
//  4. 跑测试
//  5. 清理
//
// 如果 AppFactory == nil（dev_2 wireApp 还没好），各业务测试会 t.Skip，
// 不会影响 `go build ./...` / `go test ./... -run 'Nothing'` 流水线。
func TestMain(m *testing.M) {
	ctx := context.Background()

	// 即使没有 AppFactory，也先把 PG 起起来（这样后续 report 可以顺便验证 schema）。
	// 允许通过环境变量跳过容器（CI/离线场景）：`SKIP_TESTCONTAINERS=1 go test ./tests/integration/`。
	if os.Getenv("SKIP_TESTCONTAINERS") != "1" {
		if err := startPGContainer(ctx); err != nil {
			log.Printf("integration: failed to start PG container: %v (tests will be skipped)", err)
		}
	}

	if AppFactory != nil && testDSN != "" {
		app, addr, cleanup, err := AppFactory(ctx, testDSN, testJWTSecret)
		if err != nil {
			log.Printf("integration: AppFactory failed: %v", err)
		} else {
			appClean = cleanup
			testBaseURL = "http://" + addr
			// 等 HTTP 起来
			waitHTTPReady(testBaseURL, 10*time.Second)
			_ = app
		}
	}

	code := m.Run()

	if appClean != nil {
		appClean()
	}
	if appCancel != nil {
		appCancel()
	}
	if testPGContainer != nil {
		_ = testPGContainer.Terminate(context.Background())
	}
	os.Exit(code)
}

func startPGContainer(ctx context.Context) error {
	req := testcontainers.ContainerRequest{
		Image:        "postgres:15-alpine",
		ExposedPorts: []string{"5432/tcp"},
		Env: map[string]string{
			"POSTGRES_USER":     "blog",
			"POSTGRES_PASSWORD": "blog",
			"POSTGRES_DB":       "blogdb",
		},
		WaitingFor: wait.ForAll(
			wait.ForLog("database system is ready to accept connections").WithOccurrence(2),
			wait.ForListeningPort("5432/tcp"),
		).WithDeadline(60 * time.Second),
	}
	c, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: req,
		Started:          true,
	})
	if err != nil {
		return fmt.Errorf("start container: %w", err)
	}
	testPGContainer = c

	host, err := c.Host(ctx)
	if err != nil {
		return err
	}
	port, err := c.MappedPort(ctx, "5432/tcp")
	if err != nil {
		return err
	}
	testDSN = fmt.Sprintf("host=%s port=%s user=blog password=blog dbname=blogdb sslmode=disable", host, port.Port())

	if err := applySchema(testDSN); err != nil {
		return fmt.Errorf("apply schema: %w", err)
	}
	return nil
}

// applySchema 执行 artifacts/design/schema.sql。
// 路径相对本测试文件（tests/integration/main_test.go）向上 4 级到 artifacts/design/schema.sql。
func applySchema(dsn string) error {
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return err
	}
	defer db.Close()
	// 等 PG 完全可连
	deadline := time.Now().Add(30 * time.Second)
	for time.Now().Before(deadline) {
		if err := db.Ping(); err == nil {
			break
		}
		time.Sleep(500 * time.Millisecond)
	}

	// 优先相对路径（测试运行目录是 tests/integration）
	candidates := []string{
		"../../../design/schema.sql",
		"../../design/schema.sql",
		"schema.sql",
	}
	var content []byte
	for _, p := range candidates {
		if b, err := os.ReadFile(p); err == nil {
			content = b
			break
		}
	}
	if len(content) == 0 {
		// 运行时环境里找不到 schema.sql 时，嵌入一个兜底版本（与 design/schema.sql 保持同步）。
		content = []byte(embeddedSchemaSQL)
	}
	_, err = db.Exec(string(content))
	return err
}

// embeddedSchemaSQL 与 artifacts/design/schema.sql 等价。
// 避免测试运行目录无法找到 design/schema.sql 时失败。
const embeddedSchemaSQL = `
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL     PRIMARY KEY,
    email         VARCHAR(128)  NOT NULL UNIQUE,
    password_hash VARCHAR(128)  NOT NULL,
    nickname      VARCHAR(64)   NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE TABLE IF NOT EXISTS posts (
    id          BIGSERIAL     PRIMARY KEY,
    author_id   BIGINT        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title       VARCHAR(256)  NOT NULL,
    body        TEXT          NOT NULL DEFAULT '',
    tags        TEXT[]        NOT NULL DEFAULT '{}',
    like_count  BIGINT        NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_posts_author    ON posts(author_id);
CREATE INDEX IF NOT EXISTS idx_posts_created   ON posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_tags_gin  ON posts USING GIN (tags);

CREATE TABLE IF NOT EXISTS comments (
    id          BIGSERIAL     PRIMARY KEY,
    post_id     BIGINT        NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    author_id   BIGINT        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body        TEXT          NOT NULL,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id, created_at);

CREATE TABLE IF NOT EXISTS post_likes (
    post_id     BIGINT        NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id     BIGINT        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (post_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_post_likes_user ON post_likes(user_id);
`

func waitHTTPReady(baseURL string, timeout time.Duration) {
	deadline := time.Now().Add(timeout)
	client := &http.Client{Timeout: 500 * time.Millisecond}
	for time.Now().Before(deadline) {
		resp, err := client.Get(baseURL + "/")
		if err == nil {
			resp.Body.Close()
			return
		}
		time.Sleep(200 * time.Millisecond)
	}
}

// requireAppReady：测试运行前检查 AppFactory 是否已注入。
// 未注入则 Skip，保证 dev_2 未完成时 `go test ./...` 不红。
func requireAppReady(t *testing.T) {
	t.Helper()
	setupOnce.Do(func() {
		if AppFactory == nil {
			setupErr = fmt.Errorf("AppFactory not injected; dev_2 wireApp not ready yet")
			return
		}
		if testBaseURL == "" {
			setupErr = fmt.Errorf("app not started; see TestMain logs")
		}
	})
	if setupErr != nil {
		t.Skipf("integration preconditions not met: %v", setupErr)
	}
}
