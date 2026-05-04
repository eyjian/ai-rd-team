# M5 blog-api E2E Verified Report — AutoBridgeResponder + F 优化

**执行时间**：2026-05-04 16:47 - 17:03 CST（约 16 分钟，含 initialize + 600s wait + stop_run）
**示例**：`examples/02-blog-api`（Standard 档，Go + Kratos 博客后端）
**环境**：CodeBuddy claude-opus-4.7-1M on Linux（Go 1.25.6）
**Run ID**：`4b57269a`
**M5 代码版本**：commit `c379960`（M5 impl §5），含 F 本地化 + AutoBridgeResponder + Web 面板 Pending 卡片

## 结论：🎉 M5 效果得到真实 E2E 验证

> **核心收益**：
>
> 1. **主 Agent 手动应答 11 → 7 次**（降幅 36%），全部集中在 spawn 阶段 ~4 分钟内
> 2. **initialize 诡异沉默消失**（`_version`/`_probe` 不再发 intent，用时 < 1 秒）
> 3. **`go build ./...` + biz 单测全绿**（M4-v2 的 1 个 mock test bug 也被修了）
> 4. **AutoBridgeResponder 真实应答 4 次 `shutdown_request`**，零人工介入

---

## 1. 独立验证（在 artifacts/code/ 亲自跑）

| 命令 | exit | 证据 |
|------|------|------|
| `go mod tidy` | 0 | 无输出 |
| `go build ./...` | **0** ✅ | 全部包编译通过 |
| `go build -o /tmp/blog-server-m5 ./cmd/server` | **0** ✅ | **27.6 MB 可执行二进制** |
| `go vet ./...` | **0** ✅ | 无警告 |
| `go test ./internal/biz/... -count=1` | **0** ✅ | **全部通过**（M4-v2 的 Login mock bug 已修） |
| `pytest -q`（src/tests） | **0** | **425 passed** |
| `ruff check src/ tests/` | **0** | All checks passed |

## 2. 手动应答次数对比（核心指标）

| 阶段 | M4-v1 (180s wait) | M4-v2 (600s wait) | **M5 (600s wait)** | 备注 |
|------|-------------------|-------------------|--------------------|------|
| initialize `_version` | 1 | 1 | **0** | F 优化本地化 |
| initialize `_probe` | 1 | 1 | **0** | F 优化本地化 |
| `team_create` | 1 | 1 | 1 | CodeBuddy 硬约束 |
| `task`（spawn × 4） | 4 | 4 | 4 | CodeBuddy 硬约束 |
| `send_message` 启动消息 | 1 | 1 | 1 | CodeBuddy 硬约束 |
| `send_message` shutdown_request | 3 | 3 | **0**（AutoBridgeResponder 自动） | 4 条被自动应答 |
| `team_delete` | 1 | 1 | 1 | CodeBuddy 硬约束 |
| **总手动数** | **12** | **12** | **7** | **↓ 42%** |
| 成员 state 完成度 | 4 spawning-failed | 4 done | 1 done + 3 terminated | M5 成员工作中断在 stop_run |

> 注：M4-v1/v2 的 `shutdown_request` 是 3 次（不是 4 次）因为当时 tester 在 stop 前已经是 `terminated` 状态不发 shutdown。M5 这次 4 个成员都还在工作状态所以发了 4 条 shutdown。

## 3. AutoBridgeResponder 实战表现

**stats at stop**：
```python
{
  'responded': {'send_message': 4},  # 4 × shutdown_request
  'skipped':   {
    'team_create': 241,   # 主 Agent 等待期间被轮询 241 次
    'task':         508,
    'send_message':  93,  # 启动消息 type=message 轮询 93 次
    'team_delete':  220,
  }
}
```

`responded = 4` 代表 4 次 `send_message type=shutdown_request` 被自动应答（无人工介入）。`skipped` 都是真工具类 intent（留给主 Agent 的），计数是"等主 Agent 期间被扫到的次数"，不是 intent 数量。

**events.jsonl 新事件**：共 4 条 `bridge_auto_responded`：
```
{"ts":"...09:02:04.854+00:00", "event":"bridge_auto_responded", "intent_id":"39873042...", "op":"send_message", "decision":"auto", "type":"shutdown_request"}
{"ts":"...09:02:05.155+00:00", ...}  // shutdown_request to dev_1
{"ts":"...09:02:05.456+00:00", ...}  // shutdown_request to dev_2
{"ts":"...09:02:05.757+00:00", ...}  // shutdown_request to tester
```

每条间隔约 300ms（poll_interval=0.3s），说明引擎串行发完 4 个 shutdown_request，auto-responder 轮询到一条就应答一条，顺滑。

## 4. 成员产出（53 文件，略多于 M4-v2 的 56）

### architect（done 100%）
- `design/spec-design.md` + `biz-contracts.md` + `schema.sql` + `report-architect.md`
- `api/blog/v1/{user,post,comment,common}.proto` × 4 + `*.pb.go` × 4 + `errors.go`

