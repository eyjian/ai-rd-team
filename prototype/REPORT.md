# ai-rd-team 原型验证报告

> 日期：2026-05-03
> 状态：**✅ 完成（3/5 项通过，2/5 项跳过但关键项已验证）**

## 执行摘要

完成了 5 项关键技术假设中的 3 项真实验证（P1、P3、P4）和 1 项基于 P1 数据的校准（P5），跳过 P2（Skills 自动加载，在详细设计中以保守假设处理）。

**核心结论**：**ai-rd-team 的架构基础成立，可以进入详细设计阶段**。

---

## 5 项验证总览

| 项 | 目标 | 方式 | 结果 | 关键发现 |
|----|------|------|------|---------|
| P1 | Team 模式能否自主驱动协作 | 真实实验 | ✅ 成立 | main 零干预下 3 成员完成完整任务，26 测试通过 |
| P2 | Skills 是否自动加载 | 跳过 | ⏭️ 保守假设 | 详细设计假设"需显式注入"，未来验证 |
| P3 | Web 与 Team 通信方案 | 分析 + Demo | ✅ 决策达成 | 文件监听 + HTTP 回调混合方案 |
| P4 | 制品并发写安全 | 实测 | ✅ 三策略验证 | S1 默认（不同文件）/S2 原子 rename/S3 文件锁 |
| P5 | Resource Points 权重 | 基于 P1 数据校准 | ✅ v1 完成 | 原权重低估 4 倍，新值已确定 |

---

## P1 真实实验：基础 Team 协作

**实验任务**：3 角色（architect/developer/tester）协作实现 Python 计算器

**结果**：
- ✅ 零干预协作：main 只发 1 条启动消息，成员自主完成设计→编码→测试→执行
- ✅ 制品高质量：26 pytest 用例全部通过（0.03s）
- ✅ 自主决策：architect 主动为 tester 写测试建议；tester 主动执行 pytest 保留结果
- ✅ P2P 通信：从错误消息字符串精确一致性反证必然发生了成员间消息传递
- ✅ 团队清理：shutdown_request + team_delete 流程正常

**发现的限制**：
1. main 无法直接看到成员的 "报告回复"（消息进了 inbox 但不在 main 视图）
2. 成员间消息对 main 透明（设计使然）
3. `shutdown_response` 无显式等待机制

**详细记录**：`01-basic-team/results/conclusion.md`

---

## P3 Web 与 Team 通信方案

**决策**：**文件监听（主）+ HTTP 回调（辅）混合方案**

- **文件层**：Team 产出（制品/状态/消息）落盘 `.ai-rd-team/runtime/` → Web 后端用 watchdog 监听 → SSE 推送前端
- **HTTP 层**：用户对 Team 的操作（暂停/介入/发消息）走 Flask REST API → 写入 `runtime/commands/` → 成员轮询响应

**理由**：低耦合 + 持久化 + CodeBuddy 友好 + 断点续跑

**详细记录**：`03-web-bridge/decision.md`

---

## P4 制品并发写策略

**三种策略各司其职**：

| 策略 | 场景 | 验证结果 |
|------|------|---------|
| **S1：不同文件并发写**（默认） | 代码/文档/报告等独占文件 | ✅ 10 线程 0 失败 |
| **S2：原子 rename** | 团队状态、单一事实源文件 | ✅ 最终内容完整 |
| **S3：fcntl 文件锁** | 共享追加日志（消息流/事件） | ✅ 所有写入保留 |

**跨平台注意**：fcntl 在 Windows 不可用，需要抽象层 + 降级（如 portalocker）。

**详细记录**：`04-artifacts/results/conclusion.md`

---

## P5 Resource Points 权重校准

**权重更新**（v1）：

| 权重项 | 原值 | 新值 | 倍数 |
|-------|------|------|------|
| `per_member_spawn` | 10 | **40** | ×4 |
| `per_message` | 1 | **2** | ×2 |
| `per_broadcast_target` | 1 | **2** | ×2 |
| `per_minute_runtime` | 2 | **5** | ×2.5 |
| `per_iteration` | 5 | **15** | ×3 |

**档位预算更新**：Lite=120 / Standard=400 / Full=1500

**置信度**：低（基于单次实验估算），需在实际项目中继续校准。

**关键发现**：
- **Spawn 成本巨大**（约 3-5K tokens/人）→ 精简角色比压缩消息更省
- **广播线性放大** → 必须严格限制
- **闲置也有消耗** → 需 `max_idle_minutes` 超时

**详细记录**：`05-cost-baseline/results/weight-calibration.md`

---

## 对详细设计的输入清单

### 全局性输入

