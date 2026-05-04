"""制品记录器：统一管理 artifacts/ 目录的写入 + manifest。

对应设计文档：openspec/specs/design/07-artifacts.md

M1 最小版：
- 按角色写入到对应子目录
- 维护 artifacts/manifest.yaml 增量更新
- 五类前缀命名约定（spec-/data-/result-/log-/report-）

M2+：代码产物的 in_place/artifacts_only 双向、review issues 数据类。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ai_rd_team.roles.prompt import ROLE_TO_DIR
from ai_rd_team.utils.file_ops import atomic_write

# 五类前缀（§4.1）
ARTIFACT_KINDS = {"spec", "data", "result", "log", "report"}


@dataclass
class ArtifactEntry:
    """manifest 中的一条记录。"""

    path: str  # 相对 artifacts/ 的路径
    kind: str  # spec / data / result / log / report
    producer: str  # 成员 instance_name
    created_at: str  # ISO 8601


class ArtifactRecorder:
    """制品文件写入 + manifest 维护。

    典型用法：
        recorder = ArtifactRecorder(artifacts_dir=runtime/"artifacts")
        path = recorder.write(
            role_name="architect",
            kind="spec",
            name="design",
            ext="md",
            content="# 架构设计\n...",
            producer="architect",
        )
        # path = runtime/artifacts/design/spec-design.md
    """

    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir
        self.manifest_path = artifacts_dir / "manifest.yaml"

    # ------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------

    def write(
        self,
        role_name: str,
        kind: str,
        name: str,
        ext: str,
        content: str,
        producer: str,
        owner_prefix: str | None = None,
    ) -> Path:
        """写入一个制品文件并更新 manifest。

        文件名规则：`{kind}-{name}.{ext}`
        若 owner_prefix 提供，则变为 `{owner_prefix}-{kind}-{name}.{ext}`

        Args:
            role_name: 角色名（决定子目录，通过 ROLE_TO_DIR 映射）
            kind: 五类之一（spec/data/result/log/report）
            name: 文件名主体（如 "design"、"requirements"）
            ext: 扩展名（md/yaml/json 等）
            content: 文件内容
            producer: 产出者 instance_name（用于 manifest 追溯）
            owner_prefix: 多人同类型产出时的 owner 前缀（如 "developer_1"）

        Returns:
            写入的文件的绝对路径
        """
        if kind not in ARTIFACT_KINDS:
            raise ValueError(f"unknown artifact kind: {kind}")

        subdir = ROLE_TO_DIR.get(role_name, role_name)
        filename = f"{owner_prefix}-{kind}-{name}.{ext}" if owner_prefix else f"{kind}-{name}.{ext}"

        target_dir = self.artifacts_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename

        atomic_write(target, content)

        # 更新 manifest
        rel_path = str(target.relative_to(self.artifacts_dir))
        self._update_manifest(
            ArtifactEntry(
                path=rel_path,
                kind=kind,
                producer=producer,
                created_at=datetime.now().isoformat(),
            )
        )
        return target

    def write_raw(
        self,
        role_name: str,
        filename: str,
        content: str,
        producer: str,
    ) -> Path:
        """写入任意文件名（不遵循五类前缀）。

        用于代码文件快照等特殊场景。仍更新 manifest（kind 推断为文件扩展名或 "raw"）。
        """
        subdir = ROLE_TO_DIR.get(role_name, role_name)
        target_dir = self.artifacts_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        atomic_write(target, content)

        # 推断 kind：取首个前缀段
        inferred_kind = filename.split("-", 1)[0] if "-" in filename else "raw"
        kind = inferred_kind if inferred_kind in ARTIFACT_KINDS else "raw"

        rel_path = str(target.relative_to(self.artifacts_dir))
        self._update_manifest(
            ArtifactEntry(
                path=rel_path,
                kind=kind,
                producer=producer,
                created_at=datetime.now().isoformat(),
            )
        )
        return target

    # ------------------------------------------------------------
    # manifest 管理
    # ------------------------------------------------------------

    def read_manifest(self) -> dict[str, Any]:
        """读取 manifest.yaml。不存在则返回空骨架。"""
        if not self.manifest_path.is_file():
            return {"artifacts": [], "last_updated": None}
        try:
            data = yaml.safe_load(self.manifest_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return {"artifacts": [], "last_updated": None}
            data.setdefault("artifacts", [])
            return data
        except (OSError, yaml.YAMLError):
            return {"artifacts": [], "last_updated": None}

    def _update_manifest(self, entry: ArtifactEntry) -> None:
        """增量更新 manifest：同路径覆盖，新路径追加。"""
        data = self.read_manifest()
        artifacts: list[dict[str, Any]] = data.get("artifacts", [])

        # 移除同路径的旧记录
        artifacts = [a for a in artifacts if a.get("path") != entry.path]
        artifacts.append(
            {
                "path": entry.path,
                "kind": entry.kind,
                "producer": entry.producer,
                "created_at": entry.created_at,
            }
        )

        data["artifacts"] = artifacts
        data["last_updated"] = datetime.now().isoformat()

        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(
            self.manifest_path,
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        )

    def list_artifacts(
        self,
        kind: str | None = None,
        producer: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出 manifest 中的制品（可按 kind 或 producer 过滤）。"""
        data = self.read_manifest()
        items: list[dict[str, Any]] = data.get("artifacts", [])
        if kind is not None:
            items = [a for a in items if a.get("kind") == kind]
        if producer is not None:
            items = [a for a in items if a.get("producer") == producer]
        return items


__all__ = ["ARTIFACT_KINDS", "ArtifactEntry", "ArtifactRecorder"]
