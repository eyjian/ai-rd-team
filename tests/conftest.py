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


@pytest.fixture
def tmp_quota_home(tmp_path: Path) -> Path:
    """提供一个隔离的 quota 追踪 home 目录，避免污染用户真实 ~/.ai-rd-team。"""
    d = tmp_path / "quota-home"
    d.mkdir()
    return d
