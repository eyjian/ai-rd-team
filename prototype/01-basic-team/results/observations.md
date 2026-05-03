# P1 观察笔记

> 在真实 CodeBuddy Team 实验中观察到的行为细节
> 日期：2026-05-03

## 假设对照

| 假设 | 结论 | 证据 |
|------|------|------|
| ✅ P2P 通信可行 | **成立** | main 只发一条启动消息，三成员完成接力协作 |
| ✅ 自主驱动可行 | **成立** | architect 主动为 tester 写建议章节、tester 主动执行 pytest |
| ✅ 并行派发可用 | **成立** | 3 个 `task(async)` 并行返回，成员独立运行 |
| ✅ 制品正确产出 | **成立** | 4 个产出文件全部完成且高质量 |
| ⚠️ 成员→main 消息可见性 | **有限制** | 成员的汇报消息未在 main 视图自然显现 |

## 未能验证的点

### 点 1：成员间实际消息内容
main 无法看到 architect→developer、developer→tester 的消息内容（这符合 Team 设计：成员间 P2P 通信对 main 透明）。
- 能推断的信息：至少发生了消息传递（否则制品顺序不会对齐）
- 无法推断的信息：消息条数、内容细节、延迟

### 点 2：消息延迟
只能粗略估计：
- architect 收到启动消息 → 落盘 design-note.md：约 1 分钟
- developer 收到设计就绪 → 落盘 calculator.py：约 1 分钟
- tester 收到代码就绪 → 落盘 test_calculator.py + 执行测试：约 1 分钟

**推断**：每次"收消息 + 工具调用（读文件/写文件/send_message）+ 回应"的完整轮次约 30-60 秒。

### 点 3：max_turns 的行为
每个成员设置了 `max_turns=15`，但未观察到任何一个超限（可能因为任务简单）。

## 意外发现

### 发现 1：成员能主动产出 prompt 未明确要求的制品

- architect 产出了 `design-note.md` 的"给 tester 的测试建议"章节
- tester 产出了 `test-results.txt`（我只要求写测试，没说要保留结果）

**意义**：ai-rd-team 的成员 prompt 可以不用"穷举要求"，合理的角色 persona + 明确的目标足以让成员做出符合专业人士习惯的决策。

### 发现 2：成员能遵守"工作目录"约束

我在 prompt 中明确了 `prototype/01-basic-team/results/artifacts/` 为工作目录，三个成员都严格遵守了。这对 ai-rd-team 的"制品目录规范"（参考 P4 的建议）是重大利好——**成员会服从目录约束**。

### 发现 3：成员遵循 "不要请示 main" 的指令

这是本次实验最关键的发现。prompt 明确要求"不要问 main"、"主动与队友沟通"，成员确实做到了。这说明：
- ai-rd-team 可以通过角色 prompt 塑造"自主驱动"行为
- 不需要特殊的 Adapter 机制干预，CodeBuddy Team 的默认行为即可支持

## 对详细设计的输入

### 输入 1：成员 Prompt 模板需要明确
基于本次 prompt 结构效果好，详细设计 `05-roles-skills.md` 应沉淀为模板：
```
# 身份与职责
- 角色：xxx
- 团队：xxx（成员名单）
- 任务：xxx

# 工作目录
xxx

# 你要做什么
1. xxx
2. xxx

# 关键要求
- 不要询问 main
- 主动与队友沟通
- send_message 工具使用示例

# 等待起始消息
```

### 输入 2：main 与成员通信的限制
`main ← member` 消息不像 `member ↔ member` 那样透明。详细设计需要：
- 显式声明消息可见性模型
- Web 面板通过文件监听（P3 决策）而非 main 视图观察全局状态
- 成员"完成报告"应该以**文件产出**形式，而非消息通知

**这进一步强化了 P3 的决策：运行时状态用文件，不依赖 main 视图。**

### 输入 3：shutdown 流程
`shutdown_request → 等待 → team_delete` 三步流程在本次实验走通。详细设计可沿用此模式。

## 性能基线（粗略）

| 指标 | 观察值 |
|------|--------|
| 一次 task 派发的启动时间 | <5 秒（并行派发 3 个总耗时 <10 秒） |
| 一个简单任务的完整轮次（收消息→工作→发消息） | 30-60 秒 |
| 从启动到第一个制品出现 | 约 1 分钟 |
| 从启动到全部制品完成 + 测试通过 | 约 2-3 分钟 |
| 整个实验（含汇报请求和 shutdown） | 约 6 分钟 |

**对 Resource Points 校准的输入**：
- `per_minute_runtime: 2` 权重可能偏低：一个 6 分钟的实验明显消耗巨大的 token（3 个成员独立上下文）
- `per_member_spawn: 10` 权重偏低：每个成员 spawn 意味着一个完整的上下文 + prompt + 首次响应，实际可能相当于几十到上百条消息的开销

## 风险点记录

### 风险 1：`send_message` 无成功回执机制
main 发给成员的消息只知道"放进 inbox 了"，不知道成员是否真的处理了。在真实 ai-rd-team 中需要：
- 关键消息有超时 + 重试
- 通过文件产出间接确认成员在工作

### 风险 2：成员 stuck 时主 Agent 难以发现
若某成员卡住（例如一直等不到消息），main 无法直接感知。详细设计中需要：
- 定期健康检查（轮询每个成员的 status 文件）
- 卡住时由 PM 角色介入而非 main（与头脑风暴文档一致）

### 风险 3：shutdown_response 等待机制
我在 shutdown_request 后 sleep 20 秒就 team_delete 了，实际 shutdown_response 可能未收到。这个是否会导致问题？
- 本次实验未见问题（team_delete 成功）
- 但在复杂工作中可能会导致工作丢失
- 详细设计需要：优先等 shutdown_response，超时才强制 team_delete
