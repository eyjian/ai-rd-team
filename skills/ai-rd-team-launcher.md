---
name: ai-rd-team-launcher
description: |
  ai-rd-team 启动入口。当用户表达要启动数字人研发团队的意图时激活。
  关键词：ai-rd-team、启动团队、数字人研发、研发团队、AI 研发、让一个团队帮我、
  启动一个研发团队做 xxx、用 ai-rd-team 实现 xxx。
---

# Skill: ai-rd-team 启动器

## 你的职责

帮用户把 ai-rd-team 跑起来。本 Skill 激活时，你需要：

1. 确认用户的需求和工作区
2. 启动 Python 引擎（`ai-rd-team run "..."`）
3. 激活 [ai-rd-team-bridge](./ai-rd-team-bridge.md) Skill 处理引擎产生的 intent
4. 监控运行过程并向用户反馈关键事件

## 激活条件

用户说出以下任一意图：

- "启动 ai-rd-team"
- "用 ai-rd-team 做 xxx"
- "让一个研发团队帮我做 xxx"
- "数字人团队做 xxx"

## 工作流程

### Step 1：确认需求

向用户确认：
- 你要做什么？（一句话描述）
- 当前工作区是 `cwd`（可直接用）还是指定目录？
- 运行档位？（Lite / Standard / Full，默认 Standard）

如果用户已经把需求讲清楚了，**不要反复确认**，直接进入 Step 2。

### Step 2：检查环境

```bash
# 1. 确认 ai-rd-team 已安装
ai-rd-team version

# 2. 检查 config.yaml 是否存在（不存在则首次运行会触发引导）
ls .ai-rd-team/config.yaml 2>/dev/null || echo "首次运行，会触发引导"
```

如果 `ai-rd-team` 命令找不到，提示用户：
```
需要先安装 ai-rd-team：
  pip install ai-rd-team
```

### Step 3：启动引擎

**重要**：启动前先告诉用户"我会启动引擎，然后激活 bridge Skill 来响应引擎的工具调用"。

用 `execute_command`（非交互式）启动引擎：

```bash
ai-rd-team run "<用户需求>" --mode <lite/standard/full> --no-onboarding 2>&1
```

注意：
- 带 `--no-onboarding` 避免在非交互环境卡住
- 若 config.yaml 不存在，用 `ai-rd-team init --yes` 先生成再 run
- 引擎会立刻开始派发成员，产生 intent 文件

### Step 4：激活 Bridge 处理 intent

**引擎启动的同时**，你要切换身份为 [ai-rd-team-bridge](./ai-rd-team-bridge.md)：

- 轮询 `.ai-rd-team/runtime/adapter-intents/`
- 读 intent → 调相应工具 → 写 result
- 直到 `team_delete` intent 出现

### Step 5：观察成员工作

成员被派发后会在自己的上下文中工作（异步）。你的职责：

1. 监控 `.ai-rd-team/runtime/events.jsonl`，向用户汇报关键事件：
   - `run_started`
   - `member_spawned`
   - `artifact_written`（M2+）
   - `member_status_changed`（M2+）

2. 成员之间互发消息时（通过 send_message 调用），你只负责投递，**不介入内容**。

3. 成员产出的文件在 `.ai-rd-team/runtime/artifacts/<role_dir>/`，可随时向用户展示。

### Step 6：结束

当以下任一条件发生，进入结束流程：

- 用户说"停止 ai-rd-team"
- 所有成员发消息给 `main` 说"我完成了"
- 引擎写出 `run_stopped` 事件

结束流程：

1. 向成员发 `shutdown_request`（通过 send_message）
2. 调用 `team_delete`
3. 向用户汇总产出：列出 `artifacts/` 下的所有文件
4. 展示 `runtime/events.jsonl` 的关键节点

## 与用户的沟通风格

- **行动先于请示**：用户说"做 xxx"，你就直接启动，不要反复确认细节
- **关键时刻通知**：成员派发完成、有人完成任务、需要用户决策时才打断用户
- **产出可见**：随时可以给用户看 `artifacts/` 下的文件列表和内容

## 典型对话示例

```
用户：用 ai-rd-team 做一个日报系统

你：好，我启动 ai-rd-team。默认 Standard 档（架构师 + 2 开发 + 测试），
    如果你觉得简单可以说"用 Lite 档"。
    
    [execute_command: ai-rd-team run "做一个日报系统" --mode standard --no-onboarding]

    ✅ 引擎已启动，run_id=abc12345，团队已派发：
    - architect（陈架构）
    - developer_1（林1号）
    - developer_2（林2号）
    - tester（赵小测）
    
    [切换到 bridge 模式，处理 intent 文件]

用户：（等一会）

你：[监测到多个 intent 并处理完毕]
    
    📝 架构师已产出：artifacts/design/spec-design.md
    💻 开发者正在实现接口...

...
```

## 失败处理

- **引擎启动失败**：展示错误信息，建议用户 `ai-rd-team config validate`
- **Bridge 超时**：可能是你处理 intent 太慢，加快节奏
- **成员卡住**：用 send_message 询问该成员当前状态

## 不要做的事

- ❌ 不要自己替成员工作（比如代架构师写设计）
- ❌ 不要反复询问用户进度（成员自主推进）
- ❌ 不要绕过引擎直接调工具（所有调用应来自 intent）
