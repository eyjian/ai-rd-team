# Tester 阶段报告（赵小测）

> Owner: tester（赵小测）
> 范围: `tests/integration/`
> 日期: 2026-05-04

---

## 1. 交付清单

工作目录：
`prototype/M4-example2-e2e/.ai-rd-team/runtime/artifacts/code/tests/integration/`

| 文件 | 行数 | 作用 |
|------|------|------|
| `app_stub.go`       | 80  | 和 developer_2 装配层之间的解耦钩子。声明 `AppConfig`（纯 Go 类型）、`AppRunner` 接口、`AppFactory` 包级变量。 |
| `main_test.go`      | 160 | `TestMain`：用 testcontainers-go/postgres 起 `postgres:15-alpine`，执行 `configs/schema.sql`，条件性调用 `AppFactory` 启动 BlogAPI。Docker 不可用时整体 skip，不把 CI 卡住。 |
| `helpers_test.go`   | 250 | `setupTestDB` / `apiClient.apiCall` / `createTestUser` / `uniqueEmail` / `assertErrorReason` 等 table-driven 测试必备工具。 |
| `user_test.go`      | 140 | 注册、登录、鉴权中间件（8 个 subtest）。 |
| `post_test.go`      | 240 | 文章 CRUD + 作者鉴权 + 分页 + tag 过滤（14 个 subtest）。 |
| `comment_test.go`   | 250 | 评论 CRUD + 点赞幂等 + cascade（14 个 subtest）。 |
| `e2e_flow_test.go`  | 140 | 全流程：注册→登录→发帖→GET→list(tag)→like×2→comment→list→delete→验证 404 + cascade。 |

总计约 **1260 行**，**7 个文件**，**47+ subtest**。

---

## 2. 关键决策

### 2.1 通过 `AppFactory` 钩子解耦装配层
`tests/integration/` 不直接 import `cmd/server`、也不直接 import `internal/conf`。
- 好处：tests 包独立编译、架构师/装配层的改动不会反复触发 tests 重编译。
- 代价：developer_2 需要写一个小 `init()` adapter 把 `*kratos.App` 适配成 `AppRunner`。

`AppConfig` 用纯 Go 类型（`time.Duration` / `string`），不暴露 `google.protobuf.Duration` 这类协议细节。

### 2.2 testcontainers-go 只启一次 PG，按 test 截断表
- 在 `TestMain` 里启容器 + 建 schema 一次。
- 每个 `Test*` 函数内用 `setupTestDB` 做 `TRUNCATE post_likes, comments, posts, users RESTART IDENTITY CASCADE`。
- 好处：容器 cold start ≈ 10s，但每个 test ~1ms 的 TRUNCATE 就能回到干净状态。

### 2.3 端口用 `127.0.0.1:0`
避免并行测试或本地开发服务端口冲突。`AppRunner.HTTPAddr()` 必须返回实际绑定的端口（见 developer_2 接入说明）。

### 2.4 Docker 不可用时静默 skip
`TestMain` 里 `startEnv` 返 err 时 `os.Exit(0)` 而非 `os.Exit(1)`。这样 dev 笔记本 / 轻量 CI 跑 `go test ./...` 不会被 testcontainers 卡住。

### 2.5 错误断言统一用 kratos errors 的 `reason` 字段
遵循 architect 在 `biz-contracts.md §4` 的约定：

```go
func assertErrorReason(t *testing.T, resp *apiResponse, want string)
```

只断言 `reason`，不断言 `message`（message 是人读文案，不稳定）。

### 2.6 未写 biz 层单测
架构师在消息里也建议我写 `internal/biz/*_test.go` 的 table-test。但 team-lead 的分工明确指定我只负责 `tests/integration/`，biz 单测由 developer_1 自己做更合理（他实现时顺手 TDD）。

---

## 3. 覆盖矩阵

### 3.1 用户
| 场景 | 文件 | 断言 |
|------|------|------|
| 注册成功 | user_test.go | 200/201，返回 id + email，不泄漏 password |
| 注册重复邮箱 | user_test.go | 409 / USER_EMAIL_EXISTS |
| 注册大小写变种邮箱 | user_test.go | 409（等价于小写重复） |
| 注册密码过短 | user_test.go | 400 / VALIDATION_FAILED |
| 登录成功 | user_test.go | 200，token 非空 |
| 登录密码错误 | user_test.go | 401 / INVALID_CREDENTIALS |
| `/users/me` 无 token | user_test.go | 401 / UNAUTHORIZED |
| `/users/me` 非法 token | user_test.go | 401 |
| `/users/me` 合法 token | user_test.go | 200，返回同一用户 |

