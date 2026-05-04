# M3 真实 CodeBuddy 端到端验证报告

**执行时间**：2026-05-04 13:17 - 13:21 UTC（4 分 12 秒）
**环境**：CodeBuddy claude-opus-4.7-1M on Linux
**工作区**：`prototype/M3-real-e2e/`

## 目的

在真实 CodeBuddy 环境完整跑通 **M3 Web 面板 + T3.8 引导 + driver/serve 并行**全流程，验证：

1. **T3.8a 首次启动 Web 引导**：空工作区能否通过 HTTP API 完成 config 初始化
2. **driver + serve 共享 Engine**：两者运行在同一进程的不同线程，是否互不干扰
3. **面板实时反映 Engine 状态**：成员工作时，前端能否每 3 秒轮询拿到新数据
4. **M2 能力继续生效**：Skills/Memory/Cost/Hook 在 M3 架构下是否仍然工作
5. **成员产出质量**：Skills 影响是否更深入（相比 M2 E2E 的 15 个用例）

## 初始状态

```
prototype/M3-real-e2e/
├── (空目录)
```

**关键点**：本次 E2E 故意不提前创建 `.ai-rd-team/config.yaml`，测试 Web 引导流程。

## 时序回放

### 阶段 0：Web 引导（T3.8a）

启动只读 serve：
```bash
python3 -c "from ai_rd_team.service.app import create_app; \
  import uvicorn; app=create_app(Path('.'), None); \
  uvicorn.run(app, host='127.0.0.1', port=8770)"
```

HTTP 调用序列：
| # | 请求 | 响应 |
|---|------|------|
| 1 | `GET /api/onboarding/status` | `{initialized: false, inferred: {project_name: "M3-real-e2e"}}` |
| 2 | `POST /api/onboarding/init` `{run_mode: "lite", budget_per_run: 150}` | `{ok: true, config_path: ".../.ai-rd-team/config.yaml"}` |
| 3 | `GET /api/onboarding/status` | `{initialized: true}` |

生成的 `config.yaml` 干净、带注释、可直接用：
```yaml
config_version: "1.0"
project:
  description: "M3 E2E：验证 Web 引导与面板"
run_mode: "lite"
tech_stack: {backend: null, frontend: null, mobile: null}
budget: {per_run: 150, per_day: 500}
```

### 阶段 1：driver 启动（driver + serve 合并）

```python
# driver.py
engine = TeamEnvironmentManager(workspace=WORKSPACE, quota_home_dir=.../quota-home)
engine.initialize(allow_onboarding=False)          # 发 _version + _probe intent
start_serve_thread(engine)                          # 后台线程启动 web，共享同一 engine
ctx = engine.start_run("M3 E2E：...")               # 发 team_create + task
```

Web 面板地址 `http://127.0.0.1:8770/` 返回 HTML，`/api/*` 端点全部可用。

### 阶段 2：完整 intent 往返（8 个）

| 时间 | Intent | 主 Agent 动作 | 延迟 |
|------|--------|------|------|
| 13:17:09 | `_version` | 返回 `codebuddy-claude-opus-4.7-1M` | ~28s |
| 13:17:37 | `_probe` | 返回 `available_tools` 列表 | ~9s |
| 13:17:46 | `team_create` | 调 `team_create` 工具 | ~72s |
| 13:18:58 | `task`（dev，4646 字 prompt） | 调 `task` 工具派发 | ~70s |
| 13:19:32 | `send_message`（启动） | 调 `send_message` 工具 | 即时 |
| 13:20:17 | `shutdown_request` | 调 `send_message(shutdown_request)` | ~43s |
| 13:21:00 | `team_delete` | 调 `team_delete` 工具 | ~22s |

### 阶段 3：面板实时刷新（成员工作的 45 秒内）

在成员工作时，面板通过 HTTP API 返回的实时数据：

**t=10s**（member.status=working）：
```json
{
  "status": "working",
  "current_task": "实现 fibonacci 函数与 pytest 测试",
  "progress": "10%",
  "last_updated": "2026-05-04T13:19:00+00:00"
}
```

**t=30s**（member.status=done）：
```json
{
  "status": "done",
  "current_task": "M3 E2E Fibonacci 实现与测试已完成，23/23 通过",
  "progress": "100%",
  "produced_files": [
    "artifacts/code/fibonacci.py",
    "artifacts/code/test_fibonacci.py",
    "artifacts/reports/report-developer.md"
  ]
}
```

成本快照实时更新：
```json
{"resource_points": 42, "rp_budget": 150, "rp_usage_ratio": 0.28,
 "member_spawn_count": 1, "message_count": 1}
```

