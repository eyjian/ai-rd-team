package server

import "github.com/google/wire"

// ProviderSet server 层 wire set
var ProviderSet = wire.NewSet(NewHTTPServer, NewGRPCServer)
