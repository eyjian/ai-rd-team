# 快速上手

> 读这一份文档就能从零跑通。其他文档（配置 / 角色 / Skills / 成本等）是"深入"的，不是"上手"的。

## 前置要求

- **Python 3.10+**（建议用 venv 隔离）
- **CodeBuddy IDE**（首期仅支持；Trae / Cursor / Windsurf 等平台在 roadmap 上，见 [multi-platform-brainstorming](../openspec/specs/2026-05-04-multi-platform-brainstorming.md)）
- **一个你想让 AI 团队干活的工作区目录**

---

## 第 1 步：安装 Python 包

ai-rd-team 当前处于 **beta 阶段（`0.1.0b1`）**，**尚未发布到 PyPI**。从源码或本地 wheel 安装，任选其一。

### 方式 1：可编辑安装（推荐开发 / 调试）

```bash
git clone https://github.com/eyjian/ai-rd-team.git
cd ai-rd-team
pip install -e ".[dev]"
```

源码改动立即生效；`[dev]` 还带 pytest / ruff 等开发工具。

### 方式 2：从源码直接安装（推荐纯使用）

```bash
git clone https://github.com/eyjian/ai-rd-team.git
cd ai-rd-team
pip install .
```

### 方式 3：从预构建 wheel 安装

如果你已经拿到了 wheel 文件（仓库 `dist/` 目录）：

```bash
pip install /path/to/ai-rd-team/dist/ai_rd_team-0.1.0b1-py3-none-any.whl
```

也可以自己构建：

```bash
cd ai-rd-team
pip install -e ".[publish]"
rm -rf dist/ && python -m build
pip install dist/ai_rd_team-*.whl
```

### 验证装成功

```bash
ai-rd-team version    # → ai-rd-team v0.1.0b1
ai-rd-team --help     # 应看到 6 个子命令：version / skills / init / serve / run / config
```

> ❗ 如果 `command not found`：通常是 `pip` 装到别的 Python 了。`which python3 && which pip && which ai-rd-team` 对照路径是否同源。

---

## 第 2 步：把 Skill 安装到 CodeBuddy（只做一次）

ai-rd-team 是"嵌入 CodeBuddy 的 Python 引擎"。主 Agent 需要两个 Skill 才能识别 `ai-rd-team run` 命令并应答 bridge intent：

- `ai-rd-team-launcher` — 入口引导（用户说"启动 ai-rd-team"时激活）
- `ai-rd-team-bridge` — Bridge 监听（Python 引擎产生 intent 时应答）

仓库本身就是一个**标准 CodeBuddy marketplace**（含 `.codebuddy-plugin/marketplace.json` + `plugins/ai-rd-team/` 结构），所以安装非常直接。有两种方式，**推荐方式 1**。

### 方式 1：链接为 Marketplace（推荐）

让 CodeBuddy 把整个仓库识别为一个 marketplace（和 `codebuddy-plugins-official` / `superpowers-marketplace` 一样）：

```bash
# 先看一眼命令（工具会告诉你本机的正确路径）
ai-rd-team skills

# 然后执行（替换 /path/to/ai-rd-team 为你的实际路径）
mkdir -p ~/.codebuddy/plugins/marketplaces/
ln -s /path/to/ai-rd-team ~/.codebuddy/plugins/marketplaces/ai-rd-team-marketplace
```

**重启 CodeBuddy 后**：

1. 打开 IDE 右侧「插件」面板 → 看到 `ai-rd-team-marketplace`
2. 找到 `ai-rd-team` 插件，点「安装」
3. 弹出三种安装范围，选其一：
   - **为您安装（用户范围）** — 仅本人，跨所有项目可用
   - **为此仓库所有协作者安装（项目范围）** — 和协作者共享（进 git）
   - **仅为您在此仓库安装（本地范围）** — 仅本人在此项目可用

装完后在任意 CodeBuddy 会话里说「启动 ai-rd-team 做 xxx」即激活。

> 💡 为什么推荐方式 1：**代码更新即生效**（软链直接指向 git 仓库），升级 ai-rd-team 不需要再拷一次。且能享受 CodeBuddy 原生插件管理（卸载 / 禁用 / 版本切换）。

### 方式 2：手动拷贝为用户级 Skill（备用）

如果你的 CodeBuddy 版本不支持插件管理 UI（老版本）或只想试一下：

```bash
mkdir -p ~/.codebuddy/skills/
cp -r /path/to/ai-rd-team/plugins/ai-rd-team/skills/* ~/.codebuddy/skills/
```

