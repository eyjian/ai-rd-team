from __future__ import annotations

from pathlib import Path

import pytest

from smart_bookmark.__main__ import build_parser, main


@pytest.fixture()
def parser():
    return build_parser()


# ----------------- argparse 解析 -----------------

def test_parse_add_minimal(parser) -> None:
    ns = parser.parse_args(["add", "https://a.example"])
    assert ns.command == "add"
    assert ns.url == "https://a.example"
    assert ns.tag is None
    assert ns.title is None


def test_parse_add_with_title_and_multiple_tags(parser) -> None:
    ns = parser.parse_args([
        "add", "https://a.example",
        "--title", "Hello",
        "--tag", "news", "--tag", "fun",
    ])
    assert ns.title == "Hello"
    assert ns.tag == ["news", "fun"]


def test_parse_list_no_filter(parser) -> None:
    ns = parser.parse_args(["list"])
    assert ns.command == "list"
    assert ns.tag is None
    assert ns.search is None


def test_parse_list_with_tag_and_search(parser) -> None:
    ns = parser.parse_args(["list", "--tag", "dev", "--search", "py"])
    assert ns.tag == "dev"
    assert ns.search == "py"


def test_parse_remove_requires_int_id(parser) -> None:
    ns = parser.parse_args(["remove", "7"])
    assert ns.command == "remove"
    assert ns.id == 7


def test_parse_remove_non_int_fails(parser) -> None:
    with pytest.raises(SystemExit):
        parser.parse_args(["remove", "abc"])


def test_parse_open_ok(parser) -> None:
    ns = parser.parse_args(["open", "3"])
    assert ns.command == "open"
    assert ns.id == 3


def test_parse_missing_command_fails(parser) -> None:
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parse_store_option(parser) -> None:
    ns = parser.parse_args(["--store", "/tmp/x.json", "list"])
    assert ns.store == Path("/tmp/x.json")


# ----------------- main() 端到端 -----------------

def test_main_add_and_list(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_path = tmp_path / "bm.json"

    # add（用 --title 避免联网抓取）
    rc = main([
        "--store", str(store_path),
        "add", "https://example.com",
        "--title", "Example",
        "--tag", "news",
    ])
    assert rc == 0

    # list
    rc = main(["--store", str(store_path), "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Example" in out
    assert "https://example.com" in out


def test_main_remove_nonexistent_returns_1(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store_path = tmp_path / "bm.json"
    rc = main(["--store", str(store_path), "remove", "99"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "not found" in err


def test_main_open_calls_webbrowser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store_path = tmp_path / "bm.json"
    main([
        "--store", str(store_path),
        "add", "https://a.example",
        "--title", "A",
    ])

    called: dict[str, str] = {}

    def fake_open(url: str) -> bool:
        called["url"] = url
        return True

    monkeypatch.setattr("smart_bookmark.__main__.webbrowser.open", fake_open)

    rc = main(["--store", str(store_path), "open", "1"])
    assert rc == 0
    assert called.get("url") == "https://a.example"


def test_main_list_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_path = tmp_path / "bm.json"
    rc = main(["--store", str(store_path), "list"])
    assert rc == 0
    assert "(no bookmarks)" in capsys.readouterr().out
