# BlogAPI 预期产出

## 成员产出文件

```
.ai-rd-team/runtime/artifacts/
├── code/
│   ├── go.mod
│   ├── Makefile
│   ├── api/blog/v1/
│   │   ├── user.proto
│   │   ├── post.proto
│   │   ├── comment.proto
│   │   └── (生成的 *.pb.go *_grpc.pb.go *_http.pb.go)
│   ├── cmd/blog/
│   │   ├── main.go
│   │   └── wire.go / wire_gen.go
│   ├── configs/config.yaml
│   ├── internal/
│   │   ├── biz/{user.go, post.go, comment.go, biz.go}
│   │   ├── data/{user.go, post.go, comment.go, data.go}
│   │   ├── service/{user.go, post.go, comment.go, service.go}
│   │   ├── server/{grpc.go, http.go, server.go}
│   │   └── conf/{conf.proto, conf.pb.go}
│   └── tests/
│       ├── integration/api_test.go
│       └── biz/
├── docs/
│   ├── api.md                      # 接口文档
│   └── db-schema.md                # 数据库说明
└── reports/
    ├── report-architect.md
    ├── report-developer.md         # 如果有多个 developer，会各自写
    └── report-tester.md
```

## 验收步骤

```bash
cd .ai-rd-team/runtime/artifacts/code

# 1. 构建
go build ./...

# 2. 跑集成测试（需要 Docker）
go test ./tests/integration/... -v

# 3. 启动（需要 PostgreSQL）
createdb blog_dev
./blog -conf=configs/config.yaml &

# 4. curl 走流程
curl -X POST http://localhost:8000/v1/users \
  -d '{"email":"a@b.com","password":"xxxxxxxx","nickname":"alice"}'

curl -X POST http://localhost:8000/v1/auth/login \
  -d '{"email":"a@b.com","password":"xxxxxxxx"}'
# → {"token":"eyJhbGc..."}

TOKEN="eyJhbGc..."
curl -H "Authorization: Bearer $TOKEN" \
  -X POST http://localhost:8000/v1/posts \
  -d '{"title":"Hello","body_markdown":"# World","tags":["golang"]}'
```

## 成本预期

- RP 消耗：~250-400（Standard 档预算 400）
- 成员数：4（architect + developer × 2 + tester）
- 消息数：10-20
- 运行时长：20-30 分钟

## 关键观察点（打开 Web 面板看）

- architect 先产出 proto + 数据库 schema
- 两个 developer 并行实现（biz+data vs service+server），通过 send_message 协调 wire 装配
- tester 在 developer 进入 working 后才开始写集成测试
- 成员状态：spawning → working → waiting（等协作）→ done
