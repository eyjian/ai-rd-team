# ai-rd-team 演示案例

本目录提供 3 个不同规模的演示案例，覆盖 Lite / Standard 档位和不同技术栈。

## 示例索引

| 示例 | 档位 | 技术栈 | 预计运行 RP | 说明 |
|------|------|-------|-----------|------|
| [01-smart-bookmark](01-smart-bookmark/) | Lite | Python CLI | ~120 | 命令行书签管理工具 |
| [02-blog-api](02-blog-api/) | Standard | Go + Kratos | ~400 | 博客系统后端 REST API |
| [03-todo-mini](03-todo-mini/) | Standard | 微信小程序 | ~400 | TodoList 小程序 |

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
- `.ai-rd-team/config.advanced.yaml` - Advanced 配置（含 Skills 引用）
- `.ai-rd-team/memory/agent.d/*.md` - 预填的背景记忆
- `EXPECTED_OUTPUTS.md` - 成员应该产出什么

## Skills 引用示例

三个案例分别演示了如何在 `config.advanced.yaml` 里给不同角色配置 Skills：

- **SmartBookmark**：developer 用 `python-best-practices + pytest-guide`（默认即可）
- **BlogAPI**：architect + developer + reviewer 都加载 `go-kratos-basics`
- **TodoMini**：developer 加载 `wxmini-basics`

参考每个示例的 `config.advanced.yaml`。