这会把两个 Skill（目录+`SKILL.md` 结构）**整份拷**到用户级 Skill 目录。重启 CodeBuddy，Skill 自动生效。

缺点：
- 代码更新后 Skill 不会自动更新，要手动重新 `cp -r`
- 无法通过 CodeBuddy UI 管理（只能手动 `rm -rf ~/.codebuddy/skills/ai-rd-team-*`）
- 无法切换"用户 / 项目 / 本地"安装范围

### 验证 Skill 已加载

**重启 CodeBuddy 后**：

```
你：有哪些可用的 skill？
```

应在列表里看到 `ai-rd-team-launcher` 和 `ai-rd-team-bridge`。

或者直接在 CodeBuddy 对话里输入：

```
用 ai-rd-team 做一个 hello world
```

如果 launcher 被激活，你会看到 CodeBuddy 回复里带着"启动 ai-rd-team Python 引擎"字样的回应。

> ❗ **如果看不到**：
> - 方式 1：检查软链是否指向含 `.codebuddy-plugin/marketplace.json` 的目录；看 CodeBuddy 插件面板是否列出了这个 marketplace
> - 方式 2：检查 `ls ~/.codebuddy/skills/ai-rd-team-launcher/SKILL.md` 是否真的存在
> - 两种方式都要**重启 CodeBuddy** 才生效，不会热加载

---

## 第 3 步：准备一个工作区（用 example 最快）

```bash
cp -r /path/to/ai-rd-team/examples/01-smart-bookmark ~/demo
cd ~/demo
ls -a
```

目录结构：

```
~/demo/
├── README.md                         # 示例说明
├── REQUIREMENT.md                    # 需求描述（会传给 team）
├── EXPECTED_OUTPUTS.md               # 预期产物
└── .ai-rd-team/
    ├── config.yaml                   # 已预填 Lite 档
    ├── config.advanced.yaml          # 已预填 bridge_timeout 等高级项
    └── memory/agent.d/               # 已预填背景知识
        ├── tech-stack-selected.md
        └── interface-contracts.md
```

三个 example 可选：

| example | 档位 | 成员 | 预计耗时 | 预算 |
|---------|------|------|---------|------|
| `01-smart-bookmark` | Lite | 1 developer | 5-10 min | ~120 RP |
| `02-blog-api` | Standard | 4（architect + dev × 2 + tester） | 10-15 min | ~300 RP |
| `03-todo-mini` | Standard | 4（微信小程序） | 10-15 min | ~300 RP |

---

## 第 4 步：启动 Web 面板（可选但强烈推荐）

面板是只读观测台：成员状态 / 消息流 / 成本 / 制品 / Pending bridge intents。启动它能让你清楚看到团队在干什么，不用盯命令行。

```bash
cd ~/demo
ai-rd-team serve --port 8765 &

# 浏览器打开 http://127.0.0.1:8765
# 首次访问若没 config.yaml 会弹 3 步引导（example 已自带 config，不会弹）
```

> ⚠️ Web 面板只监听 `127.0.0.1`，**不要暴露公网**（当前版本无鉴权）。

---

## 第 5 步：在 CodeBuddy 会话里启动团队

**这一步必须在 CodeBuddy IDE 里操作**，不是终端：

1. 在 CodeBuddy 里打开 `~/demo` 作为工作区
2. 在 CodeBuddy 对话里输入：

   ```
   ai-rd-team run "$(cat REQUIREMENT.md)"
   ```

3. 主 Agent（加载了 `ai-rd-team-launcher` Skill）会：
   - 启动 Python 引擎（后台进程）
   - 调用 `team_create` 创建团队
   - 调用 `task` 派发成员（注入 Skills + Memory）
   - 通过 `send_message` 投递启动消息
   - 切换到 `ai-rd-team-bridge` Skill 监听 intent

4. 成员们以 **CodeBuddy subagent 形式**并行工作，你可以：
   - 在 **Web 面板**实时观察
   - 在 **CodeBuddy IDE** 里看 subagent 的消息

---

## 第 6 步：观察 + 偶尔介入

### 观察点（Web 面板）

| 页面 | 看什么 |
|------|-------|
| 总览 | 状态 / 成员数 / 近期事件 / **Pending bridge intents** 卡片 |
| 团队 | 各成员 status / current_task / produced_files |
| 消息 | 成员间 P2P 消息流 |
| 制品 | `.ai-rd-team/runtime/artifacts/` 实时文件树 |
| 成本 | RP 消耗分布（spawn / message / broadcast / runtime） |

