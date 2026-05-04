// Code hand-written by developer_2 (equivalent to protoc output of internal/conf/conf.proto).
// This is a minimal Go struct surface (no protoreflect); consumed via direct yaml scan.
package conf

import "time"

// Bootstrap is the top-level config.
type Bootstrap struct {
	Server *Server `yaml:"server" json:"server"`
	Data   *Data   `yaml:"data"   json:"data"`
	Auth   *Auth   `yaml:"auth"   json:"auth"`
}

func (m *Bootstrap) GetServer() *Server { if m == nil { return nil }; return m.Server }
func (m *Bootstrap) GetData() *Data     { if m == nil { return nil }; return m.Data }
func (m *Bootstrap) GetAuth() *Auth     { if m == nil { return nil }; return m.Auth }

// Server groups http/grpc listen config.
type Server struct {
	Http *Server_HTTP `yaml:"http" json:"http"`
	Grpc *Server_GRPC `yaml:"grpc" json:"grpc"`
}

func (m *Server) GetHttp() *Server_HTTP { if m == nil { return nil }; return m.Http }
func (m *Server) GetGrpc() *Server_GRPC { if m == nil { return nil }; return m.Grpc }

type Server_HTTP struct {
	Addr    string        `yaml:"addr"    json:"addr"`
	Timeout time.Duration `yaml:"timeout" json:"timeout"`
}

func (m *Server_HTTP) GetAddr() string           { if m == nil { return "" }; return m.Addr }
func (m *Server_HTTP) GetTimeout() time.Duration { if m == nil { return 0 }; return m.Timeout }

type Server_GRPC struct {
	Addr    string        `yaml:"addr"    json:"addr"`
	Timeout time.Duration `yaml:"timeout" json:"timeout"`
}

func (m *Server_GRPC) GetAddr() string           { if m == nil { return "" }; return m.Addr }
func (m *Server_GRPC) GetTimeout() time.Duration { if m == nil { return 0 }; return m.Timeout }

// Data groups database and log config.
type Data struct {
	Database *Data_Database `yaml:"database"  json:"database"`
	LogLevel string         `yaml:"log_level" json:"log_level"`
}

func (m *Data) GetDatabase() *Data_Database { if m == nil { return nil }; return m.Database }
func (m *Data) GetLogLevel() string         { if m == nil { return "" }; return m.LogLevel }

type Data_Database struct {
	Driver string `yaml:"driver" json:"driver"`
	Source string `yaml:"source" json:"source"`
}

func (m *Data_Database) GetDriver() string { if m == nil { return "" }; return m.Driver }
func (m *Data_Database) GetSource() string { if m == nil { return "" }; return m.Source }

// Auth groups JWT config.
type Auth struct {
	JwtSecret string        `yaml:"jwt_secret" json:"jwt_secret"`
	AccessTtl time.Duration `yaml:"access_ttl" json:"access_ttl"`
}

func (m *Auth) GetJwtSecret() string        { if m == nil { return "" }; return m.JwtSecret }
func (m *Auth) GetAccessTtl() time.Duration { if m == nil { return 0 }; return m.AccessTtl }
