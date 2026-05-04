package server

import "github.com/google/wire"

// ProviderSet is used by top-level wire to construct http/grpc servers.
var ProviderSet = wire.NewSet(NewHTTPServer, NewGRPCServer)
