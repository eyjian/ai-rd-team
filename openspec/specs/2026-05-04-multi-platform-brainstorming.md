# 头脑风暴：多平台 Adapter 架构决策

> 日期：2026-05-04
> 状态：⏸️ 暂停——M5 已归档，M6 方向选定为"多平台支持"但暂缓启动
> 触发：M5 `reduce-bridge-burden` 归档后讨论 M6 方向，候选为 "Trae Adapter"；调研 Trae 能力后发现根本架构冲突，决定暂停，待用户重新思考方向后再启动
> 关联：`openspec/specs/design/ROADMAP.md` §1.3 非目标（"多平台 Adapter v1.1 再做"）

## 1. 上下文

ai-rd-team 0.1.0a1（M4）完成 + M5 归档后，自然而然的下一步是"多平台支持"——让 ai-rd-team 不只能跑在 CodeBuddy（Claude-Opus-4.7），也能跑在 Trae / Cursor / Windsurf / Claude Desktop 等 AI IDE 上。

核心动机：
- ROADMAP §1.3 明确 "多平台 Adapter（Trae/Qoder，v1.1 再做）"
- M5 已证明 file-bridge 协议对底层模型无关（Claude-Opus-4.7 baseline 跑通，GLM-5.1 follow-up 待验）
- 下一个自然待证明的命题：file-bridge 协议对**宿主平台**也无关

但在为 Trae 写 propose 之前，必须先对齐架构方向，否则 propose 无从下笔。

## 2. 关键调研结论（Trae, 2026-05-04）

调研来源：
- https://docs.trae.ai/ide/agent?_lang=zh（官方）
- https://forum.trae.cn/t/topic/1189（官方中文社区 Sub Agent 使用帖）
- CSDN：Trae IDE 实操指南：MCP 协议与 Skill 能力协同开发全解析

| 维度 | CodeBuddy（当前） | Trae |
|------|------------------|------|
| Subagent 派生 | `task` 工具，任意成员可派生 | 只有 SOLO Coder（主控 agent）能派生自定义 agent，**单层** |
| Agent 间互通 | `send_message`（team 内 P2P） | **不支持**——星型拓扑，sub 之间不通信 |
| 配置格式 | Skill 文件 + YAML frontmatter | **图形化 UI 面板**，无文件格式 |
| 工具扩展 | Skills（文件式） | **MCP Server**（stdio/SSE/WebSocket） |
| 结果回传 | send_message | **共享文件系统** |

### 2.1 核心冲突

ai-rd-team 的核心设计主张是**"成员之间 P2P 互通，自主协作"**（README 首屏："不是工作流编排，是数字人团队自己把活干完"）。blog-api E2E 已证明：

- dev_2 主动与 architect 约定 module 名
- tester 主动用 app_stub.go 解耦 dev_2 的 wireApp
- 这些是**成员间 P2P 直接 send_message 驱动的自主协作**

**Trae 的星型拓扑直接破坏这一能力**。在 Trae 上原样实现 ai-rd-team，成员间协作将退化为"所有消息经主 Agent 转发"，既增加主 Agent 负担（M5 刚好减负），又丢失自主协作的卖点。

## 3. 候选方案（2026-05-04 列出）

### 方案 A：受限 Trae Adapter
- 只用 Trae 原生能力：SOLO Coder 派生 sub agent + 共享文件回传
- 放弃 P2P，改成"architect 中心式 orchestration"
- 优点：工作量小（3-5 天），快速验证"多平台概念"
- 缺点：**丢失核心卖点**；与 ai-rd-team 定位冲突

### 方案 B：MCP-based Adapter（轻量）
- 把 `team_create` / `task` / `send_message` 包装成 MCP Server 的 tool
- Trae / Cursor / Windsurf / Claude Desktop 等 MCP 客户端通过调用这些 tool 与 ai-rd-team 交互
- subagent 仍反向调回 IDE 的原生 Agent 能力（难点：MCP 标准不直接支持"tool 回调"）
- 优点：一次实现多端受益
- 缺点：C.1 的"反向回调"需要非标准 MCP 扩展，技术不确定性高

