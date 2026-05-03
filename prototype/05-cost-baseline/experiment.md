# P5：成本基线测量

## 验证假设
头脑风暴中定义的 Resource Points 权重公式：
```
per_member_spawn: 10
per_message: 1
per_broadcast_target: 1
per_minute_runtime: 2
per_iteration: 5
```
这些权重基于经验拍定，**需要真实数据校准**。

## 测量目标

在 P1-P4 实验过程中**顺便**测量：

| 指标 | 定义 | 测量方式 |
|------|------|---------|
| **成员启动成本** | 一次 `task` 派发消耗的 token | 派发前后观察 CodeBuddy 面板 |
| **消息成本（单条）** | 发送方 output + 接收方 input | 估算 + 实际对比 |
| **广播成本（N 接收）** | 广播给 N 个成员的总消耗 | 估算 + 实际对比 |
| **闲置成本** | 成员等待消息时的消耗 | 让成员空等 5 分钟观察 |
| **制品产出成本** | 产出一个 Markdown/Python 文件的 output | 按文件大小估算 |

## 数据来源

### 来源 1：CodeBuddy IDE 面板
- 派发 Team 前记录当前会话 token
- 每阶段完成后记录
- 做差得到增量

### 来源 2：token_counter.py 估算
- 对每条真实消息用估算公式算一遍
- 与 CodeBuddy 实际数据对比，校准估算系数

### 来源 3：时间戳差
- `metrics_collector.py` 记录事件时间戳
- 用 `duration_seconds` 校准 `per_minute_runtime`

## 记录模板

`results/token-counts.yaml`：
```yaml
experiment: P1-basic-team
model: claude-sonnet-4
measurements:
  team_create:
    tokens_observed: 0        # 派发前
    note: "仅 API 调用，几乎无 token"
  
  member_spawn:
    architect:
      spawn_tokens: 2500      # 启动 + 首次响应
      prompt_tokens: 450
      skills_tokens: 0        # 本实验未用 skills
    developer:
      spawn_tokens: 2300
      prompt_tokens: 380
    tester:
      spawn_tokens: 2200
      prompt_tokens: 350
  
  message_costs:
    - from: main
      to: architect
      content_len: 12
      estimated_tokens: 6
      observed_delta: 2500    # 该成员收到消息后的本轮总消耗
      net_per_message: ~100
  
  broadcast_costs: []         # 本实验未使用
  
  total:
    start: 0
    end: 48300
    delta: 48300
    duration_minutes: 8.2
```

## 校准产物

`results/weight-calibration.md`：

```markdown
## Resource Points 权重校准（基于 P1 实际数据）

| 原权重 | 实际观察 | 建议新权重 | 理由 |
|--------|---------|-----------|------|
| member_spawn: 10 | ~2500 token | 25 | 原权重偏低 |
| message: 1 | ~100 token | 1 | 接近基准 |
| broadcast×N: 1/人 | 未测 | 1/人 | 保持 |
| minute_runtime: 2 | 闲置消耗低 | 1 | 偏低 |
| iteration: 5 | ~500 token | 5 | 接近 |

建议：以 "100 token = 1 Resource Point" 为基准校准。
```

## 产物清单
- `results/token-counts.yaml`：原始测量数据
- `results/weight-calibration.md`：校准建议
- `results/conclusion.md`：本项验证结论
