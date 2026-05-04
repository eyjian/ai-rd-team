package main

import (
	"flag"
	"fmt"
	"os"
	"time"

	"blog/internal/conf"

	"github.com/go-kratos/kratos/v2"
	"github.com/go-kratos/kratos/v2/log"
	"github.com/go-kratos/kratos/v2/transport/grpc"
	"github.com/go-kratos/kratos/v2/transport/http"
	"gopkg.in/yaml.v3"
)

var (
	// Name is the app name.
	Name = "blog"
	// Version is the app version.
	Version = "0.1.0"

	flagConf string
)

func init() {
	flag.StringVar(&flagConf, "conf", "configs/config.yaml", "config path, eg: -conf configs/config.yaml")
}

// newApp builds the kratos.App with the given transports.
func newApp(logger log.Logger, hs *http.Server, gs *grpc.Server) *kratos.App {
	return kratos.New(
		kratos.Name(Name),
		kratos.Version(Version),
		kratos.Logger(logger),
		kratos.Server(hs, gs),
	)
}

// loadConfig reads yaml from disk and unmarshals into *conf.Bootstrap,
// converting string durations to time.Duration.
func loadConfig(path string) (*conf.Bootstrap, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	type httpCfg struct {
		Addr    string `yaml:"addr"`
		Timeout string `yaml:"timeout"`
	}
	type grpcCfg struct {
		Addr    string `yaml:"addr"`
		Timeout string `yaml:"timeout"`
	}
	type serverCfg struct {
		HTTP *httpCfg `yaml:"http"`
		GRPC *grpcCfg `yaml:"grpc"`
	}
	type dbCfg struct {
		Driver string `yaml:"driver"`
		Source string `yaml:"source"`
	}
	type dataCfg struct {
		Database *dbCfg `yaml:"database"`
		LogLevel string `yaml:"log_level"`
	}
	type authCfg struct {
		JWTSecret string `yaml:"jwt_secret"`
		AccessTTL string `yaml:"access_ttl"`
	}
	type bootstrapRaw struct {
		Server *serverCfg `yaml:"server"`
		Data   *dataCfg   `yaml:"data"`
		Auth   *authCfg   `yaml:"auth"`
	}
	var br bootstrapRaw
	if err := yaml.Unmarshal(raw, &br); err != nil {
		return nil, err
	}
	parse := func(s string, def time.Duration) time.Duration {
		if s == "" {
			return def
		}
		d, err := time.ParseDuration(s)
		if err != nil {
			return def
		}
		return d
	}

	bs := &conf.Bootstrap{}
	if br.Server != nil {
		bs.Server = &conf.Server{}
		if br.Server.HTTP != nil {
			bs.Server.Http = &conf.Server_HTTP{Addr: br.Server.HTTP.Addr, Timeout: parse(br.Server.HTTP.Timeout, 10*time.Second)}
		}
		if br.Server.GRPC != nil {
			bs.Server.Grpc = &conf.Server_GRPC{Addr: br.Server.GRPC.Addr, Timeout: parse(br.Server.GRPC.Timeout, 10*time.Second)}
		}
	}
	if br.Data != nil {
		bs.Data = &conf.Data{LogLevel: br.Data.LogLevel}
		if br.Data.Database != nil {
			bs.Data.Database = &conf.Data_Database{Driver: br.Data.Database.Driver, Source: br.Data.Database.Source}
		}
	}
	if br.Auth != nil {
		bs.Auth = &conf.Auth{JwtSecret: br.Auth.JWTSecret, AccessTtl: parse(br.Auth.AccessTTL, 168*time.Hour)}
	}
	return bs, nil
}

func main() {
	flag.Parse()

	logger := log.With(log.NewStdLogger(os.Stdout),
		"ts", log.DefaultTimestamp,
		"caller", log.DefaultCaller,
		"service.name", Name,
		"service.version", Version,
	)
	helper := log.NewHelper(logger)

	bs, err := loadConfig(flagConf)
	if err != nil {
		helper.Errorf("load config failed: %v", err)
		os.Exit(1)
	}

	app, cleanup, err := wireApp(bs, logger)
	if err != nil {
		helper.Errorf("wire app failed: %v", err)
		os.Exit(1)
	}
	defer cleanup()

	if err := app.Run(); err != nil {
		helper.Errorf("app run failed: %v", err)
		os.Exit(1)
	}
	fmt.Fprintln(os.Stdout, "server shutdown")
}