事件流 3 条（run_starting / member_spawned / run_started），全部带 UTC 时区。

### 阶段 4：driver 结束（13:21:21）

```
Cost summary: rp=42 mode=lite members=1 messages=1 minutes=0.0
Run stopped: id=f36b5279 reason=m3-e2e-done
driver 完成；面板继续保留 8 秒以便查看最终状态
```

## 关键验证结果

### 1. T3.8a Web 引导流程 ✅

- `GET /api/onboarding/status` 正确返回 `initialized` + `inferred`
- `POST /api/onboarding/init` 生成合法 config.yaml（含注释）
- 重复 POST 会返回 409 冲突
- `run_mode` 校验正常（非法值返回 422）

### 2. driver + serve 架构 ✅

- 单进程 + uvicorn 后台线程，**无需独立 serve 进程**
- Web 面板与 Engine 共享同一实例，读类端点实时读 runtime/，写类端点通过 EngineProxy
- driver 主线程跑 Engine，serve 线程跑 HTTP，**互不阻塞**

### 3. 成员产出质量（对比 M2 / M1）⭐

| 指标 | M1 | M2 | M3 |
|------|----|----|----|
| 产出文件 | 1 | 2 | **3** |
| 测试用例 | 0 | 15 | **23** |
| 验证覆盖维度 | - | parametrize | parametrize + bool 陷阱 + 递推验证 + TypeError |

M3 成员表现**明显更细致**：
- 主动识别 `bool` 被 Python 当作 int 的陷阱并加专项测试
- 主动增加 `TypeError` 检查（非 int 输入）
- 加入递推关系交叉验证 `fib(50) == fib(49) + fib(48)`
- 报告中**显式引用** Skills 名称「符合 `python-best-practices` Skill」

`pytest -v` 结果：**23 passed in 0.04s** ✅

### 4. M2 能力在 M3 架构下继续工作 ✅

- **Skills 注入**：prompt 4646 字，含完整 python-best-practices + pytest-guide
- **CostTracker**：rp=42（40 spawn + 2 message），ratio=0.28
- **时区时间戳**（F1）：events / state / cost 全部 `+00:00`
- **team_id 保留**（F2）：team.yaml 结束时仍有 `team_id: ai-rd-team-f36b5279`
- **成员自报 done**（F3）：不需要 Engine 兜底 terminated

### 5. Web 面板 API 覆盖度

测试过的端点（通过 curl + 浏览器）：

| 端点 | 状态 | 备注 |
|------|------|------|
| `GET /api/health` | ✅ | 200 |
| `GET /api/onboarding/status` | ✅ | T3.8a |
| `POST /api/onboarding/init` | ✅ | T3.8a |
| `GET /api/run/current` | ✅ | 返回 engine_state + run 数据 |
| `GET /api/team/members` | ✅ | 实时成员状态 |
| `GET /api/cost/snapshot` | ✅ | 实时成本 |
| `GET /api/events?limit=5` | ✅ | 按时序返回 |
| `GET /` | ✅ | Vue3 HTML |

## 产物

```
prototype/M3-real-e2e/
├── README 无（driver 即说明）
├── driver.log            # 完整驱动日志
├── driver.py             # 合并 driver + serve 的驱动脚本
├── quota-home/           # QuotaTracker 隔离 home
│   └── quota-history.jsonl
└── .ai-rd-team/
    ├── config.yaml       # Web 引导生成的配置
    └── runtime/
        ├── artifacts/
        │   ├── code/
        │   │   ├── fibonacci.py             # 成员产出
        │   │   └── test_fibonacci.py        # 23 个用例
        │   └── reports/
        │       └── report-developer.md      # 成员开发报告
        ├── cost/
        │   ├── post-run.jsonl
        │   └── resource-points.yaml
        ├── current-run.yaml
        ├── events.jsonl                     # 完整事件流
        ├── logs/
        │   └── adapter-calls.jsonl
        ├── messages/
        │   └── 20260504-131932-main-developer.json
        └── state/
            ├── members/developer.yaml       # status=done
            ├── roster.yaml
            └── team.yaml                    # team_id 完整
```

## 结论

> **M3 Web 面板 + T3.8 Web 引导 + driver/serve 并行架构在真实 CodeBuddy 环境完整可用。**

M3 MVP 彻底收尾。Skills 持续拉高成员产出质量（M1 1 文件 → M2 15 测试 → M3 23 测试 + 严谨边界），架构在真实场景下经受住了考验。

下一步：
1. M4 打磨发布（README / 示例 / PyPI test）
2. 或给 Web 面板补细节（消息发送按钮、成员互动等）
