# P1 结论：基础 Team 协作

> 日期：2026-05-03
> 状态：**✅ 核心假设成立，有补充说明**

## 核心结论

**CodeBuddy Team 模式的 `team_create` + `task`(async) + `send_message` 能够支持 ai-rd-team 所需的"自主驱动多成员协作"。**

整个 ai-rd-team 的架构基础是成立的，可以进入详细设计阶段。

## 成功证据

1. **零干预协作完成**：main 只发了 1 条启动消息，3 名成员独立完成了设计、编码、测试、执行测试的完整流程
2. **制品高质量**：26 个 pytest 用例全部通过，代码结构、docstring、错误处理都符合专业标准
3. **自主决策可见**：architect 主动为 tester 写测试建议、tester 主动执行 pytest 并保留结果，这些都不在启动 prompt 的明确要求里
4. **P2P 通信存在**：从"developer 使用的错误消息 == tester 断言的错误消息"这种精确一致性看，必然发生了成员间消息传递

## 发现的限制

### 限制 1：main ← 成员 消息的可见性

main 发出的 "请汇报" 请求成员收到了，但 main **无法在同一会话中直接看到回复**。
**影响**：不能用"成员发消息给 main"作为状态汇报的主要手段。  
**应对**：走 P3 决策的文件监听方案，状态以文件形式呈现给 Web 面板。

### 限制 2：成员间消息对 main 不可见（设计使然）

这是 CodeBuddy Team 的设计特性（独立上下文、P2P）：architect↔developer 的消息不会流到 main。  
**影响**：main 不能做"全局协作监督"。  
**应对**：
- 运行时状态由文件层统一呈现
- 若需要监控成员间对话，应要求成员在关键决策点写"决策日志"到文件

### 限制 3：shutdown_response 时序依赖

main 必须在 `team_delete` 前等待所有 `shutdown_response`，但 CodeBuddy Team 没有显式的"等待机制"，只能 sleep + 祈祷。  
**影响**：并发工作可能被强制终止。  
**应对**：
- main 向成员发 shutdown_request 前，应先让成员完成当前工作
- 详细设计中明确 shutdown 流程的 SOP

## 对 ai-rd-team 架构的影响

### 利好：核心架构成立
- 四层架构（表现层 + 服务层 + 引擎层 + 适配层）可以按原计划推进
- Adapter 层只需包装 CodeBuddy 工具即可满足第一期需求
- "自主驱动"理念被证实可行

### 调整：状态监控必须走文件
- Web 面板**不能**通过 main 视图观察成员状态
- 成员必须定期将自己的 status 写到 `.ai-rd-team/runtime/state/members/{name}.yaml`
- 配合 P3 的文件监听方案，Web 就能获取全局视图

### 调整：关键事件应有文件产出证据
不光是制品，"关键决策"、"评审结论"、"异常"都应落盘到文件：
- 成员间消息可选择性地 echo 到 `runtime/messages/{timestamp}-{from}-{to}.json`
- 阶段完成时写 `runtime/events/phase-{name}-complete.json`
- 这样 main 和 Web 都能掌握全局

## 对详细设计的具体输入

| 设计文档 | 影响项 |
|---------|-------|
| `01-engine.md` | 引擎需要维护"成员状态文件"的读写协议 |
| `02-adapter.md` | CodeBuddyAdapter 的 `send_message` 要可选择 echo 到文件 |
| `04-web-panel.md` | 确认采用文件监听（P3），不走 main 视图 |
| `05-roles-skills.md` | 成员 Prompt 模板要包含"定期写 status 文件"的指令 |
| `07-artifacts.md` | 新增"运行时文件"目录结构（与制品并列） |
| `11-runtime-protocol.md` | 明确 main/Adapter/成员/文件 之间的通信协议 |

## 对 Resource Points 权重校准的输入（P5 用）

| 权重项 | 当前值 | 校准建议 |
|-------|-------|---------|
| per_member_spawn | 10 | **偏低**。每个 async 成员带完整 prompt + 系统上下文 + 首次响应，建议提到 **20-30** |
| per_message | 1 | 合理（消息本身 token 少） |
| per_minute_runtime | 2 | **偏低**。成员空转等消息也有一定消耗，建议提到 **3-5** |
| per_iteration | 5 | 合理 |
| per_broadcast_target | 1 | 本实验未测，保持 |

## 下一步

P1 验证完成，可以继续：
- **P2（Skills 加载）**：在 P1 的基础上测试 `.codebuddy/skills/` 是否被自动应用
- **P5（成本基线）**：基于 P1 数据进一步细化权重建议

或者直接进入详细设计第一批文档（`00-overview.md` + `10-config-schema.md` + `05-roles-skills.md`）。

---

**建议决策给用户**：P1 核心已通过，P2 可以与详细设计并行推进，不必卡在原型阶段。
