"""制品记录器：按 ProjectLayout 将团队产出分派到项目根（交付物）或 runtime/（过程）。

对应设计文档：
- openspec/specs/design/07-artifacts.md
- openspec/changes/relocate-artifacts-to-root/design.md D1-D4

M7 核心设计：
- 五个公开方法：write_code / write_doc / write_test / write_deploy / write_process
- 老的 write() / write_raw() 已**删除**（不保留 DeprecationWarning 兼容层）
- manifest.yaml 位置：<runtime_dir>/manifest.yaml（不再是 artifacts/ 私有索引）
- 每条 manifest entry 含 `category` 字段（delivery / process）
  - delivery：path 为项目根相对
  - process：path 为 runtime_dir 相对
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from ai_rd_team.artifacts.layout import (
    VALID_DOC_CATEGORIES,
    VALID_PROCESS_KINDS,
    VALID_TESTS_MODES,
    ProjectLayout,
)
from ai_rd_team.utils.file_ops import atomic_write

logger = logging.getLogger(__name__)


# 交付 / 过程的 manifest category（07-artifacts §4.1）
CATEGORY_DELIVERY = "delivery"
CATEGORY_PROCESS = "process"
VALID_CATEGORIES = frozenset([CATEGORY_DELIVERY, CATEGORY_PROCESS])


@dataclass
class ArtifactEntry:
    """manifest 中的一条记录。"""

    path: str  # delivery: 相对项目根；process: 相对 runtime_dir
    kind: str  # code / doc / test / deploy / review / report / log
    category: str  # delivery / process
    producer: str  # 成员 instance_name
    created_at: str  # ISO 8601

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "category": self.category,
            "producer": self.producer,
            "created_at": self.created_at,
        }


class ArtifactRecorder:
    """按 ProjectLayout 分派交付物 / 过程数据到正确位置。

    典型用法::

        recorder = ArtifactRecorder(
            project_root=workspace_dir,
            runtime_dir=workspace_dir / ".ai-rd-team" / "runtime",
            layout=ProjectLayout.from_yaml(...)  # 或 DEFAULT_LAYOUTS["go"] 等
        )

        # 交付物（进项目根）
        recorder.write_code("mysh", "main.go", content, producer="developer_1")
        recorder.write_doc("design", "ARCHITECTURE.md", content, producer="architect")
        recorder.write_test("mysh", "user_test.go", content, producer="tester")
        recorder.write_deploy("Dockerfile", content, producer="devops")

        # 过程（进 runtime_dir）
        recorder.write_process("review", "spec-review-user", content, producer="reviewer")
    """

    def __init__(
        self,
        project_root: Path,
        runtime_dir: Path,
        layout: ProjectLayout,
    ):
        self.project_root = Path(project_root)
        self.runtime_dir = Path(runtime_dir)
        self.layout = layout
        self.manifest_path = self.runtime_dir / "manifest.yaml"

        # 启动检测：若发现老位置的 manifest，打 warning 指引用户迁移
        legacy_manifest = self.runtime_dir / "artifacts" / "manifest.yaml"
        if legacy_manifest.is_file() and not self.manifest_path.is_file():
            logger.warning(
                "ArtifactRecorder: legacy manifest detected at %s; "
                "please delete <workspace>/.ai-rd-team/runtime/artifacts/ "
                "and re-run the team. Ignoring legacy file.",
                legacy_manifest,
            )

    # ==========================================================
    # 交付物（进项目根）
    # ==========================================================

    def write_code(
        self,
        module: str,
        filename: str,
        content: str,
        producer: str,
    ) -> Path:
        """写代码文件到 <project_root>/<layout.code_dirs[module] or module>/<filename>。

        若 `module` 不在 layout.code_dirs 中，则直接用 module 作为子目录名
        （允许架构师未声明完整的 code_dirs）。
        """
        if not module:
            raise ValueError("write_code: module must be a non-empty string")
        subdir = self.layout.code_dirs.get(module, module)
        target = self._write_under(self.project_root, subdir, filename, content)
        self._record(
            path=target.relative_to(self.project_root),
            kind="code",
            category=CATEGORY_DELIVERY,
            producer=producer,
        )
        return target

    def write_doc(
        self,
        category: str,
        filename: str,
        content: str,
        producer: str,
    ) -> Path:
        """写文档到 <project_root>/<docs_root>/<docs_subdirs[category]>/<filename>。

        `category` 必须 ∈ {requirements, design, delivery, research}，否则抛 ValueError。
        架构师可通过 layout 把某个 subdir 置为空串实现扁平化。
        """
        if category not in VALID_DOC_CATEGORIES:
            raise ValueError(
                f"write_doc: invalid category {category!r}; "
                f"valid options are {sorted(VALID_DOC_CATEGORIES)}"
            )
        subdir_parts = [self.layout.docs_root, self.layout.docs_subdirs.get(category, category)]
        subdir = "/".join(p for p in subdir_parts if p)  # 空串被过滤掉实现扁平化
        target = self._write_under(self.project_root, subdir, filename, content)
        self._record(
            path=target.relative_to(self.project_root),
            kind="doc",
            category=CATEGORY_DELIVERY,
            producer=producer,
        )
        return target

    def write_test(
        self,
        module: str | None,
        filename: str,
        content: str,
        producer: str,
    ) -> Path:
        """按 layout.tests_mode 路由测试文件。

        - `separate`：文件落 <project_root>/<tests_root>/<filename>；module 被忽略
        - `alongside`：文件落 <project_root>/<code_dirs[module] or module>/<filename>；
          module 必填，否则抛 ValueError
        """
        mode = self.layout.tests_mode
        if mode not in VALID_TESTS_MODES:
            raise ValueError(
                f"write_test: invalid layout.tests_mode {mode!r}; "
                f"valid options are {sorted(VALID_TESTS_MODES)}"
            )

        if mode == "alongside":
            if not module:
                raise ValueError("write_test: alongside mode requires module (got None/empty)")
            subdir = self.layout.code_dirs.get(module, module)
        else:  # separate
            tests_root = self.layout.tests_root or "tests"
            subdir = tests_root

        target = self._write_under(self.project_root, subdir, filename, content)
        self._record(
            path=target.relative_to(self.project_root),
            kind="test",
            category=CATEGORY_DELIVERY,
            producer=producer,
        )
        return target

    def write_deploy(
        self,
        filename: str,
        content: str,
        producer: str,
    ) -> Path:
        """按文件名惯例将部署产物落到项目根或 <deploy_root>/。"""
        if filename in self.layout.root_level_files:
            target = self._write_under(self.project_root, "", filename, content)
        else:
            target = self._write_under(
                self.project_root, self.layout.deploy_root, filename, content
            )
        self._record(
            path=target.relative_to(self.project_root),
            kind="deploy",
            category=CATEGORY_DELIVERY,
            producer=producer,
        )
        return target

    # ==========================================================
    # 过程数据（进 .ai-rd-team/runtime）
    # ==========================================================

    def write_process(
        self,
        kind: str,
        name: str,
        content: str,
        producer: str,
        ext: str = "md",
    ) -> Path:
        """写过程数据到 <runtime_dir>/<kind>/<name>.<ext>。

        `kind` 必须 ∈ {review, report, log}，其它抛 ValueError。
        """
        if kind not in VALID_PROCESS_KINDS:
            raise ValueError(
                f"write_process: invalid kind {kind!r}; "
                f"valid options are {sorted(VALID_PROCESS_KINDS)}"
            )
        filename = f"{name}.{ext}" if ext else name
        target = self._write_under(self.runtime_dir, kind, filename, content)
        self._record(
            path=target.relative_to(self.runtime_dir),
            kind=kind,
            category=CATEGORY_PROCESS,
            producer=producer,
        )
        return target

    # ==========================================================
    # manifest 管理
    # ==========================================================

    def read_manifest(self) -> dict[str, Any]:
        """读取 manifest.yaml；不存在或非法返回空骨架。"""
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

    def list_artifacts(
        self,
        *,
        kind: str | None = None,
        producer: str | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出 manifest 中的制品（按 kind / producer / category 过滤）。"""
        data = self.read_manifest()
        items: list[dict[str, Any]] = data.get("artifacts", [])
        if kind is not None:
            items = [a for a in items if a.get("kind") == kind]
        if producer is not None:
            items = [a for a in items if a.get("producer") == producer]
        if category is not None:
            items = [a for a in items if a.get("category") == category]
        return items

    # ==========================================================
    # 内部
    # ==========================================================

    def _write_under(
        self,
        base: Path,
        subdir: str,
        filename: str,
        content: str,
    ) -> Path:
        """原子写到 base / subdir / filename。subdir 为空串则直接落 base。"""
        if not filename or "/" in filename or "\\" in filename:
            raise ValueError(f"filename must be a simple name, got {filename!r}")
        target_dir = base / subdir if subdir else base
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        atomic_write(target, content)
        return target

    def _record(
        self,
        *,
        path: Path,
        kind: str,
        category: str,
        producer: str,
    ) -> None:
        """根据 category 更新 manifest 条目（path 已是正确相对路径）。"""
        if category not in VALID_CATEGORIES:
            raise ValueError(f"unknown category: {category}")
        entry = ArtifactEntry(
            path=str(path).replace("\\", "/"),  # 跨平台友好
            kind=kind,
            category=category,
            producer=producer,
            created_at=datetime.now().isoformat(),
        )
        self._update_manifest(entry)

    def _update_manifest(self, entry: ArtifactEntry) -> None:
        """增量更新 manifest：同 (path, category) 覆盖，新路径追加。"""
        data = self.read_manifest()
        artifacts: list[dict[str, Any]] = data.get("artifacts", [])

        # 按 (path, category) 去重——path 相对基不同，仅 path 可能碰撞
        artifacts = [
            a
            for a in artifacts
            if not (a.get("path") == entry.path and a.get("category") == entry.category)
        ]
        artifacts.append(entry.to_dict())

        data["artifacts"] = artifacts
        data["last_updated"] = datetime.now().isoformat()

        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(
            self.manifest_path,
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        )


__all__ = [
    "CATEGORY_DELIVERY",
    "CATEGORY_PROCESS",
    "VALID_CATEGORIES",
    "ArtifactEntry",
    "ArtifactRecorder",
]
