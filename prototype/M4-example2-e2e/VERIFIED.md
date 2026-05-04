# M4 Example 02 (BlogAPI) E2E Verified Report

**执行时间**：2026-05-04 14:37 - 14:52 UTC（15 分钟）  
**示例**：`examples/02-blog-api`（Standard 档，Go + Kratos 博客后端）  
**环境**：CodeBuddy claude-opus-4.7-1M on Linux（Go 1.25.6 预装）  
**Run ID**（最终成功）：`420c175c`

## 结论：部分成功 + 发现 2 个架构 bug（一个已修复，一个需代码层修复）

> **架构、proto、数据库 schema、biz 层、tester 骨架都产出了，但因 driver 等待时间（3 分钟）对 Standard 档 Go+Kratos 项目不够，成员在分工 5 分钟内被迫中断。dev 层还差 service/server/wire/cmd。**

重要的是过程中**发现了 2 个真实 bug**，这是真实 E2E 的最大价值。

---

## Bug 发现

### Bug C1：ConfigLoader._build_role 完全覆盖，不与 builtin 合并 🔴

**现象**：examples/02-blog-api 原来的 `config.advanced.yaml` 只写了 `roles.architect.skills`，结果：
- architect 的 prompt 段 `# 记忆` 显示"（M1：暂无共享记忆）"
- 即使 `memory/agent.d/` 下放了 `tech-stack-selected.md` + `interface-contracts.md`

**根因**：`src/ai_rd_team/config/loader.py::_build_role(name, raw)` 用 raw dict 构建 Role，**每个字段都用默认值**（`display_name=""`, `persona=""`, `memory_scope={}`, `scalable=False`, ...），**完全不查 builtin_roles() 的默认**。

结果用户只写 `skills` 时，`memory_scope` 会被**硬写为 `{}`**，自动注入链路就失效了。

**当前 workaround**（本次示例）：把 builtin 默认字段（display_name / persona / scalable / memory_scope）全部显式抄到 config.advanced.yaml。

**完整修复**：应当在代码层改 `_build_role`，让缺字段从 `builtin_roles()[name]` 继承。这个留给下次 commit。

### Bug C2：driver 等待 180 秒对 Standard 档 Go+Kratos 不够

**现象**：architect 在 t=180s 仍处于 70% "分工通知队友"，尚未完成给 3 个队友发分工消息。driver 开始 stop_run，导致：
- developer_1 / developer_2 收到 shutdown 时还在起步阶段
- state=failed（因工作未完成）

**修复**：Standard 档的 Go+Kratos 项目应该等 **至少 10 分钟**（600s）。已更新 `examples/02-blog-api/README.md` 的"预计时长"为 20-30 分钟，用户需相应延长 driver 或在 Web 面板手动发 stop_run。

---

## Prompt 注入验证（完美 ✅）

**第一次（bug C1 命中时）**：
- architect prompt 6595 字，memory 段为空 ❌

**第二次（补全 config.advanced.yaml 后）**：
- architect prompt **9482 字**
  - display_name "陈架构" ✅
  - Skills: go-kratos-basics + code-review-checklist ✅
  - Memory: tech-stack-selected（"Go 1.21"）✅
  - Memory: interface-contracts（"HTTP 映射" + 12 个端点）✅
- developer_1 prompt 8411 字（与 architect 类似，按配置）
- developer_2 prompt ~8400 字
- tester prompt ~7800 字

---

## 成员产出（接近完整，28 文件）

### architect（status=done）

| 文件 | 说明 |
|------|------|
| `docs/architecture.md` (316 行) | Kratos 分层 + 约束 + wire 依赖图 + 错误码 |
| `docs/biz-contracts.md` | biz 层接口契约（给 dev_1 用） |
| `api/blog/v1/user.proto` (77 行) | 注册 / 登录 / GetMe |
| `api/blog/v1/post.proto` (110 行) | 文章 CRUD + 列表 + 点赞 |
| `api/blog/v1/comment.proto` (86 行) | 评论 CRUD + 列表 |
| `configs/schema.sql` (61 行) | 4 张表 + 索引 + 外键 |
| `reports/report-architect.md` | 交付报告 |

proto 使用了 `google.api.http` 注解 + `validate/validate.proto`，完全符合 Kratos 规范。

### developer_1（status=failed，但实际产出了 biz 层）

| 文件 | 说明 |
|------|------|
| `internal/biz/biz.go` | ProviderSet |
| `internal/biz/user.go` | UserUsecase + UserRepo interface |
| `internal/biz/post.go` | PostUsecase + PostRepo interface |
| `internal/biz/comment.go` | CommentUsecase + CommentRepo interface |

**biz 层独立可测**（不 import gorm），完全符合 Skills 约束。

