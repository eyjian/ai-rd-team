# SmartBookmark 预期产出

## 成员产出文件

```
.ai-rd-team/runtime/artifacts/
├── code/
│   ├── pyproject.toml                  # 可 pip install -e .
│   ├── smart_bookmark/
│   │   ├── __init__.py
│   │   ├── __main__.py                 # CLI 入口
│   │   ├── models.py                   # Bookmark dataclass
│   │   └── store.py                    # JSON 存储
│   └── tests/
│       ├── __init__.py
│       ├── test_store.py               # store.py 的测试
│       └── test_cli.py                 # argparse 测试
└── reports/
    └── report-developer.md
```

## 验收步骤

```bash
cd .ai-rd-team/runtime/artifacts/code

# 1. 装
pip install -e .

# 2. 测
pytest

# 3. 手工验证
bookmark add https://vuejs.org --tag vue --title "Vue 3 官网"
bookmark add https://go-kratos.dev --tag golang
bookmark list
bookmark list --tag vue
bookmark list --search "vue"
bookmark remove 2
bookmark open 1  # 打开浏览器
```

## 成员状态

最终 `.ai-rd-team/runtime/state/members/developer.yaml`：

```yaml
name: developer
role: developer
status: done         # ← 关键
current_task: "SmartBookmark 完成"
progress: "100%"
produced_files:
  - artifacts/code/pyproject.toml
  - artifacts/code/smart_bookmark/__main__.py
  - artifacts/code/smart_bookmark/store.py
  - artifacts/code/smart_bookmark/models.py
  - artifacts/code/tests/test_store.py
  - artifacts/code/tests/test_cli.py
  - artifacts/reports/report-developer.md
blocking_issues: []
```

## 成本预期

- RP 消耗：~60-150（Lite 档预算 150）
- 消息数：3-5 条
- 运行时长：5-10 分钟
