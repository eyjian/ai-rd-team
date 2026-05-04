---
type: memory
layer: agent.d
author: manual
created: 2026-05-04
updated: 2026-05-04
tags: [contracts]
estimated_tokens: 200
---

# SmartBookmark 接口契约

## CLI 子命令签名

```bash
bookmark add <url> [--tag TAG] [--title TITLE]
bookmark list [--tag TAG] [--search KEYWORD]
bookmark remove <id>
bookmark open <id>
```

## 数据模型

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class Bookmark:
    id: int           # 从 1 递增
    url: str
    title: str        # 未提供时从网页 <title> 抓取
    tags: list[str]
    created: str      # ISO 8601
```

## 存储文件

- 路径：`~/.smart-bookmark/bookmarks.json`
- 格式：`{"bookmarks": [<Bookmark dict>, ...], "next_id": int}`
- 写入要用原子替换（写 tmp 文件 + os.replace）

## 模块分工

| 模块 | 职责 |
|------|------|
| `smart_bookmark.models` | Bookmark dataclass |
| `smart_bookmark.store` | JSON 读写 + add/list/remove 实现 |
| `smart_bookmark.__main__` | argparse 子命令装配 |

## 测试要求

- `test_store.py`：add/list（带 tag 过滤）/ remove / next_id 自增
- `test_cli.py`：每个子命令的 argparse 解析（用 `parser.parse_args(...)`）
- 所有测试独立 `tmp_path` fixture，不污染 `~/.smart-bookmark/`
