# 快速上手

## 前置要求

- Python 3.10+
- CodeBuddy IDE（首期支持，后续会加 Trae / Qoder）

## 安装

```bash
git clone https://github.com/eyjian/ai-rd-team.git
cd ai-rd-team
pip install -e ".[dev]"

# 验证
ai-rd-team version
```

## 跑第一个示例

用 `examples/01-smart-bookmark`（Lite 档、~120 RP、5-10 分钟）：

```bash
cp -r examples/01-smart-bookmark ~/demo
cd ~/demo
```

这时目录结构：
```
~/demo/
├── README.md
├── REQUIREMENT.md
├── EXPECTED_OUTPUTS.md
└── .ai-rd-team/
    ├── config.yaml                    # 已预填 Lite 档
    └── memory/agent.d/                # 已预填背景知识
        ├── tech-stack.md
        └── cli-spec.md
```

### 启动 Web 面板（推荐，方便观察）

```bash
ai-rd-team serve --port 8765 &
open http://127.0.0.1:8765
```

### 在 CodeBuddy 会话中启动

```
在 CodeBuddy 里打开 ~/demo 作为工作区，然后运行：

ai-rd-team run "$(cat REQUIREMENT.md)"
```

CodeBuddy 的主 Agent 会：
1. 启动 ai-rd-team Python 引擎
2. 调用 `team_create` 创建团队
3. 调用 `task` 派发 developer 成员（注入 Skills + Memory）
4. 通过 `send_message` 投递启动消息
5. 成员自主工作，产出文件到 `.ai-rd-team/runtime/artifacts/`
6. 主 Agent 响应 Engine 的 shutdown / team_delete 请求结束

整个过程你只需在 Web 面板观察。

## 观察点

### 面板 > 总览页

```
状态: running
成员数: 1
需求: 做一个叫 smart-bookmark 的命令行书签管理工具...
最近事件:
  - run_starting ...
  - member_spawned developer ...
  - run_started ...
```

### 面板 > 团队页

```
name      | role      | status   | current_task                | produced_files
developer | developer | working  | 实现 CLI store 模块          | []
```

当 `status` 变成 `done` 且 `produced_files` 开始有内容，说明成员开始产出了。

### 面板 > 制品页

实时列出 `.ai-rd-team/runtime/artifacts/` 下的所有文件，点击可查看内容。

### 面板 > 成本页

实时显示 RP 消耗（spawn / message / broadcast / runtime）。

## 验证产出

成员完成后：

```bash
cd ~/demo/.ai-rd-team/runtime/artifacts/code

# 装
pip install -e .

# 测
pytest

# 用
bookmark add https://vuejs.org --tag vue
bookmark list
```

## 下一步

- 修改 `examples/01-smart-bookmark/REQUIREMENT.md`，让 AI 团队加新功能
- 试试 `examples/02-blog-api`（Standard 档，4 成员并行）
- 读 [配置详解](02-configuration.md) 自定义你的项目
