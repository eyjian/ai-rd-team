.PHONY: api wire build run clean tidy vet test

# module 根
MODULE := blog
# 二进制产物
BIN    := bin/blog

# ---------------------------------------------------------------------------
# make api —— 生成 api/blog/v1/*.pb.go *_grpc.pb.go *_http.pb.go
#
# 标准做法：配 buf.gen.yaml，跑 buf generate。
# 本原型环境未安装 protoc / buf，`api/blog/v1/*.pb.go` 已手写并与
# protoc-gen-go / protoc-gen-go-grpc / protoc-gen-go-http 产物接口等价，
# 可直接编译；安装 buf 后可改用本地生成覆盖：
#
#   buf generate --template buf.gen.yaml api
# ---------------------------------------------------------------------------
api:
	@echo "[make api] proto files kept at api/blog/v1, pb.go already provided"
	@echo "           install buf + protoc-gen-go-http to regenerate:"
	@echo "           buf generate --template buf.gen.yaml api"

# make wire —— 生成 cmd/blog/wire_gen.go
wire:
	@echo "[make wire] running google/wire on ./cmd/blog"
	@command -v wire >/dev/null 2>&1 && wire ./cmd/blog || echo "wire not installed; wire_gen.go is pre-generated"

# make build —— 编译
build:
	@mkdir -p bin
	go build -o $(BIN) ./cmd/blog

# make run —— 本地启动
run: build
	./$(BIN) -conf configs/config.yaml

# make tidy —— 同步依赖
tidy:
	go mod tidy

# make vet —— 静态检查
vet:
	go vet ./...

# make test —— 跑测试
test:
	go test ./... -race -cover

clean:
	rm -rf bin
