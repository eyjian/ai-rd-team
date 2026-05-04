from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError

from .models import Bookmark


DEFAULT_STORE_DIR = Path.home() / ".smart-bookmark"
DEFAULT_STORE_FILE = DEFAULT_STORE_DIR / "bookmarks.json"

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


class BookmarkError(Exception):
    """Base error for bookmark operations."""


class BookmarkNotFoundError(BookmarkError):
    """Raised when a bookmark id cannot be found."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def fetch_title(url: str, timeout: float = 3.0) -> str:
    """Best-effort fetch of <title> from a URL. Returns url itself on failure."""
    try:
        req = urlrequest.Request(
            url,
            headers={"User-Agent": "smart-bookmark/0.1"},
        )
        with urlrequest.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read(65536)
        try:
            text = raw.decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            return url
        m = _TITLE_RE.search(text)
        if m:
            title = m.group(1).strip()
            # 折叠空白
            title = re.sub(r"\s+", " ", title)
            if title:
                return title
    except (URLError, HTTPError, TimeoutError, ValueError, OSError):
        return url
    return url


class BookmarkStore:
    """JSON-backed bookmark store with atomic writes."""

    def __init__(self, path: Path | None = None) -> None:
        self.path: Path = Path(path) if path is not None else DEFAULT_STORE_FILE

    # ---------- I/O ----------

    def _load(self) -> dict:
        if not self.path.exists():
            return {"bookmarks": [], "next_id": 1}
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise BookmarkError(f"Corrupted store file: {self.path}: {e}") from e
        if not isinstance(data, dict):
            raise BookmarkError(f"Invalid store format: {self.path}")
        data.setdefault("bookmarks", [])
        data.setdefault("next_id", 1)
        return data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    # ---------- API ----------

    def all(self) -> list[Bookmark]:
        data = self._load()
        return [Bookmark.from_dict(b) for b in data["bookmarks"]]

    def add(
        self,
        url: str,
        title: str | None = None,
        tags: Iterable[str] | None = None,
        *,
        title_fetcher=None,
        now: str | None = None,
    ) -> Bookmark:
        if not url or not url.strip():
            raise ValueError("url must be a non-empty string")
        url = url.strip()
        tag_tuple: tuple[str, ...] = tuple(t.strip() for t in (tags or ()) if t.strip())

        if title is None or not title.strip():
            fetcher = title_fetcher if title_fetcher is not None else fetch_title
            title = fetcher(url)
        title = title.strip() or url

        data = self._load()
        new_id = int(data["next_id"])
        bookmark = Bookmark(
            id=new_id,
            url=url,
            title=title,
            tags=tag_tuple,
            created=now if now is not None else _now_iso(),
        )
        data["bookmarks"].append(bookmark.to_dict())
        data["next_id"] = new_id + 1
        self._save(data)
        return bookmark

    def list(
        self,
        tag: str | None = None,
        search: str | None = None,
    ) -> list[Bookmark]:
        items = self.all()
        if tag:
            t = tag.strip()
            items = [b for b in items if t in b.tags]
        if search:
            kw = search.strip().lower()
            if kw:
                items = [
                    b for b in items
                    if kw in b.title.lower() or kw in b.url.lower()
                ]
        return items

    def get(self, bookmark_id: int) -> Bookmark:
        for b in self.all():
            if b.id == bookmark_id:
                return b
        raise BookmarkNotFoundError(f"bookmark id={bookmark_id} not found")

    def remove(self, bookmark_id: int) -> Bookmark:
        data = self._load()
        matched: dict | None = None
        kept: list[dict] = []
        for raw in data["bookmarks"]:
            if int(raw["id"]) == bookmark_id and matched is None:
                matched = raw
            else:
                kept.append(raw)
        if matched is None:
            raise BookmarkNotFoundError(f"bookmark id={bookmark_id} not found")
        data["bookmarks"] = kept
        self._save(data)
        return Bookmark.from_dict(matched)
