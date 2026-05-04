# ai-rd-team Skills 包

本目录包含 ai-rd-team 为 CodeBuddy（以及未来 Trae / Qoder）提供的 Skill 文件。

## 两种使用方式

### 方式 A：作为 Python 包 + Skill 组合（推荐）

```bash
# 1. 安装 Python 包
pip install ai-rd-team

# 2. 把 Skills 目录链接到 CodeBuddy 本地 Skills
#    （或复制，取决于 CodeBuddy 版本）
ln -s $(python -c "import ai_rd_team, pathlib; print(pathlib.Path(ai_rd_team.__file__).parent.parent.parent / 'skills')") \
      ~/.codebuddy/plugins/marketplaces/local/skills/ai-rd-team

# 3. 在 CodeBuddy 会话中使用
# 用户：use skill ai-rd-team-launcher
# 用户：做一个 TodoList 小程序
```

### 方式 B：纯 Skill 安装（未来，待 CodeBuddy 支持 bundled Python）

```
codebuddy skill install ai-rd-team
```

## Skills 清单

| Skill | 用途 | 由谁触发 |
|-------|-----|---------|
| `ai-rd-team-launcher.md` | 入口引导：用户说"启动 ai-rd-team" 时激活 | 用户意图 |
| `ai-rd-team-bridge.md` | Bridge 监听：引擎启动后自动处理 intent 文件 | 引擎启动 |

## Skill 与 Python 引擎的关系

```
用户
  │ "启动 ai-rd-team 做 xxx"
  ▼
launcher.md（指引主 Agent）
  │ 启动 Python 进程：ai-rd-team run "..."
  ▼
引擎初始化
  │ Bridge 写 intent：runtime/adapter-intents/{uuid}.json
  ▼
bridge.md（监听 Skill）
  │ 主 Agent 读 intent → 调 team_create/task/send_message → 写 result
  ▼
引擎读 result → 业务层继续
```

**关键**：Python 引擎不能直接调 CodeBuddy 工具，必须由主 Agent 承担"工具调用者"角色。
