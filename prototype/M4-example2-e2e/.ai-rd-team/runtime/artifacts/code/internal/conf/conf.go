package conf

import (
	"fmt"
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

// Bootstrap 根配置
type Bootstrap struct {
	Server *Server `yaml:"server"`
	Data   *Data   `yaml:"data"`
	Auth   *Auth   `yaml:"auth"`
}

// Server 网络层配置
type Server struct {
	HTTP HTTPServer `yaml:"http"`
	GRPC GRPCServer `yaml:"grpc"`
}

type HTTPServer struct {
	Network string        `yaml:"network"`
	Addr    string        `yaml:"addr"`
	Timeout time.Duration `yaml:"timeout"`
}

type GRPCServer struct {
	Network string        `yaml:"network"`
	Addr    string        `yaml:"addr"`
	Timeout time.Duration `yaml:"timeout"`
}

// Data 数据层配置
type Data struct {
	Database Database `yaml:"database"`
}

type Database struct {
	Driver string `yaml:"driver"` // postgres
	Source string `yaml:"source"` // DSN
}

// Auth 认证配置（字段名与 biz/data 层严格对齐）
type Auth struct {
	JWTSecret string        `yaml:"jwt_secret"`
	Expire    time.Duration `yaml:"expire"`
}

// LoadConfig 从 yaml 文件加载配置
func LoadConfig(path string) (*Bootstrap, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read config %s: %w", path, err)
	}
	bc := &Bootstrap{}
	if err := yaml.Unmarshal(raw, bc); err != nil {
		return nil, fmt.Errorf("parse config %s: %w", path, err)
	}
	applyDefaults(bc)
	return bc, nil
}

// LoadConfigFromBytes 从 yaml 字节加载（tester 可用）
func LoadConfigFromBytes(data []byte) (*Bootstrap, error) {
	bc := &Bootstrap{}
	if err := yaml.Unmarshal(data, bc); err != nil {
		return nil, fmt.Errorf("parse config: %w", err)
	}
	applyDefaults(bc)
	return bc, nil
}

func applyDefaults(bc *Bootstrap) {
	if bc.Server == nil {
		bc.Server = &Server{}
	}
	if bc.Server.HTTP.Network == "" {
		bc.Server.HTTP.Network = "tcp"
	}
	if bc.Server.HTTP.Addr == "" {
		bc.Server.HTTP.Addr = ":8000"
	}
	if bc.Server.HTTP.Timeout == 0 {
		bc.Server.HTTP.Timeout = 10 * time.Second
	}
	if bc.Server.GRPC.Network == "" {
		bc.Server.GRPC.Network = "tcp"
	}
	if bc.Server.GRPC.Addr == "" {
		bc.Server.GRPC.Addr = ":9000"
	}
	if bc.Server.GRPC.Timeout == 0 {
		bc.Server.GRPC.Timeout = 10 * time.Second
	}
	if bc.Auth == nil {
		bc.Auth = &Auth{}
	}
	if bc.Auth.JWTSecret == "" {
		bc.Auth.JWTSecret = "dev-secret-change-me"
	}
	if bc.Auth.Expire == 0 {
		bc.Auth.Expire = 24 * time.Hour
	}
	if bc.Data == nil {
		bc.Data = &Data{}
	}
	if bc.Data.Database.Driver == "" {
		bc.Data.Database.Driver = "postgres"
	}
}
