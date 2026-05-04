from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path
from typing import Sequence

from .models import Bookmark
from .store import (
    BookmarkNotFoundError,
    BookmarkStore,
    DEFAULT_STORE_FILE,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bookmark",
        description="smart-bookmark: a tiny CLI bookmark manager",
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=None,
        help=f"Path to bookmarks.json (default: {DEFAULT_STORE_FILE})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Add a bookmark")
    p_add.add_argument("url", help="URL to bookmark")
    p_add.add_argument("--tag", action="append", default=None,
                       help="Tag (can be specified multiple times)")
    p_add.add_argument("--title", default=None,
                       help="Title (fetched from URL if omitted)")

    p_list = sub.add_parser("list", help="List bookmarks")
    p_list.add_argument("--tag", default=None, help="Filter by tag")
    p_list.add_argument("--search", default=None,
                        help="Fuzzy search in title/url")

    p_remove = sub.add_parser("remove", help="Remove a bookmark by id")
    p_remove.add_argument("id", type=int, help="Bookmark id")

    p_open = sub.add_parser("open", help="Open a bookmark in browser")
    p_open.add_argument("id", type=int, help="Bookmark id")

    return parser


def _format_bookmark(b: Bookmark) -> str:
    tag_str = f" [{', '.join(b.tags)}]" if b.tags else ""
    return f"{b.id:>4}  {b.title}{tag_str}\n      {b.url}  ({b.created})"


def _cmd_add(store: BookmarkStore, args: argparse.Namespace) -> int:
    bookmark = store.add(url=args.url, title=args.title, tags=args.tag)
    print(f"Added #{bookmark.id}: {bookmark.title}")
    print(f"  {bookmark.url}")
    if bookmark.tags:
        print(f"  tags: {', '.join(bookmark.tags)}")
    return 0


def _cmd_list(store: BookmarkStore, args: argparse.Namespace) -> int:
    items = store.list(tag=args.tag, search=args.search)
    if not items:
        print("(no bookmarks)")
        return 0
    for b in items:
        print(_format_bookmark(b))
    return 0


def _cmd_remove(store: BookmarkStore, args: argparse.Namespace) -> int:
    try:
        b = store.remove(args.id)
    except BookmarkNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"Removed #{b.id}: {b.title}")
    return 0


def _cmd_open(store: BookmarkStore, args: argparse.Namespace) -> int:
    try:
        b = store.get(args.id)
    except BookmarkNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    webbrowser.open(b.url)
    print(f"Opening #{b.id}: {b.url}")
    return 0


_COMMANDS = {
    "add": _cmd_add,
    "list": _cmd_list,
    "remove": _cmd_remove,
    "open": _cmd_open,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = BookmarkStore(path=args.store)
    handler = _COMMANDS[args.command]
    return handler(store, args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