### 方案 C：MCP Server + ai-rd-team 自持 LLM（激进重构）
- 在 B 基础上更进一步：subagent **不再反向调 IDE**，而是 ai-rd-team 自己接入 LLM API（OpenAI-compatible / Anthropic / Gemini）
- ai-rd-team 从"寄生于 IDE"变成"独立服务"
- 优点：架构最干净；任何 IDE/CLI/ChatBot 都能触发 ai-rd-team 干活
- 缺点：**从 0.1 到 1.0 的架构跃迁**；需要处理 LLM API key / 成本 / 流控 / 模型市场等一系列新问题
- 影响范围：Adapter / Engine / Cost / Config 都要大改

### 方案 D：暂缓多平台，改做其他 M6
候选：Full 档 E2E（D1，Known Limitation）/ Memory 升级（B2）/ 成本校准（B1）/ Web 面板增强（C1）

## 4. 决策矩阵（待用户决定）

| 方案 | 工作量 | 技术风险 | 战略价值 | 回退成本 |
|------|-------|---------|---------|---------|
| A 受限 Trae Adapter | 🟢 3-5d | 🟢 低 | 🟡 打折（丢 P2P 卖点） | 🟢 低 |
| B MCP Adapter（反向回调） | 🟡 5-7d | 🔴 高（非标准 MCP 扩展） | 🟢 高（多平台） | 🟡 中 |
| C MCP + 自持 LLM | 🔴 10-15d | 🔴 高 | 🟢🟢 极高（架构解放） | 🔴 高（改不动退不回） |
| D 放弃多平台做别的 | - | - | - | - |

## 5. 暂停原因

用户在 2026-05-04 17:51 决定暂停 Trae 相关工作。合理判断：
- 选 A 则丢卖点，选 C 则相当于 0.2 版本重构，选 B 技术不确定性高
- 这个决策级别明显 > 一个普通 M6，应该在更清醒的状态下、有更充分材料时再做
- M5 刚归档、0.1.0a1 还没发 PyPI，现在不 push 多平台也不会错过窗口

## 6. 恢复时的入口

未来重启多平台工作时，从这里继续：

### 6.1 立刻可用的已调研信息（本文档 §2）
- Trae 能力清单（subagent / 工具 / 扩展机制）
- 与 CodeBuddy 的五维对比表
- 核心架构冲突点

### 6.2 决策清单（本文档 §3-4）
- 先定"保留 P2P"还是"接受退化"：这是方案 A vs B/C 的根本分水岭
- 若选 B/C，还要决定"subagent 运行在哪"：IDE 原生 Agent vs ai-rd-team 自持 LLM

### 6.3 可直接借用的参考
- Trae 社区的三种结果聚合模式（聚合文件 / 分区目录 / 主 Agent 轮询）
- MCP Server 配置示例（stdio / SSE / WebSocket）
- `trae-agent` 开源仓库：https://github.com/bytedance/trae-agent（可借鉴 CLI 层设计）

### 6.4 若恢复工作的第一步
建议按顺序：
1. 读本文档回顾架构冲突
2. 跟用户花 1 小时深度讨论方案 A/B/C 取舍
3. 选定后再 `use_skill openspec-propose` 写 change

## 7. 其他已列出但未处理的 M6 候选（留档）

从 2026-05-04 讨论中整理：

- **D1 Full 档 E2E**：Known Limitation "Full 档仅单测覆盖"。7 人团队真实 E2E，副产物是成本校准数据。工作量 4-6d。
- **B1 成本校准**：RP → token → USD，当前固定权重，Known Limitation。工作量 3-4d。
- **B2 Memory 升级**：向量检索 / 召回策略 / 语义去重，当前只有文件式三层。工作量 5-7d。
- **B4 Skills 深化**：Go+Kratos / Vue3 / 微信小程序 SOP 深化（CHANGELOG Planned）。工作量 3-5d。
- **C1 Web 面板增强**：成员消息发送 / 制品在线编辑（CHANGELOG Planned）。工作量 3-5d。
- **A3 PyPI 正式发布**：需用户账号，流程见 RELEASING.md。工作量 1-2d。

## 8. 小结

**本文档只是"暂停快照"**，不是最终决定。所有候选方案都保留开口。等用户准备好决策时，本文档是最有效率的"加载上下文"入口。