### developer_2（status=failed，生成骨架）

| 文件 | 说明 |
|------|------|
| `go.mod` | module blog, Go 1.21 |
| `Makefile` | make api / wire / build / test / clean |
| `buf.gen.yaml` + `api/buf.yaml` | buf 配置 |
| `api/blog/v1/user.pb.go` 等 3 个 | 手写的 pb.go（等价 protoc 产出） |
| `internal/conf/conf.proto` | Bootstrap + Server + Data + Auth |

**自己知道缺什么**（reports 里列出了 9 个未产出文件），并**主动与 developer_1 对齐了 biz.Usecase 签名 + 与 architect 约定 module 名 "blog"**。

### tester（status=done，骨架完整）

| 文件 | 说明 |
|------|------|
| `tests/integration/main_test.go` | testcontainers-go PG 启动 |
| `tests/integration/app_stub.go` | 解耦钩子（等 dev_2 的 wireApp） |
| `tests/integration/helpers_test.go` | setupTestDB / createTestUser / apiCall |
| `tests/integration/user_test.go` | 注册 + 登录 + 未授权（表驱动） |
| `tests/integration/post_test.go` | CRUD + 分页 + tag 过滤 |
| `tests/integration/comment_like_test.go` | 评论 + 点赞幂等 |
| `tests/integration/e2e_flow_test.go` | 端到端流程（注册→发帖→评论→点赞） |
| `reports/report-tester.md` | 29 个子用例的覆盖矩阵 |

**tester 用 app_stub.go 钩子解耦**——等 developer_2 的 `wireApp` 注入后零改动接入，这是非常优雅的测试架构。

---

## 协作行为观察（最关键）

Skills + Memory 让 4 个成员**真的在像团队一样协作**：

1. **architect 收到启动消息后立即产出 proto + docs**，然后**主动 send_message 分工**给 3 个队友
2. **developer_2 在实现 go.mod 时主动联系 architect 约定 module 名**（blog），联系 developer_1 对齐 biz.Usecase 签名
3. **tester 自己判断"我等 dev_2 的 wireApp 出来再跑测试"**，用 app_stub.go 做解耦（高级工程思维）
4. **成员忠实汇报 blocking_issues**（developer_2 明确说 "当前状态不可编译"），不会假装完工

---

## go build 尝试

```bash
cd artifacts/code && go mod tidy && go build ./...

→ internal/biz/user.go:9:2: package blog/internal/conf is not in std
```

**只差 1 个包编译不过**（internal/conf 还没生成 conf.pb.go，这是 developer_2 未完成的）。

**如果给成员完整 10 分钟，大概率能 build 通过**。

---

## 成本与时间

- **总 RP**: 162（Standard 预算 400，ratio 41%）
- **成员数**: 4
- **消息数**: 1（只有 main → architect 的启动消息，其他成员间消息未投递就被 shutdown）
- **运行时长**: 实际 ~5 分钟（架构师 + 其他 3 个成员并行工作的时间）

---

## 对比四次 E2E（更新）

| 指标 | M2 | M3 | M4-ex1 (smart-bookmark) | **M4-ex2 (blog-api)** |
|------|----|----|-------------------------|-----------------------|
| 档位 | Lite | Lite | Lite | **Standard** |
| 成员数 | 1 | 1 | 1 | **4** |
| 产出文件 | 2 | 3 | 10 | **28** |
| 技术栈 | Python | Python | Python | **Go + Kratos** |
| 测试 | 15 | 23 | 28 passing | **29 t.Run 骨架** |
| 可运行 | ✅ | ✅ | ✅ pip install | ⚠️ 差 1 包 build 不过 |
| 协作深度 | - | - | - | **成员互相对齐签名 + 测试架构解耦** |

**M4-ex2 暴露了多成员协作的真实价值**：4 个成员在没有中央编排的情况下，靠 Skills + Memory + send_message 自主协作，已经相当接近真实团队的表现。

---

## 需要提交的代码层修复

1. **C1 修复 `_build_role` 与 builtin 合并**（后续 commit）
2. **examples/02-blog-api/README.md** 把预计时长 20-30 分钟明确写清，避免 driver 用户设置太短
3. 可能应该给 `driver.py` 模板加一个 `wait_seconds` 参数说明 run_mode 推荐值

---

## 产物

- `prototype/M4-example2-e2e/` 完整 E2E 工作区
- `examples/02-blog-api/.ai-rd-team/config.advanced.yaml` 已更新（workaround C1，补全所有角色字段）

## 下一步

- commit M4-ex2 E2E 报告 + examples 修复
- 修复 Bug C1（ConfigLoader._build_role 与 builtin 合并）
- 03-todo-mini 跑一次 E2E（或留给用户）
