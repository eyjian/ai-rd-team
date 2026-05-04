package integration

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	_ "github.com/lib/pq"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/modules/postgres"
	"github.com/testcontainers/testcontainers-go/wait"
)

// testEnv bundles everything the suite needs to talk to a single
// disposable Postgres + running BlogAPI instance.
type testEnv struct {
	pgContainer *postgres.PostgresContainer
	pgDSN       string
	httpBaseURL string

	appCleanup func()
	appStopCtx context.Context

	once sync.Once
}

var (
	// sharedEnv is populated by TestMain and reused by every test in the
	// integration package. Integration tests are not run in parallel with
	// each other to keep Postgres state predictable; table-driven cases
	// inside a single Test* function are fine to run sequentially.
	sharedEnv *testEnv
)

// TestMain boots a Postgres testcontainer, applies schema.sql, hands the
// DSN to the AppFactory (if registered) and finally runs the package
// tests. It tears everything down at the end regardless of outcome.
//
// Keeping setup/teardown in TestMain (as opposed to per-test fixtures)
// matches the BlogAPI spec: the wire graph is expensive and the schema
// is fully isolated by truncation between tests.
func TestMain(m *testing.M) {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	// Allow the suite to be skipped entirely when Docker is unavailable,
	// e.g. in minimal CI jobs that only run `go test -run=TestUnit`.
	if os.Getenv("BLOG_SKIP_INTEGRATION") == "1" {
		log.Println("[integration] BLOG_SKIP_INTEGRATION=1, skipping")
		os.Exit(0)
	}

	env, err := startEnv(ctx)
	if err != nil {
		// Do NOT fail the suite if Docker is missing — that would block
		// `go test ./...` on dev laptops. Emit a clear message and skip.
		log.Printf("[integration] env not available, skipping: %v", err)
		os.Exit(0)
	}
	sharedEnv = env

	code := m.Run()

	stopCtx, stopCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer stopCancel()
	env.stop(stopCtx)

	os.Exit(code)
}

// startEnv launches Postgres, applies schema and (if AppFactory is wired)
// starts the BlogAPI. It returns as soon as the HTTP port is accepting
// connections so tests can hit the server immediately.
func startEnv(ctx context.Context) (*testEnv, error) {
	pgContainer, err := postgres.RunContainer(ctx,
		testcontainers.WithImage("postgres:15-alpine"),
		postgres.WithDatabase("blog"),
		postgres.WithUsername("blog"),
		postgres.WithPassword("blog"),
		testcontainers.WithWaitStrategy(
			wait.ForLog("database system is ready to accept connections").
				WithOccurrence(2).
				WithStartupTimeout(60*time.Second),
		),
	)
	if err != nil {
		return nil, fmt.Errorf("start postgres container: %w", err)
	}

	dsn, err := pgContainer.ConnectionString(ctx, "sslmode=disable")
	if err != nil {
		_ = pgContainer.Terminate(ctx)
		return nil, fmt.Errorf("get pg connection string: %w", err)
	}

	if err := applySchema(ctx, dsn); err != nil {
		_ = pgContainer.Terminate(ctx)
		return nil, fmt.Errorf("apply schema.sql: %w", err)
	}

	env := &testEnv{
		pgContainer: pgContainer,
		pgDSN:       dsn,
	}

	// If developer_2's wireApp isn't registered yet we still want the
	// suite to boot (tests relying on the HTTP server will simply skip).
	if AppFactory != nil {
		httpAddr, cleanup, err := startApp(ctx, dsn)
		if err != nil {
			_ = pgContainer.Terminate(ctx)
			return nil, fmt.Errorf("start app: %w", err)
		}
		env.httpBaseURL = "http://" + httpAddr
		env.appCleanup = cleanup
	}

	return env, nil
}

// applySchema reads configs/schema.sql relative to the repo module root
// and executes it against the freshly-started Postgres instance.
//
// The path is resolved by walking up from the test binary's working dir
// until a go.mod with `module blog` is found, to keep the code robust to
// `go test ./tests/integration/...` vs `go test ./...`.
func applySchema(ctx context.Context, dsn string) error {
	schemaPath, err := findSchemaFile()
	if err != nil {
		return err
	}
	b, err := os.ReadFile(schemaPath)
	if err != nil {
		return fmt.Errorf("read %s: %w", schemaPath, err)
	}

	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return fmt.Errorf("open db: %w", err)
	}
	defer db.Close()

	// Give Postgres a few extra ticks — the container log signal is
	// optimistic and the socket may still be hot-reloading config.
	pingCtx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	for {
		if err := db.PingContext(pingCtx); err == nil {
			break
		}
		select {
		case <-pingCtx.Done():
			return fmt.Errorf("pg not ready: %w", pingCtx.Err())
		case <-time.After(300 * time.Millisecond):
		}
	}

	if _, err := db.ExecContext(ctx, string(b)); err != nil {
		return fmt.Errorf("exec schema: %w", err)
	}
	return nil
}

// findSchemaFile walks up the directory tree looking for configs/schema.sql,
// which lives at the module root (next to go.mod).
func findSchemaFile() (string, error) {
	cwd, err := os.Getwd()
	if err != nil {
		return "", err
	}
	dir := cwd
	for i := 0; i < 8; i++ {
		candidate := filepath.Join(dir, "configs", "schema.sql")
		if st, err := os.Stat(candidate); err == nil && !st.IsDir() {
			return candidate, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return "", fmt.Errorf("configs/schema.sql not found starting at %s", cwd)
}

func (e *testEnv) stop(ctx context.Context) {
	e.once.Do(func() {
		if e.appCleanup != nil {
			e.appCleanup()
		}
		if e.pgContainer != nil {
			_ = e.pgContainer.Terminate(ctx)
		}
	})
}
