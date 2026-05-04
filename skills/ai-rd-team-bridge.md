---
name: ai-rd-team-bridge
description: |
  ai-rd-team 引擎工具 Bridge。当 ai-rd-team 引擎运行中
  （即 .ai-rd-team/runtime/adapter-intents/ 目录存在且有 .json 文件时）
  自动激活，负责把引擎发出的"工具调用意图"转换为实际的 team_create / task /
  send_message / team_delete 调用，并把结果写回给引擎。
  关键词：ai-rd-team、bridge、adapter-intents、tool bridge、工具桥接。
---

# Skill: ai-rd-team Bridge（主 Agent 侧工具桥）

## 你的职责

ai-rd-team 引擎是一个 Python 进程，它无法直接调用 CodeBuddy 的工具
（`team_create` / `task` / `send_message` / `team_delete`）。

**你（主 Agent）就是代替它调工具的人。**

## 激活条件

以下任一条件满足时激活本 Skill：

1. 用户启动了 `ai-rd-team run` 或 `use skill ai-rd-team-launcher`
2. 你在工作目录下看到 `.ai-rd-team/runtime/adapter-intents/` 目录且里面有 `.json` 文件
3. 引擎日志（`.ai-rd-team/runtime/logs/engine.log`）中出现 `waiting for bridge`

## 工作流程

### 1. 轮询 intent 目录

```bash
# 每隔 1 秒轮询一次（用 bash 或 python -c）
ls .ai-rd-team/runtime/adapter-intents/*.json 2>/dev/null
```

如果没有文件，等 1 秒再查。**直到团队结束（`team_delete` intent 被处理）或用户手动停止**。

### 2. 读取 intent 文件

每个 intent 是一个 JSON 文件，格式：

```json
{
  "_id": "uuid-xxx",
  "_ts": "2026-05-04T10:00:00",
  "op": "team_create",
  "team_name": "ai-rd-team-abc12345",
  "description": "Run abc12345: 做一个计算器"
}
```

`op` 字段决定你要调用哪个工具。

### 3. 按 op 调用对应工具

| op | 你要做的事 |
|----|----------|
| `team_create` | 调用 `team_create(team_name=..., description=...)` |
| `task` | 调用 `task(subagent_name=..., description=..., prompt=..., name=..., team_name=..., mode=..., max_turns=...)` |
| `send_message` | 调用 `send_message(type=..., recipient=..., content=..., summary=..., request_id=..., approve=...)` |
| `team_delete` | 调用 `team_delete()` |
| `_probe` | 不调工具，返回当前可用工具名称列表 |
| `_version` | 不调工具，返回 CodeBuddy 版本字符串（若不知道返回 null） |

### 4. 写 result 文件

成功：

```json
{
  "data": {
    "平台返回的结果字段": "值"
  }
}
```

失败：

```json
{
  "error": "错误描述"
}
```

把这个 JSON 写到 `.ai-rd-team/runtime/adapter-results/{_id}.json`（文件名和 intent 的 `_id` 对应）。

**注意**：引擎读到 result 后会删除 intent 和 result 文件，你不需要清理。

### 5. 继续轮询下一个 intent

回到步骤 1。

## 每个 op 的具体要求

### op = `team_create`

- 调用 `team_create(team_name, description)`
- 返回：`{"data": {"team_name": "...", "platform_id": "..."}}`（`platform_id` 可从工具返回值中提取，或直接用 team_name）

### op = `task`

- intent 包含这些字段：`subagent_name`、`description`、`prompt`、`name`、`team_name`、`mode`（默认 `bypassPermissions`）、`max_turns`（可选）
- 调用 `task(subagent_name=..., description=..., prompt=..., name=..., team_name=..., mode=..., max_turns=...)`
- 返回：`{"data": {"name": "...", "platform_id": "..."}}`
- **重要**：`name` + `team_name` 同时传入才触发异步团队模式

### op = `send_message`

- intent 可能包含：`type`、`recipient`、`content`、`summary`、`request_id`、`approve`
- 只传 intent 中**非 null/非缺失**的字段给 `send_message`
- 返回：`{"data": {"ok": true}}`
- 5 种类型：
  - `message`：必须有 `recipient` + `content` + `summary`
  - `broadcast`：必须有 `content` + `summary`（无 `recipient`）
  - `shutdown_request`：必须有 `recipient`，`content` 可为空
  - `shutdown_response`：必须有 `request_id` + `approve`
  - `plan_approval_response`：必须有 `recipient` + `request_id` + `approve`

### op = `team_delete`

- 调用 `team_delete()`（无参数）
- 返回：`{"data": {"ok": true}}`
- 处理完后**本次 bridge 循环应终止**（引擎要求我们退出）

### op = `_probe`

- **不调工具**，直接返回你当前能看到的工具名：
  ```json
  {"data": {"available_tools": ["team_create", "team_delete", "task", "send_message"]}}
  ```
- 只列出 ai-rd-team 核心工具，不需要列全部

### op = `_version`

- **不调工具**，返回你知道的 CodeBuddy 版本（从 IDE 提示/环境变量/用户告知）
- 不知道就返回 `{"data": {"version": null}}`
- 不要因为不知道就报错

## 快捷实现：用一段 Python 脚本轮询

如果你觉得手动轮询太慢，可以用 bash 起一个 Python 脚本来加速查看。但**工具调用必须由你来做**（脚本无权调用）。

示例（仅辅助查看，不代替调工具）：

```bash
python3 -c "
import json, time, glob
while True:
    files = sorted(glob.glob('.ai-rd-team/runtime/adapter-intents/*.json'))
    if files:
        for f in files:
            data = json.loads(open(f).read())
            print(f'intent: {data[\"op\"]} id={data[\"_id\"][:8]}')
        break
    time.sleep(1)
"
```

看到 intent 后，**你根据 op 调用相应工具**。

## 错误处理

- 工具调用抛异常 → 写 `{"error": "异常信息"}`
- 文件不存在 / JSON 格式错 → 跳过，继续下一个
- 超过 5 分钟无新 intent → 可以询问用户是否结束

## 并发

- 同一时刻可能有多个 intent 文件（如引擎同时派发多个成员）
- 按文件修改时间（_ts）顺序处理
- 每个处理完再处理下一个（不需要真并行）

## 何时退出

- 看到 `op=team_delete` 的 intent 处理完
- 引擎 `logs/engine.log` 出现 `engine stopped`
- 用户明确说"停止 ai-rd-team"

## 与引擎的共识（只读参考）

- intent 目录：`.ai-rd-team/runtime/adapter-intents/`
- result 目录：`.ai-rd-team/runtime/adapter-results/`
- 文件命名：`{uuid}.json`（由引擎决定）
- 每个 intent 超时默认 60 秒（在 `config.adapter.bridge_timeout_seconds` 可调）
- 引擎读完 result 会自动删除两个文件

---

**最重要的一条**：你就是 Python 引擎的"手"。引擎告诉你做什么，你负责执行。
不要等引擎等太久，尽量在秒级响应 intent。
