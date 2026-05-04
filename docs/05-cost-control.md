# 成本控制

ai-rd-team 不直接用钱或 token 数计量，用 **Resource Points (RP)**。

## 为什么用 RP 而不是 token？

- token 数不直观（"这个功能用了 5 万 token" 你没感觉）
- 不同模型 token 单价差异大（opus vs haiku 相差 60 倍）
- 成员行为不只是 token：spawn subagent、broadcast、运行时长都是成本
- RP 是个**抽象层**，把多维成本统一成一个数字便于预算

## RP 计量公式（M2 固定权重）

| 事件 | RP |
|------|-----|
| spawn 一个成员 | 40 |
| 发送一条消息 | 2 |
| broadcast（每个目标） | 2 |
| 运行 1 分钟 | 5 |
| 一轮迭代（architect/reviewer 回复） | 15 |

**注意**：M2 用固定权重简化实现。M5 计划根据真实 token 消耗回归校准更精确的系数。

## 档位预算（M2 默认）

| 档位 | max_resource_points | max_members | max_messages | max_broadcasts | max_runtime_minutes | max_total_iterations |
|------|---------------------|-------------|--------------|----------------|---------------------|----------------------|
| lite | 120 | 2 | 20 | 0 | 30 | 5 |
| standard | 400 | 5 | 100 | 3 | 120 | 15 |
| full | 1500 | 15 | 500 | 10 | 480 | 50 |

## 窗口额度（Quota）

独立于单次运行，限制**累计消耗**：

```yaml
cost_control:
  quota_enabled: true
  quota_windows:
    per_day: 2000
    per_week: 10000
    per_month: 30000
```

超过任一窗口会触发 **BLOCK**（下次 start_run 直接拒绝）。

历史记录存在 `~/.ai-rd-team/quota-history.jsonl`（每次 run 结束追加一行）。

## 预算检查动作（BudgetAction）

在每次 `check_budget()` 调用时返回：

| action | 触发条件 | 语义 |
|--------|---------|------|
| CONTINUE | 一切正常 | 继续 |
| WARN | rp_ratio ≥ 0.75（model_fallback.trigger_threshold） | 建议切换低成本模型 |
| SMART_PAUSE | rp ≥ budget 或 member/message/broadcast/runtime/iteration 任一超限 | **暂停运行**，等待用户决定 |
| BLOCK | 窗口额度耗尽（day / week / month） | **拒绝启动**，需要等窗口重置 |

## smart_pause 响应（Web 面板）

当 action=SMART_PAUSE，前端会弹出告警模态，提供 3 种选择：

1. **继续**（`action: continue`）：记录事件，前端不再弹窗（同一 run 内）
2. **提高预算**（`action: raise_budget`, `raise_to: 新值`）：动态提升硬限
3. **停止**（`action: stop`）：等价 `stop_run(reason="user-budget-stop")`

对应后端：`POST /api/run/budget-ack`。

## 模型降级 semi_auto（M2）

```yaml
cost_control:
  model_fallback:
    enabled: true
    trigger_threshold: 0.75   # 超 75% 预算触发
    model_chain:
      - "claude-opus-4.7"
      - "claude-sonnet-4.7"
      - "claude-haiku-4.5"
```

第一期返回**建议**（不实际切换）。主 Agent 收到 WARN 后可以手动 `/switch` 模型。

自动切换留待 M5（需要 Adapter 层支持运行时切模型）。

## 实时查看

### 命令行

```bash
cat .ai-rd-team/runtime/cost/resource-points.yaml
```

```yaml
run_id: "abc12345"
mode: "lite"
resource_points: 42
rp_budget: 150
rp_usage_ratio: 0.28
member_spawn_count: 1
message_count: 1
broadcast_count: 0
runtime_minutes: 2.3
day_used: 42
week_used: 42
month_used: 42
```

### Web 面板 > 成本页

- 当前运行 RP 使用情况（圆环 + 数字）
- 窗口额度（day/week/month 剩余）
- 历史运行成本表格（post-run.jsonl）

### API

```bash
curl http://127.0.0.1:8765/api/cost/snapshot
curl http://127.0.0.1:8765/api/cost/budget-check
curl http://127.0.0.1:8765/api/cost/history?limit=20
```

## post-run 记录

每次 run 结束会追加到 `.ai-rd-team/runtime/cost/post-run.jsonl`：

```json
{"run_id":"abc12345","mode":"lite","started_at":"...","ended_at":"...",
 "resource_points":42,"rp_budget":150,"member_spawn_count":1,"message_count":1,
 "runtime_minutes":2.3,"notes":"normal"}
```

适合后期做成本分析、模型性价比对比。

## 相关设计文档

- `openspec/specs/design/08-cost-control.md` — 成本控制完整设计
- `src/ai_rd_team/cost/tracker.py` — 实现
