# P1：基础 Team 协作实验

## 验证假设
CodeBuddy 的 `team_create` + `task`(async) + `send_message` 能够支持"自主驱动"的多成员协作，即：
- ✅ 成员间直接 P2P 通信（不经过 main 转发）
- ✅ 成员能自主决定"做完就通知谁"
- ✅ 并行任务能真正并行（互不阻塞）

## 实验设计

### 场景
3 角色协作实现 Python 计算器：
- `architect`：输出接口设计 → `design-note.md`
- `developer`：实现代码 → `calculator.py`
- `tester`：写测试 → `test_calculator.py`

### 对话预期路径
```
main → architect:    "帮我设计一个计算器接口"
architect → developer: "接口是 calc(op, a, b)，请实现"
developer → tester:    "实现完成，请测试"
tester → developer:    "发现问题：XXX" / "测试通过"
developer → main 或 architect: "完成"
```

### 关键观察点
1. **是否 P2P**：developer → tester 消息是否需要经过 main 中转？
2. **消息可见性**：每个成员看到的消息是只有发给自己的，还是全团队可见？
3. **自主决策**：成员能否主动决定发消息给谁（不硬编码 recipient）？
4. **延迟**：消息从发出到被接收/处理的时间间隔
5. **并发**：两个成员同时工作时是否真正并行

## 真实实验步骤

1. 调用 `team_create(team_name="proto-p1-team", description="原型 P1 验证")`
2. 依次派发 3 个成员：
   ```
   task(subagent_name="code-explorer", name="architect", team_name="proto-p1-team",
        mode="bypassPermissions", description="计算器架构设计",
        prompt="...（见 prompts/architect.md）")
   task(subagent_name="code-explorer", name="developer", ...)
   task(subagent_name="code-explorer", name="tester", ...)
   ```
3. 通过 `send_message(type="message", recipient="architect", content="开始任务", summary="启动")`
4. 观察后续消息流
5. 记录每条消息到 `results/conversation-log.md`
6. 完成后 `team_delete()`

## 成功标准

| # | 指标 | 成功阈值 |
|---|------|---------|
| 1 | P2P 消息数 | ≥3 条（architect↔developer↔tester 间的直接通信） |
| 2 | 制品产出 | 3 个文件全部产出 |
| 3 | 代码可运行 | `calculator.py` 通过 `test_calculator.py` |
| 4 | 自主决策体现 | 至少 1 次成员未被告知 recipient，自主选择发送对象 |
| 5 | 团队清理 | `team_delete` 无残留 |

## 失败场景与应对

| 失败情况 | 含义 | 应对 |
|---------|------|------|
| 所有消息都经过 main | 非真正 P2P | 头脑风暴需重做，改"调度器 + 工作队列"方案 |
| 成员间无法互相发现 | 注册表机制有问题 | 加显式队友名单注入到 prompt |
| 并行变串行 | `task(async)` 不真异步 | 接受限制，调整架构为"有限并行" |
| 成员不主动工作 | 需要 main 驱动每步 | 加强 prompt；若仍失败，需重新设计自主驱动机制 |

## 产物清单

- `results/conversation-log.md`：完整消息流记录
- `results/observations.md`：观察笔记（延迟/自主性/P2P 比例等）
- `results/metrics.yaml`：结构化指标
- `results/artifacts/`：成员产出的 design-note.md / calculator.py / test_calculator.py
- `results/conclusion.md`：本项验证结论（✅/❌/⚠️）

## Prompt 草稿

### architect 的 prompt
```
你是一个 Python 架构师"陈架构"，请为团队设计一个简单的计算器接口。

任务：
1. 设计接口签名，写入 <workspace>/prototype/01-basic-team/results/artifacts/design-note.md
2. 设计完成后，使用 send_message 发给 developer，内容包含接口描述
3. 等待 developer/tester 的问题并回答

接口要求：
- 支持 +, -, *, / 四则运算
- 入参：op (str), a (float), b (float)
- 返回：float
- 异常：除零抛 ZeroDivisionError

不需要询问 main，自主决策。完成所有沟通后使用 send_message 通知 main 你的工作完成。
```

### developer 的 prompt
```
你是一个 Python 开发者"林小开"。

任务：
1. 等待 architect 的接口设计
2. 收到后，实现到 <workspace>/prototype/01-basic-team/results/artifacts/calculator.py
3. 实现完成后，使用 send_message 发给 tester，请求测试
4. 根据 tester 的反馈修复问题
5. 全部完成后 send_message 通知 main

不需要请示 main 就可以与 architect/tester 自由沟通。
```

### tester 的 prompt
```
你是一个 Python 测试工程师"赵小测"。

任务：
1. 等待 developer 完成开发
2. 收到后，写测试到 <workspace>/prototype/01-basic-team/results/artifacts/test_calculator.py
3. 执行 pytest，如果失败使用 send_message 告知 developer 具体问题
4. 如果通过，使用 send_message 通知 main 并附测试结果

不需要请示 main。
```
