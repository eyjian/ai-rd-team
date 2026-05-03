# 原型验证计划

> 5 项关键假设的详细验证设计

---

## 共同场景

**任务**：3 角色协作实现 Python 计算器

- `architect`（架构师）：输出接口签名和数据结构（`design-note.md`）
- `developer`（开发者）：实现 `calculator.py`
- `tester`（测试）：写 `test_calculator.py` 并执行

**对话顺序**（期望）：
```
user → architect: "实现一个支持 +/-/*// 的计算器"
architect → developer: "接口这样定义: def calc(op, a, b) -> float"
developer → architect: "除零怎么处理？"
architect → developer: "抛 ZeroDivisionError"
developer → tester: "我写完了，你帮忙测"
tester → developer: "发现 Bug: 浮点精度问题"
developer → tester: "已修复"
tester → main: "全部通过"
```

关键观察点：中间过程**不经过 main 转发**，成员间直接 P2P。

---

## P1：基础 Team 协作

### 假设
CodeBuddy 的 `team_create` + `task`(async) + `send_message` 能够支持"自主驱动"的多成员协作：
- 成员间直接 P2P 通信（不经过 main 转发）
- 成员能自主决定"做完就通知谁"
- 消息有正确的收件人路由
- 并行任务能真正并行

### 方法
**路径 A（真实实验）**：
1. 在当前会话中 `team_create(team_name="proto-p1")`
2. 依次 `task(subagent_name="code-explorer", name="architect"/"developer"/"tester", team_name="proto-p1", prompt="...")`
3. 通过 `send_message` 给 architect 发起任务
4. 观察成员间消息流，记录到 `01-basic-team/results/conversation-log.md`

**路径 B（Python 模拟）**：
- `simulated/team.py`：团队容器 + 成员注册表
- `simulated/member.py`：成员类（带收件箱）
- `simulated/mailbox.py`：消息路由
- 跑一个伪对话，证明架构可行

### 成功标准
- ✅ **必须**：至少 3 次 P2P 消息（A→B→C→A），不经过 main
- ✅ **必须**：每个成员独立完成自己的制品文件
- ✅ **必须**：团队运行结束时 `team_delete` 成功清理
- ⚠️ **关注**：每个 `task` 派发的启动延迟
- ⚠️ **关注**：消息从发出到被处理的延迟

### 失败后的应对
若 P2P 不可行（消息必须经过 main 转发），整个"自主驱动"方案需重新设计。备选方案：改为"显式调度 + 文件桥接"模式。

---

## P2：Skills 加载

### 假设
成员能读取 `.codebuddy/skills/` 或项目 `.ai-rd-team/skills/` 目录，按需加载并应用 Skills（如 Python 编码规范、pytest 使用指南）。

### 方法
**路径 A（真实实验）**：
1. 在 `02-skills-loading/skills/` 放 2 个测试 Skills：
   - `python-coding-style.md`：要求 `snake_case`、类型注解
   - `pytest-guide.md`：要求用 `pytest.fixture` 而非 `setUp`
2. 派发 developer 和 tester 时，prompt 中指明 skills 目录
3. 观察他们产出的代码是否符合 Skills 规范

**路径 B（Python 模拟）**：
- 简单实现一个 SkillsLoader 类，按需读取 `.md` 文件拼入 prompt

### 成功标准
- ✅ developer 产出的代码用 `snake_case` + 类型注解
- ✅ tester 产出的测试用 `pytest.fixture`
- ⚠️ 观察：Skills 是"自动应用"还是需要 prompt 显式引用

### 失败后的应对
若 Skills 无法"自动生效"，需要在成员 prompt 中显式注入 Skills 内容——记忆成本增加，需在成本章节加一项。

---

## P3：Web 面板通信方案选型

### 假设
Web 面板能够实时观察运行中 Team 的状态（成员消息、产出制品、资源消耗）。

### 方法
**不做真实实验**，而是技术选型对比：

| 方案 | 原理 | 优点 | 缺点 |
|------|------|------|------|
| A. 文件监听 | Web 后端 watch 制品/消息目录 | 简单、无耦合 | 实时性略差（轮询/inotify） |
| B. Socket 推送 | Team 成员写消息时推给 Web | 实时性好 | 需要成员 Adapter 支持 |
| C. 共享状态文件 | Team 和 Web 都读写 `state.json` | 折中 | 并发锁复杂 |
| D. HTTP 回调 | 成员通过 curl 调 Web API | 成员可控 | 成员要能执行命令 |

