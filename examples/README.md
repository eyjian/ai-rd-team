# ai-rd-team 演示案例

本目录提供 3 个不同规模的演示案例，覆盖 Lite / Standard 档位和不同技术栈。

## 示例索引

| 示例 | 档位 | 技术栈 | 预计运行 RP | 说明 |
|------|------|-------|-----------|------|
| [01-smart-bookmark](01-smart-bookmark/) | Lite | Python CLI | ~120 | 命令行书签管理工具 |
| [02-blog-api](02-blog-api/) | Standard | Go + Kratos | ~400 | 博客系统后端 REST API |
| [03-todo-mini](03-todo-mini/) | Standard | 微信小程序 | ~400 | TodoList 小程序 |
| [04-custom-skill](04-custom-skill/) | Standard | FastAPI + Pydantic v2 | ~350 | **演示自定义 Skill**：团队编码规范落地 AI 产出 |

## 如何运行任意示例

```bash
# 1. 把示例目录复制到你想工作的地方
cp -r examples/01-smart-bookmark ~/demo-smart-bookmark
cd ~/demo-smart-bookmark

# 2. （可选）启动 Web 面板观察
ai-rd-team serve --port 8765 &
open http://127.0.0.1:8765

# 3. 在 CodeBuddy 会话中启动
ai-rd-team run "$(cat REQUIREMENT.md)"
```

## 核心约定

每个示例目录包含：

- `README.md` - 示例说明、预期产出、可能遇到的问题
- `REQUIREMENT.md` - 喂给 `ai-rd-team run` 的需求描述（也可以用自然语言直接说）
- `.ai-rd-team/config.yaml` - Basic 配置
- `.ai-rd-team/config.advanced.yaml` - Advanced 配置（含 `adapter.bridge_timeout_seconds` + 角色 Skills 引用）
- `.ai-rd-team/memory/agent.d/tech-stack-selected.md` - 技术栈（必须用这个文件名，默认 memory_scope 才会加载）
- `.ai-rd-team/memory/agent.d/interface-contracts.md` - 接口契约（同上，约定俗成命名）

**关于 agent.d 文件命名**：默认 `memory_scope.agent_d` 是 `["tech-stack-selected", "interface-contracts", ...]`。自定义 agent.d 文件时，**必须用这些名字**，否则不会被自动加载。如需用别的名字，在 `config.advanced.yaml` 里显式配置 `roles.<role>.memory_scope.agent_d`。

## Skills 引用示例

四个案例分别演示了如何在 `config.advanced.yaml` 里给不同角色配置 Skills：

- **01 SmartBookmark**：developer 用默认 `python-best-practices + pytest-guide`
- **02 BlogAPI**：architect + developer + reviewer 都加载 `builtin:go-kratos-basics`
- **03 TodoMini**：developer 加载 `builtin:wxmini-basics`
- **04 CustomSkill**：混合引用 `builtin:xxx` + **项目自定义 Skill**（`fastapi-routers` / `team-python-style`），放在 `.ai-rd-team/skills/` 下

想把公司/项目专有编码规范落地给 AI 团队？**先看 [04-custom-skill](04-custom-skill/)**。

参考每个示例的 `config.advanced.yaml`。自定义 Skill 的完整编写指南见 [docs/04-skills.md](../docs/04-skills.md#完整示例给项目加一个自定义-skill)。