**重点关注 "Pending bridge intents" 卡片**：
- ✅ 绿色 "无需干预" = AutoBridgeResponder 自动处理中，你什么都不用做
- ⚠️ amber 高亮 = 有 intent 需要主 Agent 应答，卡片会显示要调什么工具（如 `task(name=developer, ...)`）

### 需要手动应答的情形（M5 后只剩 4 类）

| intent op | 含义 | 你在 CodeBuddy 里要调的工具 |
|-----------|------|---------------------------|
| `team_create` | 创建团队 | `team_create(...)` |
| `task` | 派发成员 | `task(name=..., team_name=..., ...)` |
| `send_message type=message` | 投递消息 | `send_message(recipient=..., content=..., ...)` |
| `team_delete` | 清理团队 | `team_delete(...)` |

其他 intent（`_version` / `_probe` / `shutdown_*` / `broadcast`）由 AutoBridgeResponder 自动应答，**不用你管**。详见 [bridge 与 auto-responder](06-bridge-and-auto-responder.md)。

---

## 第 7 步：验证产出

成员完成后，runtime 目录会有所有产物：

```bash
cd ~/demo/.ai-rd-team/runtime

# 产出的代码文件
ls artifacts/

# 事件流
tail -20 events.jsonl

# 最终成本
cat cost-summary.yaml

# 各成员终态
ls state/members/
```

以 `01-smart-bookmark` 为例，产物可直接装来跑：

```bash
cd ~/demo/.ai-rd-team/runtime/artifacts/code
pip install -e .
pytest
bookmark add https://vuejs.org --tag vue
bookmark list
```

---

## ⚠️ 常见第一次坑

| 症状 | 原因 | 解决 |
|------|-----|------|
| `ai-rd-team: command not found` | pip 装到别的 Python 了 / venv 没激活 | `which python3 && which ai-rd-team` 核对路径 |
| CodeBuddy 里不认 `ai-rd-team run` 命令 | 没装 Skill 或没重启 CodeBuddy | 重做第 2 步，重启 CodeBuddy |
| 成员一直不启动（10 分钟无进展） | 主 Agent 没监听 bridge | 看 Web 面板 Pending 卡片，按提示手动调工具；或检查 `ai-rd-team-bridge` Skill 是否激活 |
| `config.yaml not found` | 当前目录不是工作区 | `cd` 到有 `.ai-rd-team/config.yaml` 的目录 |
| bridge timeout | 主 Agent 响应慢（CodeBuddy 通常 60-90 秒/次） | `config.advanced.yaml` 加 `adapter.bridge_timeout_seconds: 300`；examples 已预设 |
| 装过但导入报错 `ModuleNotFoundError` | wheel 可能没打全非 .py 资源 | 确认装的是 `0.1.0b1` 或更新版；`pyproject.toml` 已显式 include preset/skills/html |

更多已知限制见 [CHANGELOG.md](../CHANGELOG.md) 的 "Known Limitations"。

---

## 🚀 最短路径（5 步一口气跑通）

```bash
# 1. 克隆 + 装
git clone https://github.com/eyjian/ai-rd-team.git && cd ai-rd-team && pip install .

# 2. 装为 CodeBuddy marketplace（链路最短的方式）
mkdir -p ~/.codebuddy/plugins/marketplaces/
ln -sfn $(python3 -c "import ai_rd_team; print(ai_rd_team.codebuddy_marketplace_dir())") \
        ~/.codebuddy/plugins/marketplaces/ai-rd-team-marketplace
# ↓ 重启 CodeBuddy → 插件面板 → ai-rd-team → 安装

# 3. 准备工作区
cp -r examples/01-smart-bookmark ~/try && cd ~/try

# 4. 开面板
ai-rd-team serve --port 8765 &

# 5. 在 CodeBuddy 里打开 ~/try，对话框输入：
#    ai-rd-team run "$(cat REQUIREMENT.md)"
```

---

## 下一步

- **加新功能**：改 `examples/01-smart-bookmark/REQUIREMENT.md`，让 AI 团队按新需求迭代
- **试更复杂的**：`examples/02-blog-api`（Standard 档，4 成员并行 Go+Kratos）
- **自定义项目**：读 [配置详解](02-configuration.md) 和 [角色与团队](03-roles-and-team.md)
- **了解 M5 bridge 机制**：[bridge 与 auto-responder](06-bridge-and-auto-responder.md)