**路径 B（原型实现）**：
- `03-web-bridge/file-watch-approach.py`：用 `watchdog` 监听目录
- `03-web-bridge/simple-flask.py`：最小 Flask 服务器，展示监听效果

### 成功标准
输出 `decision.md`，给出第一期推荐方案 + 理由 + 未来演进路径。

---

## P4：制品并发写

### 假设
多个成员同时产出不同文件到共享目录，不会相互覆盖或损坏。

### 方法
**路径 A（真实实验）**：
- 让 developer 和 tester **同时**（或近乎同时）写各自文件
- 观察是否有冲突、乱序

**路径 B（Python 模拟）**：
- `04-artifacts/simulated/concurrent_write.py`：用多线程模拟 N 个成员并发写
- 测试场景：
  - 不同文件（期望无冲突）
  - 同一文件（期望有保护机制）
- 测试方案：临时文件 + 原子 rename vs 文件锁

### 成功标准
- ✅ 不同文件并发写：无冲突
- ✅ 同一文件并发写：有明确的冲突处理策略（最后一个覆盖 / 锁等待 / 报错）
- ✅ 产出"制品并发写安全方案"给 `07-artifacts.md` 参考

---

## P5：成本基线测量

### 假设
Resource Points 的权重公式（成员 10 / 消息 1 / 广播×人数 1 / 分钟 2 / 迭代 5）是合理的。

### 方法
在 P1-P4 的实验过程中**顺便**测量：

1. **成员启动成本**：`task` 派发一个成员时的 token 消耗
2. **消息成本**：一条 `send_message` 的 input+output token
3. **广播成本**：广播对 N 个成员的总消耗
4. **闲置成本**：成员等待时是否仍有 token 消耗
5. **制品产出成本**：产出 1 个 Markdown / 1 个 Python 文件的平均 token

记录到 `05-cost-baseline/results/token-counts.yaml`。

### 数据源
- CodeBuddy 如果能看到本次会话累计 token，手动记录
- 估算：按消息内容字符数 × 系数（后期校准）

### 成功标准
- 拿到 5 类操作的 token 参考值
- 给出 Resource Points 权重校准建议
- 写入 `05-cost-baseline/results/weight-calibration.md`

---

## 执行顺序与时间预估

| # | 步骤 | 形式 | 预估 token |
|---|-----|------|-----------|
| 1 | 目录骨架 + 共享工具 + experiment.md | 离线编写 | 0 |
| 2 | 各 P 的模拟实现（路径 B） | 离线编写 | 0 |
| 3 | P1 真实实验 | 真实派发 Team | ~30K |
| 4 | P2 真实实验（可与 P1 合并） | 真实派发 | ~10K |
| 5 | P4 真实实验（在 P1/P2 观察） | 真实派发 | ~5K |
| 6 | P3 技术选型 | 离线讨论 | 0 |
| 7 | P5 数据整理（贯穿 P1/P2/P4） | 离线汇总 | 0 |
| 8 | REPORT.md 汇总 | 离线编写 | 0 |

**合计真实 token**：约 45-55K，成本 ¥3-5（按 Sonnet 定价粗估）。

---

## 产出物清单

- `prototype/README.md`（本总览）
- `prototype/VERIFICATION-PLAN.md`（本计划）
- `prototype/shared/*.py`（共享工具）
- `prototype/0{1-5}-*/experiment.md`（5 份实验设计）
- `prototype/0{1-5}-*/simulated/*.py`（参考实现）
- `prototype/0{1-5}-*/results/*`（真实实验记录）
- `prototype/REPORT.md`（最终汇总报告）

---

## 风险与应对

| 风险 | 可能性 | 应对 |
|------|-------|------|
| P1 失败（不能 P2P） | 中 | 转入"显式调度"备选方案，头脑风暴重新做一轮 |
| Token 预估严重偏差 | 中 | 提前停止，改用更简单场景 |
| 派发的成员不遵循 prompt | 低 | 加强 prompt 约束，或改用 code-explorer 的系统 prompt 辅助 |
| CodeBuddy 工具行为与文档不符 | 中 | 实时记录观察，调整验证方法 |
