# 示例 01：SmartBookmark（命令行书签工具）

**档位**：Lite  
**技术栈**：Python 3.10+（无依赖）  
**预计 RP**：120 上下  
**预计时长**：5-10 分钟  

## 目标产出

一个 CLI 工具 `bookmark`，支持：

- `bookmark add <url> [--tag TAG]` 添加书签
- `bookmark list [--tag TAG] [--search KEYWORD]` 列出书签
- `bookmark remove <id>` 删除
- `bookmark open <id>` 在浏览器打开

数据存在 `~/.smart-bookmark/bookmarks.json`。

## 预期文件树（成员产出后）

```
.ai-rd-team/runtime/artifacts/
├── code/
│   ├── smart_bookmark/
│   │   ├── __init__.py
│   │   ├── __main__.py       # CLI 入口（argparse）
│   │   ├── store.py          # JSON 存储
│   │   └── models.py         # Bookmark dataclass
│   ├── tests/
│   │   ├── test_store.py
│   │   └── test_cli.py
│   └── pyproject.toml        # 可安装配置
└── reports/
    └── report-developer.md
```

## 如何运行

```bash
cp -r examples/01-smart-bookmark ~/demo-smart-bookmark
cd ~/demo-smart-bookmark

# 启动 Web 面板（可选）
ai-rd-team serve --port 8765 &

# 在 CodeBuddy 会话中运行
ai-rd-team run "$(cat REQUIREMENT.md)"
```

## 成功验收

1. `.ai-rd-team/runtime/state/members/developer.yaml` 的 `status: done`
2. `artifacts/code/tests/test_store.py` 存在，且 `pytest` 全过
3. 可以实际把产出代码装起来用：
   ```bash
   cd .ai-rd-team/runtime/artifacts/code
   pip install -e .
   bookmark add https://vuejs.org --tag vue
   bookmark list
   ```

## Skills 配置

- developer 使用默认 Skills（`python-best-practices` + `pytest-guide`）

预填的 `memory/agent.d/` 说明了 CLI 接口契约和数据格式。

## 可能遇到的问题

- **成员产出路径错误**：Prompt 已指定 `artifacts/code/`，不应该写到项目根目录
- **测试未写**：检查 `memory/agent.d/cli-spec.md` 是否明确要求「每个模块都有对应测试」