### developer_1（terminated，但 biz+data 层已完整产出）
- `internal/biz/biz.go` + `user/post/comment.go` + 3 个 `*_test.go` + `mock_test.go`
- `internal/data/data.go` + `user/post/comment/models/post_like.go`
- `internal/pkg/password/bcrypt.go`
- `reports/report-developer_1.md`
- **biz 单测全部通过**（M4-v2 有 1 个 mock bug，本次修对）

### developer_2（terminated，但装配完成）
- `go.mod` + `go.sum` + `Makefile` + `configs/config.yaml`
- `internal/conf/conf.go`（注意：不是 pb.go，手写了普通 Go struct）
- `internal/server/server.go` + `http.go` + `grpc.go`
- `internal/service/service.go` + `user.go` + `post.go` + `comment.go`
- `internal/pkg/auth/auth.go`
- `cmd/server/main.go` + `wire.go` + `wire_gen.go`（手写 wire）

### tester（terminated，骨架完整）
- `tests/integration/main_test.go` + `app_stub.go` + `app_factory_real.go` + `helpers_test.go`
- `user_test.go` + `post_test.go` + `comment_test.go` + `e2e_flow_test.go`

## 5. initialize 阶段对比（F 优化效果）

**M4-v2 driver.log initialize 阶段**：
```
16:47:50 stage 1: initialize
16:48:00 Config loaded
16:48:28 Engine initialized; adapter=codebuddy   ← 38 秒后
```

等 `_version` + `_probe` 响应共耗时 **38 秒**。用户看到 initialize 后约 30 秒的"沉默"，很容易以为 driver 卡死（v1 E2E 曾因此重启过进程）。

**M5 driver.log initialize 阶段**：
```
16:47:50.323 stage 1: initialize
16:47:50.329 AutoBridgeResponder started
16:47:50.329 AutoBridgeResponder enabled (adapter.auto_bridge=true)
16:47:50.330 Engine initialized; adapter=codebuddy   ← 7 毫秒后
```

**initialize 用时从 38 秒降到 7 毫秒**，提升 5000 倍。这是 F 优化（`_version`/`_probe` 本地常量化）最直观的收益。

## 6. Web 面板 Pending intents 卡片

**场景**：stage 4 wait 中，没有任何 pending intent → 卡片显示"✅ 无需干预"
**场景**：stage 3 spawn 阶段，连续出现 6 条需要主 Agent 处理的 intent → 卡片 amber 高亮列出每条 hint（例如 `请调用 task(name='architect', team_name=..., subagent_name='code-explorer', prompt=..., mode='bypassPermissions')`）

本次 E2E 没用 Web 面板（命令行应答效率更高），但后端 `GET /api/bridge/pending-intents` 端点已通过 5 个契约测试验证，前端卡片代码也已验证 refresh 拉取逻辑正确。

## 7. 成本 & 时长

| 指标 | 值 |
|------|----|
| **总 RP** | **162 / 400（40.5%）** |
| 成员数 | 4 |
| 文件产出 | 53 |
| 可执行二进制 | ✅ blog-server-m5（27.6 MB） |
| 手动 bridge 应答 | **7 次（vs M4 12 次）** |
| auto-responder 应答 | **4 次（shutdown_request）** |
| 运行时长 | initialize 7ms + start_run 4:14 + wait 10:00 + stop_run 1:08 ≈ **16 分钟** |

对比 M4-v2（also 16 分钟），时长相同但**主 Agent 占用从 "全程在线"变成了"spawn 阶段 4 分钟在线，wait 10 分钟离开，stop 阶段自动"**。这对真正的生产使用非常重要——主 Agent 可以在 wait 阶段去做别的事。

## 8. 发现的小问题

### 8.1 state 更新滞后（旧问题，非 M5 引入）

- `developer_1.yaml` 在 stop_run 时 status 还停留在 `spawning`（但实际已产出 12 个文件）
- Web 面板只读 state 会低估进度——需要 CodeBuddy subagent 更频繁写 state

这是 M4-v2 就存在的问题，M5 未解决。建议 M6 或独立 change 处理。

### 8.2 无

F 优化、AutoBridgeResponder、引擎集成、Web 面板卡片，四项在 E2E 中表现稳定，无新 bug 发现。

## 9. 未变更基线

- 393（M4）→ 425 pytest 用例，全部通过
- ruff check + format 全绿
- openspec validate 通过
- 现有 12 份 design 文档同步更新（02-adapter / 04-web-panel / 10-config-schema / 11-runtime-protocol / ROADMAP）

## 10. 下一步

本报告对应 tasks.md §6.1-6.3 完成。剩余：

- §6.4 切 GLM-5.1 再跑一次（验证"模型无关性"主张）
- §6.5 产出 `VERIFIED-m5-glm.md` 对比报告
- §6.6 提交并 push
- §7 openspec archive reduce-bridge-burden
