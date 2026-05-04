"""Preset 加载器（T2.14）：把档位预设 YAML 暴露给用户 / 合并到 config。

三个档位的完整 advanced preset 存放在本模块同级目录 ``presets/``：
- ``lite.yaml``：最小团队（1 developer），成本最低
- ``standard.yaml``：标准团队（architect + 2 dev + tester），推荐
- ``full.yaml``：完整团队（7 角色齐全），复杂项目

用途：
- 用户可以 ``cp`` 其中一份到 ``.ai-rd-team/config.advanced.yaml`` 作为起点
- ``ai-rd-team config preset --mode standard`` 命令导出到工作区
- 编程接口：``load_preset("standard")`` 返回 dict
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ai_rd_team.config.models import RunMode


class PresetError(Exception):
    """Preset 加载异常。"""


def presets_dir() -> Path:
    """返回 preset YAML 的包内目录。"""
    return Path(__file__).resolve().parent / "presets"


def list_presets() -> list[str]:
    """列出所有可用 preset 名（不含 .yaml 后缀）。"""
    d = presets_dir()
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def load_preset(mode: RunMode | str) -> dict[str, Any]:
    """加载某档位 preset 为 dict。

    Raises:
        PresetError: 档位不存在或 YAML 解析失败
    """
    path = presets_dir() / f"{mode}.yaml"
    if not path.is_file():
        raise PresetError(
            f"preset {mode!r} not found (searched {path}); available: {list_presets()}"
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise PresetError(f"failed to parse preset {mode}: {e}") from e
    if not isinstance(data, dict):
        raise PresetError(f"preset {mode} must be a mapping, got {type(data).__name__}")
    return data


def export_preset_to_workspace(
    mode: RunMode | str,
    workspace: Path,
    force: bool = False,
) -> Path:
    """把 preset 拷贝到工作区 ``.ai-rd-team/config.advanced.yaml``。

    Args:
        mode: lite / standard / full
        workspace: 工作区根目录（包含或不包含 .ai-rd-team 都可）
        force: 目标已存在时是否覆盖

    Returns:
        目标文件绝对路径

    Raises:
        PresetError: preset 不存在 / 目标已存在且 force=False
    """
    src = presets_dir() / f"{mode}.yaml"
    if not src.is_file():
        raise PresetError(f"preset {mode!r} not found")

    ws_dir = workspace if workspace.name == ".ai-rd-team" else workspace / ".ai-rd-team"
    ws_dir.mkdir(parents=True, exist_ok=True)
    dst = ws_dir / "config.advanced.yaml"
    if dst.exists() and not force:
        raise PresetError(f"{dst} already exists; pass force=True to overwrite")
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


__all__ = [
    "PresetError",
    "export_preset_to_workspace",
    "list_presets",
    "load_preset",
    "presets_dir",
]
