"""测试文件操作工具（utils/file_ops）。"""

from __future__ import annotations

import json
from pathlib import Path

from ai_rd_team.utils.file_ops import (
    atomic_write,
    atomic_write_json,
    locked_append,
    read_if_exists,
    read_json_if_exists,
)


class TestAtomicWrite:
    def test_writes_content(self, tmp_path: Path) -> None:
        target = tmp_path / "sub" / "file.txt"
        atomic_write(target, "hello 世界")

        assert target.is_file()
        assert target.read_text(encoding="utf-8") == "hello 世界"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b" / "c" / "file.txt"
        atomic_write(target, "x")
        assert target.is_file()

    def test_no_temp_files_left(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        atomic_write(target, "content")
        # 目录下除了目标文件不应有遗留 .tmp 文件
        siblings = list(tmp_path.iterdir())
        assert siblings == [target]

    def test_overwrite_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        target.write_text("old", encoding="utf-8")
        atomic_write(target, "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_atomic_write_json(self, tmp_path: Path) -> None:
        target = tmp_path / "data.json"
        atomic_write_json(target, {"k": "值", "n": 42})

        parsed = json.loads(target.read_text(encoding="utf-8"))
        assert parsed == {"k": "值", "n": 42}


class TestLockedAppend:
    def test_single_write(self, tmp_path: Path) -> None:
        target = tmp_path / "log.jsonl"
        locked_append(target, '{"a": 1}\n')
        assert target.read_text() == '{"a": 1}\n'

    def test_multiple_appends(self, tmp_path: Path) -> None:
        target = tmp_path / "log.jsonl"
        for i in range(5):
            locked_append(target, f'{{"i": {i}}}\n')

        lines = target.read_text().splitlines()
        assert len(lines) == 5
        assert lines[0] == '{"i": 0}'
        assert lines[-1] == '{"i": 4}'


class TestRead:
    def test_read_if_exists_missing(self, tmp_path: Path) -> None:
        assert read_if_exists(tmp_path / "nope") is None

    def test_read_if_exists_present(self, tmp_path: Path) -> None:
        p = tmp_path / "x.txt"
        p.write_text("hi", encoding="utf-8")
        assert read_if_exists(p) == "hi"

    def test_read_json_valid(self, tmp_path: Path) -> None:
        p = tmp_path / "x.json"
        p.write_text('{"k": 1}', encoding="utf-8")
        assert read_json_if_exists(p) == {"k": 1}

    def test_read_json_invalid_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / "x.json"
        p.write_text("not json", encoding="utf-8")
        assert read_json_if_exists(p) is None

    def test_read_json_missing_returns_none(self, tmp_path: Path) -> None:
        assert read_json_if_exists(tmp_path / "nope.json") is None
