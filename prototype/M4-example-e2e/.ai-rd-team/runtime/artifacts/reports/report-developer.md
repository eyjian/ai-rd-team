# Developer Report — smart-bookmark

## 实现思路

按 interface-contracts 分层，纯标准库实现：

| 模块 | 职责 |
|------|------|
| `smart_bookmark.models` | `Bookmark` 冻结 dataclass（id / url / title / tags / created），序列化用 `to_dict / from_dict` |
| `smart_bookmark.store` | JSON 读写 + 业务方法 `add / list / remove / get / all`；`fetch_title` 用 urllib 抓 `<title>`；原子写（`.tmp + os.replace + fsync`） |
| `smart_bookmark.__main__` | argparse 子命令装配 + dispatch 到 store；`open` 子命令使用 `webbrowser.open` |

### 关键设计点
- `next_id` 单调递增，删除不回退，与契约一致。
- `store.add(title=None)` 时走 `title_fetcher` 抓取，抓不到就 fallback 成 URL。测试里通过注入 `title_fetcher` 保持离线。
- 所有 I/O 走 `Path`；文件写入前 `mkdir(parents=True, exist_ok=True)`；不存在的 store 文件被视作空库。
- 默认路径 `~/.smart-bookmark/bookmarks.json`，CLI 全局支持 `--store` 覆盖，便于测试/多库。
- JSON 用 `indent=2, ensure_ascii=False`，中文可读。
- 异常：`BookmarkNotFoundError` 继承 `BookmarkError`；`add` 空 URL 抛 `ValueError`；`list` 模糊匹配大小写不敏感。

## 测试覆盖

运行结果：**28 passed in 2.16s**（pytest 9.0.3, Python 3.11.6）。

### `tests/test_store.py`（15 个）
- add：分配 id=1、自增、空 URL 抛 ValueError、无 title 时使用 fetcher
- list：无过滤 / tag 过滤 / search 模糊匹配（parametrize 3 个用例，含大小写、无命中）
- remove：删除后 next_id 不回退；未知 id 抛 `BookmarkNotFoundError`
- get：命中与未命中
- 载入缺失文件返回空；原子写后中文可读

### `tests/test_cli.py`（13 个）
- argparse：add / list / remove / open 四个子命令的解析，含多 tag、非整数 id 报错、缺失子命令报错、全局 `--store`
- main()：add+list、remove 不存在返回 1 并报错到 stderr、open 用 monkeypatch 验证 `webbrowser.open` 被调用、空库提示 `(no bookmarks)`

所有文件 I/O 测试都使用 pytest `tmp_path` fixture，不污染 `~/.smart-bookmark/`。

## 验收步骤

```bash
cd artifacts/code

# 1. 安装（可选）
pip install -e .

# 2. 跑测试
python3 -m pytest -v       # 期望 28 passed

# 3. 手验 CLI（用临时 store 避免污染）
STORE=$(mktemp -d)/bm.json
python3 -m smart_bookmark --store "$STORE" add https://example.com --title "Example" --tag news
python3 -m smart_bookmark --store "$STORE" list
python3 -m smart_bookmark --store "$STORE" list --tag news
python3 -m smart_bookmark --store "$STORE" list --search example
python3 -m smart_bookmark --store "$STORE" remove 1
```

## 产出清单

```
artifacts/code/
├── pyproject.toml
├── README.md
├── smart_bookmark/
│   ├── __init__.py
│   ├── __main__.py
│   ├── models.py
│   └── store.py
└── tests/
    ├── __init__.py
    ├── test_store.py
    └── test_cli.py
artifacts/reports/
└── report-developer.md
```
