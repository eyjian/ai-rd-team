# BlogAPI 预期产出（M7 新布局）

## 成员产出文件

Go + Kratos 项目；架构师声明 `data-project-layout.yaml` 用 `base=go` + `alongside` 测试；交付物直接落项目根：

```
<workspace>/                              # 项目根
├── go.mod
├── Makefile
├── api/blog/v1/
│   ├── user.proto
│   ├── post.proto
│   ├── comment.proto
│   └── (生成的 *.pb.go *_grpc.pb.go *_http.pb.go)
├── cmd/blog/
│   ├── main.go
│   └── wire.go / wire_gen.go
├── configs/config.yaml
├── internal/
│   ├── biz/{user.go, post.go, comment.go, biz.go,
│   │        user_test.go, post_test.go, ...}  # alongside: 测试与代码同目录
│   ├── data/{user.go, post.go, comment.go, data.go}
│   ├── service/{user.go, post.go, comment.go, service.go}
│   ├── server/{grpc.go, http.go, server.go}
│   └── conf/{conf.proto, conf.pb.go}
├── tests/
│   └── integration/api_test.go          # 跨模块集成测试仍在 tests/
├── docs/
│   ├── design/
│   │   ├── ARCHITECTURE.md              # 架构师总图
│   │   ├── api.md                       # 接口文档
│   │   └── db-schema.md                 # 数据库说明
│   └── delivery/
│       └── checklist.md                 # PM 维护的交付 checklist
└── .ai-rd-team/
    └── runtime/
        ├── manifest.yaml                # 权威索引
        └── reports/                     # 阶段报告（过程）
            ├── report-architect.md
            ├── report-developer_1.md
            ├── report-developer_2.md
            ├── report-tester.md
            ├── report-run-summary.md    # PM 总览
            └── data-project-layout.yaml # 架构师声明的布局
```

## 验收步骤

```bash
cd <workspace>                          # 代码就在项目根

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

- architect 先产出 `docs/design/ARCHITECTURE.md` + `docs/design/data-interfaces.yaml`（proto 对应）
- 两个 developer 并行实现（biz+data vs service+server），通过 send_message 协调 wire 装配；代码**直接落项目根**
- tester 在 developer 进入 working 后才开始写集成测试
- 成员状态：spawning → working → waiting（等协作）→ done
- `manifest.yaml` 里每条产出都带 `category: delivery | process`，方便 PM 在 checklist 里引用
