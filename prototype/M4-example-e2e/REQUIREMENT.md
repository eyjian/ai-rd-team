做一个叫 smart-bookmark 的命令行书签管理工具。

功能需求：
1. bookmark add <url> [--tag TAG] [--title TITLE]
   - URL 必填，tag 和 title 可选（title 未提供时从 URL 的网页 title 标签抓取，抓不到就用 URL 本身）
2. bookmark list [--tag TAG] [--search KEYWORD]
   - 无参数列全部；--tag 按标签过滤；--search 按标题/URL 模糊搜索
3. bookmark remove <id>
   - 按 ID 删除（ID 就是数字序号，从 1 开始）
4. bookmark open <id>
   - 调 webbrowser 模块在浏览器打开

数据持久化：
- 存 ~/.smart-bookmark/bookmarks.json
- 每条记录：{id: int, url: str, title: str, tags: list[str], created: "ISO 8601"}

技术要求：
- Python 3.10+，标准库即可（argparse + json + dataclasses + urllib）
- 用 pyproject.toml 让它可以 pip install -e .
- 入口 smart_bookmark/__main__.py（支持 python -m smart_bookmark）
- 用 argparse 分子命令
- pytest 覆盖 store.py 的 add/list/remove，以及 CLI argparse 解析

非目标：
- 不需要云同步
- 不需要浏览器插件
- 不需要 GUI
