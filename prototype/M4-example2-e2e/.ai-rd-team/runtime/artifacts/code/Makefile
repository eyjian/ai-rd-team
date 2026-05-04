.PHONY: build run test tidy vet clean

build:
	go build -o bin/server ./cmd/server

run:
	go run ./cmd/server -conf configs/config.yaml

test:
	go test ./... -race -cover

tidy:
	go mod tidy

vet:
	go vet ./...

clean:
	rm -rf bin/
