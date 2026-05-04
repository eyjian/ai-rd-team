from __future__ import annotations

import json
from pathlib import Path

import pytest

from smart_bookmark.models import Bookmark
from smart_bookmark.store import (
    BookmarkNotFoundError,
    BookmarkStore,
)


@pytest.fixture()
def store(tmp_path: Path) -> BookmarkStore:
    return BookmarkStore(path=tmp_path / "bookmarks.json")


def _fake_fetcher(url: str) -> str:
    return f"TITLE::{url}"


def test_add_creates_file_and_assigns_id_one(store: BookmarkStore) -> None:
    # Arrange
    assert not store.path.exists()

    # Act
    bm = store.add(
        url="https://a.example",
        title="A",
        tags=["x", "y"],
        now="2026-05-04T00:00:00+00:00",
    )

    # Assert
    assert isinstance(bm, Bookmark)
    assert bm.id == 1
    assert bm.url == "https://a.example"
    assert bm.title == "A"
    assert bm.tags == ("x", "y")
    assert store.path.exists()
    raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert raw["next_id"] == 2
    assert len(raw["bookmarks"]) == 1


def test_add_auto_increments_next_id(store: BookmarkStore) -> None:
    b1 = store.add(url="https://a.example", title="A")
    b2 = store.add(url="https://b.example", title="B")
    b3 = store.add(url="https://c.example", title="C")
    assert [b1.id, b2.id, b3.id] == [1, 2, 3]


def test_add_without_title_uses_fetcher(store: BookmarkStore) -> None:
    bm = store.add(
        url="https://a.example",
        title=None,
        title_fetcher=_fake_fetcher,
    )
    assert bm.title == "TITLE::https://a.example"


def test_add_empty_url_raises(store: BookmarkStore) -> None:
    with pytest.raises(ValueError, match="url must be"):
        store.add(url="  ", title="x")


def test_list_returns_all_when_no_filter(store: BookmarkStore) -> None:
    store.add(url="https://a.example", title="Alpha", tags=["news"])
    store.add(url="https://b.example", title="Beta", tags=["dev"])
    items = store.list()
    assert [b.title for b in items] == ["Alpha", "Beta"]


def test_list_filters_by_tag(store: BookmarkStore) -> None:
    store.add(url="https://a.example", title="Alpha", tags=["news", "fun"])
    store.add(url="https://b.example", title="Beta", tags=["dev"])
    store.add(url="https://c.example", title="Gamma", tags=["news"])
    items = store.list(tag="news")
    assert sorted(b.title for b in items) == ["Alpha", "Gamma"]


@pytest.mark.parametrize(
    "keyword, expected_titles",
    [
        ("alpha", ["Alpha"]),
        ("EXAMPLE", ["Alpha", "Beta"]),  # 大小写不敏感，两个 URL 都匹配
        ("zzz", []),
    ],
)
def test_list_search_case_insensitive(
    store: BookmarkStore,
    keyword: str,
    expected_titles: list[str],
) -> None:
    store.add(url="https://a.example", title="Alpha")
    store.add(url="https://b.example", title="Beta")
    items = store.list(search=keyword)
    assert sorted(b.title for b in items) == sorted(expected_titles)


def test_remove_deletes_record_and_keeps_next_id(store: BookmarkStore) -> None:
    store.add(url="https://a.example", title="A")
    store.add(url="https://b.example", title="B")

    removed = store.remove(1)
    assert removed.id == 1
    remaining = store.list()
    assert [b.id for b in remaining] == [2]

    # next_id 不回退，下一个新增应是 3
    b3 = store.add(url="https://c.example", title="C")
    assert b3.id == 3


def test_remove_unknown_id_raises(store: BookmarkStore) -> None:
    store.add(url="https://a.example", title="A")
    with pytest.raises(BookmarkNotFoundError, match="id=999"):
        store.remove(999)


def test_get_returns_bookmark(store: BookmarkStore) -> None:
    store.add(url="https://a.example", title="A")
    bm = store.get(1)
    assert bm.url == "https://a.example"


def test_get_missing_raises(store: BookmarkStore) -> None:
    with pytest.raises(BookmarkNotFoundError):
        store.get(42)


def test_load_missing_file_returns_empty(store: BookmarkStore) -> None:
    assert store.list() == []


def test_save_is_atomic_and_readable(store: BookmarkStore) -> None:
    store.add(url="https://a.example", title="中文标题", tags=["中文"])
    text = store.path.read_text(encoding="utf-8")
    # ensure_ascii=False 让中文可直接阅读
    assert "中文标题" in text
    assert "中文" in text