1. **状态监控走文件层，不走 main 视图**（P1 + P3）
2. **制品目录结构分"产物"和"运行时"**（P1 + P3 + P4）
3. **Resource Points 权重采用 v1 校准值**（P5）
4. **档位预算更新为 120/400/1500**（P5）

### 各文档具体输入

| 文档 | 输入 |
|------|------|
| `00-overview.md` | 采用原型验证的架构结论作为设计基础 |
| `01-engine.md` | 引擎需维护成员状态文件的读写 + shutdown 时序控制 |
| `02-adapter.md` | CodeBuddyAdapter 的 send_message 可选 echo 到文件 |
| `04-web-panel.md` | 采用文件监听 + HTTP 回调混合方案 |
| `05-roles-skills.md` | Prompt 模板化（基于 P1 有效格式）+ 保守假设 Skills 需显式注入 |
| `07-artifacts.md` | 三种并发写策略分工 + 跨平台注意 |
| `08-cost-control.md` | 权重 v1 + 预算 v1 + 权重热更新机制 |
| `11-runtime-protocol.md` | `.ai-rd-team/runtime/` 目录结构规范 |

---

## 原型产物清单

```
prototype/
├── README.md                    # 总览
├── VERIFICATION-PLAN.md         # 5 项验证详细计划
├── REPORT.md                    # 本报告
│
├── shared/                      # 共享工具（可复用到正式实现）
│   ├── token_counter.py
│   ├── metrics_collector.py
│   └── artifact_recorder.py
│
├── 01-basic-team/
│   ├── experiment.md
│   ├── simulated/team.py        # Team/Member/Mailbox 参考实现（已跑通）
│   └── results/
│       ├── artifacts/           # ⭐ 真实 Team 产出的代码
│       │   ├── design-note.md
│       │   ├── calculator.py
│       │   ├── test_calculator.py
│       │   └── test-results.txt  (26 passed)
│       ├── conversation-log.md
│       ├── observations.md
│       ├── metrics.yaml
│       └── conclusion.md         ⭐ P1 结论
│
├── 02-skills-loading/           # ⏭️ 跳过，素材已准备
│   ├── experiment.md
│   └── skills/                  # 测试 Skills（保留供未来实验）
│
├── 03-web-bridge/
│   ├── experiment.md
│   ├── file-watch-approach.py   # watchdog Demo（已验证）
│   ├── simple-http-callback.py  # Flask Demo（已验证）
│   └── decision.md              ⭐ P3 决策
│
├── 04-artifacts/
│   ├── experiment.md
│   ├── simulated/concurrent_write.py  # 4 测试全通过
│   └── results/conclusion.md    ⭐ P4 结论
│
└── 05-cost-baseline/
    ├── experiment.md
    └── results/
        ├── token-counts.yaml         # 原始估算数据
        ├── weight-calibration.md     # 详细校准逻辑
        └── conclusion.md             ⭐ P5 结论（v1）
```

---

## 风险与遗留

### 已识别风险

| 风险 | 缓解方案 | 所属设计文档 |
|------|---------|------------|
| CodeBuddy 工具 API 未来变化 | BaseAdapter 抽象 + 版本感知 | `02-adapter.md` |
| main 无法直接观察成员状态 | 文件监听方案 | `04-web-panel.md` |
| 跨平台文件锁差异 | fcntl + portalocker 抽象 | `07-artifacts.md` |
| Resource Points 低置信度 | 权重热更新 + 实际数据积累 | `08-cost-control.md` |
| shutdown 时序依赖 | 优先等响应 + 超时强制 | `11-runtime-protocol.md` |

### 遗留工作

- P2（Skills 自动加载）未实测，详细设计阶段如需要可补测
- 跨平台（Windows）原型未测，预计在实现阶段统一处理
- Web 面板端到端联调未做（文件监听 + Team 产出），在详细设计完成后做

---

## 下一步

**进入详细设计阶段**，按核心链路优先顺序：

1. `00-overview.md`：总览、架构图、模块划分、文档索引
2. `10-config-schema.md`：配置文件完整 Schema
3. `05-roles-skills.md`：角色定义 + Skills 体系 + Prompt 模板
4. `02-adapter.md`：BaseAdapter + CodeBuddyAdapter（实现级）
5. `01-engine.md`：团队环境管理器（实现级）
6. `07-artifacts.md`：制品格式 + 目录结构 + 并发写策略
7. `06-memory-system.md`：三层记忆
8. `08-cost-control.md`：分档 + 成本 + 模型降级（采用 P5 权重）
9. `11-runtime-protocol.md`：运行时协议
10. `03-service-api.md`：REST API（架构级）
11. `04-web-panel.md`：Web 面板（架构级）
12. `09-hooks-security.md`：Hook + 安全（架构级）
