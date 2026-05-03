# P3 决策：Web 面板与 Team 通信方案

> 日期：2026-05-03
> 基于 `experiment.md` 的方案对比
> 第一期推荐方案 + 演进路径

## 第一期选型：**方案 A（文件监听）+ 方案 D（HTTP 回调）混合**

### 主路：方案 A - 文件监听

**规则**：Team 成员的所有产出（消息、制品、状态）都落盘到约定目录，Web 后端通过文件监听感知变化。

**目录约定**：
```
.ai-rd-team/runtime/
├── state/
│   ├── team.yaml              # 团队整体状态（原子 rename）
│   └── members/{name}.yaml    # 各成员状态
├── messages/
│   └── {timestamp}-{from}-{to}.json   # 每条消息一个文件
├── events.jsonl               # 全局事件追加日志（fcntl 锁）
└── artifacts/
    └── {phase}/{file}         # 各阶段制品
```

### 辅路：方案 D - HTTP 回调

**规则**：对"用户对团队的操作"（暂停/介入/发消息）采用 Web 后端暴露 REST API，让**用户通过 Web 操作 Team**。

**接口示例**：
```
POST /api/team/pause          # 暂停
POST /api/team/resume          # 恢复
POST /api/team/message          # 用户向某成员发消息
GET  /api/team/state           # 查询当前状态（也可直接读文件）
```

## 完整数据流

```
┌──────────────┐
│  Team 成员    │
│  (CodeBuddy)  │
└──────┬───────┘
       │ 产出消息/制品/状态变更
       ▼
┌──────────────────────────────────┐
│  .ai-rd-team/runtime/ 目录        │
│  (约定结构，原子写)                │
└──────┬───────────────────────────┘
       │ 文件变化
       ▼ (watchdog/inotify)
┌──────────────┐       ┌──────────────┐
│  Flask 后端   │ ◄────┤  用户 (Web UI)│
│  - 监听文件   │  ────┤  - 查看状态   │
│  - 推送 SSE   │       │  - 发送操作   │
└──────┬───────┘       └──────────────┘
       │ SSE / WebSocket
       ▼
┌──────────────┐
│  Vue3 前端    │
│  - 实时展示   │
└──────────────┘

用户操作（暂停等）：
  用户 → Web 前端 → POST /api/team/xxx → Flask → 写入 .ai-rd-team/runtime/commands/
  Team 成员定期检查 commands/ 目录响应操作
```

## 方案选择理由

| 原则 | 文件监听+HTTP | 单独 Socket | 纯 HTTP 轮询 |
|------|--------------|------------|-------------|
| 低耦合 | ✅ 成员不知 Web 存在 | ❌ | ⚠️ |
| 持久化 | ✅ 文件即历史 | ❌ | ❌ |
| 简单 | ✅ | ❌ 连接管理 | ✅ |
| CodeBuddy 友好 | ✅ 成员只需写文件 | ❌ 需要 socket 能力 | ⚠️ 需要 curl |
| 断点续跑 | ✅ | ❌ | ❌ |
| 实时性 | 中（~100ms） | 高 | 低 |

**关键权衡**：第一期不追求毫秒级实时性，但要求可靠 + 简单 + 低耦合，文件路线最合适。

## 第二期/未来演进

### 演进点 1：实时性优化
当用户规模增长或需要毫秒级反馈时：
- 保留文件层作为数据源
- 增加内存 pub/sub（Redis / 内置 channel）
- 文件监听变为"兜底"

### 演进点 2：分布式部署
ai-rd-team Web 面板跑在远程服务器时：
- 文件同步 → 改为网络队列（Redis Streams / Kafka）
- Web 后端与 Team 跨机器

### 演进点 3：QQ/微信 Bot
通过相同的 HTTP API 入口接入其他表现层，无需重构。

## 第一期的技术栈确认

| 组件 | 选型 |
|------|------|
| 文件监听库 | `watchdog`（已在原型 `file-watch-approach.py` 演示） |
| Web 后端 | Flask（已确定） |
| 实时推送 | SSE（Server-Sent Events，原生支持，简单） |
| 前端 | Vue3 + Chart.js + Mermaid.js |
| 消息格式 | JSON（便于解析） |
| 状态格式 | YAML（可读性好） |

## 对设计文档的影响

- `04-web-panel.md`：采用本决策作为架构依据
- `11-runtime-protocol.md`：明确 `.ai-rd-team/runtime/` 的目录结构和文件协议
- `07-artifacts.md`：引用 P4 的写入策略

## 原型验证的 P3 项 - 结论

**✅ 成立**：文件监听 + HTTP 回调混合方案可行，满足第一期需求。

**原型产物**：
- `file-watch-approach.py`：已验证 watchdog 可用
- `simple-http-callback.py`：已验证 Flask HTTP 接口可用
- 两个 Demo 都跑起来了（理论验证阶段完成，未做联调）

**遗留工作**：
- 联调：真实 Team 成员写文件 + Web 监听的端到端测试（并入 P1 一起做）
- 细节：文件监听的 debounce 策略（避免同一文件写入多次触发）
