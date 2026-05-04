.PHONY: tidy build run test clean

GO ?= go
BIN ?= bin/server

tidy:
	$(GO) mod tidy

build: tidy
	mkdir -p bin
	$(GO) build -o $(BIN) ./cmd/server

run:
	$(GO) run ./cmd/server -conf ./configs/config.yaml

test:
	$(GO) test ./...

clean:
	rm -rf bin
