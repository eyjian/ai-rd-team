# SmartBookmark 预期产出（M7 新布局）

## 成员产出文件

交付物直接在**项目根**，过程数据在 `.ai-rd-team/runtime/`：

```
<workspace>/                                # 项目根
├── pyproject.toml                          # 可 pip install -e .
├── smart_bookmark/
│   ├── __init__.py
│   ├── __main__.py                         # CLI 入口
│   ├── models.py                           # Bookmark dataclass
│   └── store.py                            # JSON 存储
├── tests/
│   ├── __init__.py
│   ├── test_store.py
│   └── test_cli.py
└── .ai-rd-team/
    └── runtime/
        ├── manifest.yaml                   # 权威索引（含所有 delivery + process）
        ├── reports/
        │   └── report-developer.md         # 开发者总结（过程）
        └── state/members/developer.yaml
```

（注：Python 默认 `ProjectLayout` 的 `code_dirs={"main": "src"}`，但只有一个主模块 `smart_bookmark/` 时，实际更常见的是直接落项目根。架构师会按项目特点调整；最新行为以 `manifest.yaml` 里的 `path` 为准。）

## 验收步骤

```bash
cd <workspace>

# 1. 装（代码已经就在项目根）
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
produced_files:          # 相对项目根
  - pyproject.toml
  - smart_bookmark/__main__.py
  - smart_bookmark/store.py
  - smart_bookmark/models.py
  - tests/test_store.py
  - tests/test_cli.py
  - .ai-rd-team/runtime/reports/report-developer.md
blocking_issues: []
```

## 成本预期

- RP 消耗：~60-150（Lite 档预算 150）
- 消息数：3-5 条
- 运行时长：5-10 分钟
