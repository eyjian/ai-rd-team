# 测试覆盖矩阵（tester 预产出骨架）

> 作者：赵（tester）
> 状态：骨架已就位，等待 developer_2 的 wireApp 接入后启用
> 测试位置：`artifacts/code/tests/integration/`

## 文件结构

```
tests/integration/
├── main_test.go          # TestMain：testcontainers PG + schema.sql + app 启动
├── app_stub.go           # 占位的 startApp；dev_2 接入后替换（详见 TODO）
├── helpers_test.go       # apiCall / createTestUser / assertStatus / assertReason
├── paths_test.go         # pathPost / pathComments / pathLike
├── user_test.go          # 用户（9 个子用例）
├── post_test.go          # 文章（5 个子用例）
├── comment_like_test.go  # 评论 + 点赞（7 个子用例）
└── e2e_flow_test.go      # 端到端完整流程（8 个子测试，覆盖幂等）
```

## 接入点（给 developer_2）

`app_stub.go` 暴露一个函数变量：

```go
var startApp = func(dsn string) (baseURL string, shutdown func(), ready bool, err error)
```

Dev_2 完成 `cmd/blog/wireApp` 后，请**不要改动**任何 `*_test.go`；只需：

1. 把 `app_stub.go` 替换为 `app_wired.go`，实现 `startApp` 为：
   - 构造 `conf.Bootstrap`：
     - `server.http.addr = 127.0.0.1:0`（随机端口）
     - `data.database.source = dsn`（从参数注入）
     - `auth.jwt_secret = "test-secret"`，`ttl = 604800`
   - 调用 `wireApp(bootstrap.Server, bootstrap.Data, bootstrap.Auth, logger)`
   - 后台 `go app.Run()`；轮询 HTTP 端口直到可 `TCP dial`
   - 返回 `baseURL = "http://127.0.0.1:PORT"`，`shutdown = func() { app.Stop() }`，`ready = true`
2. 如需从 `HTTPServer` 读取监听端口，推荐在 `server/http.go` 暴露一个 `Endpoint()`，或直接让 `wireApp` 再返回一个 `*http.Server` 以便测试取 Addr。

## 覆盖矩阵

### 端点级覆盖（12 端点 × 正常/401/403/404）

| HTTP | 路径 | 正常 200 | 401 | 403 | 404 | 409 |
|---|---|---|---|---|---|---|
| POST | /v1/users | Register_OK, E2E | — | — | — | Register_Duplicate_409 |
| POST | /v1/auth/login | Login_OK, E2E | Login_WrongPassword, Login_UnknownEmail | — | — | — |
| GET | /v1/users/me | GetMe_OK | GetMe_NoToken, GetMe_InvalidToken | — | — | — |
| POST | /v1/posts | E2E | Create_NoToken_401 | — | — | — |
| GET | /v1/posts/{id} | E2E.GetPost | — | — | Get_NotFound_404, E2E.DeleteByAuthor_Then404 | — |
| GET | /v1/posts | E2E.ListByTag, List_Pagination_OK | — | — | — | — |
| PUT | /v1/posts/{id} | E2E.UpdateByAuthor | （覆盖于 Create_NoToken 同类 middleware） | E2E.UpdateOthers_Forbidden | Update_NotFound_404 | — |
| DELETE | /v1/posts/{id} | E2E.DeleteByAuthor | — | Delete_NotOwned_403 | （通过 Then404 间接） | — |
| POST | /v1/posts/{id}/comments | E2E.CreateComment, List_OK | Create_NoToken_401 | — | Create_PostNotFound_404 | — |
| GET | /v1/posts/{id}/comments | E2E.ListComments, List_OK | — | — | — | — |
| POST | /v1/posts/{id}/like | E2E.LikeIdempotent | Like_NoToken_401 | — | Like_PostNotFound_404 | — |
| DELETE | /v1/posts/{id}/like | E2E.LikeIdempotent, Unlike_WhenNotLiked_Idempotent | Unlike_NoToken_401 | — | — | — |

### 业务语义额外覆盖

- **点赞幂等**：E2E.LikeIdempotent（重复 POST /like 仍然 likes_count=1）
- **取消幂等**：Unlike_WhenNotLiked_Idempotent（从未点赞也返回 0，不报错）
- **删除后 404**：E2E.DeleteByAuthor_Then404
- **参数校验 400**：Register_InvalidEmail_400（验证 validate middleware 生效）
- **tag 过滤**：E2E.ListByTag

## 执行方式

```bash
cd artifacts/code
# 骨架状态下：TestMain 会启动 PG 容器，跑 schema.sql，
# 因为 app_stub 的 ready=false，所有子测试 t.Skip，不会误报。
go test ./tests/integration/... -v

# dev_2 接入 wireApp 后：ready=true，全量跑
go test ./tests/integration/... -v -race -cover
```

## 待 dev 产出后再做的事

- [ ] dev_2 接入 `wireApp`；本目录下测试即可直接跑
- [ ] 如果 biz 单测覆盖不足 70%，我补**错误路径**（bcrypt mismatch、FindByEmail not-found、Post not-owned 等）
- [ ] 最终跑 `-cover` 并更新本文档底部的"实际覆盖率"小节

## 实际覆盖率（等跑完补充）

- core path coverage: TBD（目标 ≥ 70%）
- 总用例数：骨架阶段 29 个子用例（9 user + 5 post + 7 comment/like + 8 e2e），按端点 x 场景去重后 26 个独立断言场景