### 3.2 文章
| 场景 | 文件 | 断言 |
|------|------|------|
| 创建 (有 token) | post_test.go | 200/201, id ≠ 0, author_id 正确, tags 保持 |
| 创建 (无 token) | post_test.go | 401 |
| Get (公开) | post_test.go | 200，字段回显 |
| Get 不存在 | post_test.go | 404 / POST_NOT_FOUND |
| Update 作者 | post_test.go | 200 |
| Update 非作者 | post_test.go | 403 / FORBIDDEN |
| Delete 非作者 | post_test.go | 403 |
| Delete 作者 | post_test.go | 200/204，后续 GET=404 |
| List 默认分页 | post_test.go | size=20, total=25 |
| List page=2 | post_test.go | 剩余 5 条 |
| List size=10 | post_test.go | 10 条 |
| List tag=go | post_test.go | 15（10 专属 + 5 共享） |
| List tag=missing | post_test.go | 空 |
| List size>100 | post_test.go | 截到 100（seeded 25 故返 25） |

### 3.3 评论
| 场景 | 文件 | 断言 |
|------|------|------|
| 无 token 评论 | comment_test.go | 401 |
| 有 token 评论 | comment_test.go | 200/201，回显 post_id/author_id/content |
| 评论不存在的 post | comment_test.go | 404 / POST_NOT_FOUND |
| content 空 | comment_test.go | 400 / VALIDATION_FAILED |
| 列表公开 | comment_test.go | 200，total=7 |
| 列表分页 | comment_test.go | size=3&page=2 → 3 条 |

### 3.4 点赞（幂等性是 **重点**）
| 场景 | 文件 | 断言 |
|------|------|------|
| 无 token | comment_test.go | 401 |
| 首次 like | comment_test.go | count=1 |
| 同用户再次 like | comment_test.go | **count 仍=1（幂等）** |
| 另一用户 like | comment_test.go | count=2 |
| 首次 unlike | comment_test.go | count=1 |
| 同用户再次 unlike | comment_test.go | **count 仍=1（幂等）** |
| like 不存在的 post | comment_test.go | 404 |

### 3.5 E2E 全流程
一个用户走完 9 步（注册→登录→发帖→GET→list(tag)→like×2→comment→list→delete→验 404 + cascade），验收 Post/Comment/Like 整合正确。

---

## 4. 编译 / 运行状态

```
cd prototype/M4-example2-e2e/.ai-rd-team/runtime/artifacts/code
```

| 命令 | 结果 |
|------|------|
| `go vet ./tests/integration/...` | ✅ pass |
| `go test -c -o /dev/null ./tests/integration/...` | ✅ **测试包独立编译通过** |
| `go build ./...` | ❌ **developer_2 的 internal/server 有编译错**（非 tester 范围） |

### 4.1 上游阻塞
developer_2 的 `internal/server/{grpc.go,http.go}` 编译错：
- 用了 `c.HTTP / c.GRPC`，但 conf.pb.go 里字段是 `Http / Grpc`。
- 引用了 `v1.RegisterUserServiceServer / RegisterPostServiceServer / RegisterCommentServiceServer`，但 architect 手写的 pb.go 没有定义这三个函数。

已经发 send_message 通知 developer_2 修。修完后 `go build ./...` 就能通过。

### 4.2 要跑真实集成测试还缺什么
1. developer_2 修完上面编译错。
2. developer_2 新建 `tests/integration/app_factory_real.go`，`init()` 里把 `integration.AppFactory` 填上（适配 `*kratos.App` → `AppRunner`）。关键：`HTTPAddr()` 必须返回**实际绑定的端口**（用 `app.Endpoint()` 或 server 自己暴露）。
3. Docker 可用的环境上跑 `go test -race ./tests/integration/...`。

目前 AppFactory 为 nil 时 `requireApp(t)` 会把所有 HTTP 层测试 skip，完全不阻塞其他团队成员的 `go build ./...`。

---

## 5. 依赖（写进 go.mod 的）

- `github.com/testcontainers/testcontainers-go` / `.../modules/postgres`
- `github.com/lib/pq`（纯 database/sql 跑 schema 和 TRUNCATE）
- `github.com/go-kratos/kratos/v2/log`（AppFactory 接口签名需要）

没有 testify，没有 resty，断言全用原生 `t.Fatalf/Errorf`（符合 architect 要求）。

---

## 6. 未决 / 建议

- **建议 developer_1 自己补 `internal/biz/*_test.go` 的 TDD 单测**。他比我更懂自己 usecase 的内部分支，手写 stub + table-test 写起来 30 分钟搞定。architect 已经列了覆盖清单。
- **List 的 `size>100 应被 clamp` 这个行为我按 biz-contracts §3 的“size ≤ 100”写死了**；如 usecase 决定改成返 400 VALIDATION_FAILED，请告知我一下，我改 case。
- **E2E 里删完 post 后列 comments，我把 `404` 和 `200 + empty list` 都视作可接受**；spec 没硬性规定，哪个实现方便走哪个。

---

## 7. 完成度

- [x] 读 architect 的 spec-design.md + data-interfaces.yaml + biz-contracts.md
- [x] main_test.go（testcontainers-go 启 PG + schema.sql）
- [x] app_stub.go（AppFactory 钩子）
- [x] helpers_test.go（setupTestDB / apiCall / createTestUser）
- [x] user / post / comment / e2e_flow 四个业务 test 文件
- [x] 本地 `go vet ./tests/integration/...` + `go test -c` 验证编译通过
- [x] report-tester.md
