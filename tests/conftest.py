"""pytest 共享 fixture。"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """提供一个临时工作区目录。"""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def tmp_ai_rd_team_dir(tmp_workspace: Path) -> Path:
    """提供 .ai-rd-team/ 子目录。"""
    d = tmp_workspace / ".ai-rd-team"
    d.mkdir()
    return d
