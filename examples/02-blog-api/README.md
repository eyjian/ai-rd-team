# 示例 02：BlogAPI（Go + Kratos 博客后端）

**档位**：Standard  
**技术栈**：Go + Kratos + GORM + PostgreSQL  
**预计 RP**：300-400  
**预计时长**：20-30 分钟  

## 目标产出

一个博客系统的后端 REST API，支持：

- 用户注册 / 登录（JWT）
- 发布文章（Markdown body）
- 评论、点赞
- 分页查询文章列表 / 单篇详情

## 团队配置

Standard 档默认：**architect × 1 + developer × 2 + tester × 1**

- **architect**：设计 proto / 数据库 schema / 分层结构
- **developer_1**：实现 biz + data 层
- **developer_2**：实现 service + server 装配
- **tester**：集成测试（testcontainers-go 跑 PG）

## 预期文件树

```
<workspace>/                              # 项目根（代码直接落这里）
├── api/blog/v1/
│   ├── blog.proto                  # 接口定义
│   ├── blog.pb.go                  # 生成
│   ├── blog_grpc.pb.go
│   └── blog_http.pb.go
├── cmd/blog/
│   ├── main.go
│   ├── wire.go
│   └── wire_gen.go
├── configs/
│   └── config.yaml
├── internal/
│   ├── biz/                        # 业务逻辑
│   │   ├── user.go / post.go / comment.go
│   │   └── biz.go (wire set)
│   ├── data/                       # 数据访问
│   │   ├── user.go / post.go / comment.go
│   │   └── data.go (wire set)
│   ├── service/                    # 协议层
│   │   ├── user.go / post.go
│   │   └── service.go (wire set)
│   ├── server/
│   │   ├── grpc.go / http.go
│   │   └── server.go (wire set)
│   └── conf/
│       ├── conf.proto
│       └── conf.pb.go
├── Makefile
└── go.mod
```

## 如何运行

```bash
cp -r examples/02-blog-api ~/demo-blog-api
cd ~/demo-blog-api

ai-rd-team serve --port 8765 &
ai-rd-team run "$(cat REQUIREMENT.md)"
```

## Skills 配置

见 `config.advanced.yaml`：

- architect：`go-kratos-basics` + `code-review-checklist`
- developer：`go-kratos-basics`
- reviewer：`go-kratos-basics` + `code-review-checklist`
- tester：`go-kratos-basics`

## 验收标准

1. `cd <workspace> && go build ./...` 通过（代码就在项目根）
2. `go test ./... -race` 通过
3. proto 文件能 `kratos proto client` 重新生成
4. 启动后 curl 测试能走通注册 / 登录 / 发帖流程
