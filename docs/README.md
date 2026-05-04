# ai-rd-team 使用手册

从零上手 ai-rd-team 的面向用户文档。比起 `openspec/specs/design/` 下的**实现级设计文档**（面向贡献者），这里更适合"我只想用起来"。

## 目录

1. [快速上手](01-getting-started.md) — 5 分钟跑通第一个示例
2. [配置详解](02-configuration.md) — Basic + Advanced 两层配置怎么写
3. [角色与团队](03-roles-and-team.md) — 7 角色、档位、可伸缩、升档
4. [Skills 指南](04-skills.md) — 内置 Skills、自定义 Skills、如何影响成员行为
5. [成本控制](05-cost-control.md) — RP 计量、预算、smart_pause、模型降级
6. [Bridge 与 Auto-Responder](06-bridge-and-auto-responder.md)（M5+）— E2E 主 Agent 只需应答 4 类 intent

其他主题（记忆、Hook、CLI）暂参考：

- **记忆系统** → `openspec/specs/design/06-memory-system.md`
- **Hook 与安全** → `openspec/specs/design/09-hooks-security.md`
- **Web 面板** → `openspec/specs/design/04-web-panel.md` + `openspec/specs/design/03-service-api.md`
- **CLI 完整参考** → `ai-rd-team --help` 和各子命令的 `--help`

## 示例

不想读文档？直接看 [examples/](../examples/) 三个真实案例。

## Follow-ups（待办 / 独立验证）

[`follow-ups/`](follow-ups/) 目录记录那些**从某个 openspec change 拆出来、独立推进**的小任务——通常是纯验证、无代码变更、无 spec delta，因此不走 openspec change 体系：

- [GLM-5.1 兼容性基线 E2E](follow-ups/GLM51-compat.md) — 从 M5 `reduce-bridge-burden` 6.4/6.5 拆出，等待在 GLM-5.1 会话中执行。

## 设计文档（进阶）

如果你想贡献代码或深入原理，请阅读 [openspec/specs/design/](../openspec/specs/design/) 下的 12 份详细设计文档。
