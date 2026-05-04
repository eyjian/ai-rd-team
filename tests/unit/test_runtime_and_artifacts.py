"""测试 RuntimeStateManager（T1.11）和 ArtifactRecorder（T1.12 / M7 重构）。"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from ai_rd_team.artifacts.layout import DEFAULT_LAYOUTS, ProjectLayout
from ai_rd_team.artifacts.recorder import (
    CATEGORY_DELIVERY,
    CATEGORY_PROCESS,
    ArtifactRecorder,
)
from ai_rd_team.runtime.state import RuntimeStateManager, utc_now_iso


class TestUtcNowIso:
    """F1 回归：utc_now_iso 应产生带 UTC 时区 + 毫秒精度的 ISO 8601 字符串。"""

    def test_has_timezone_suffix(self) -> None:
        s = utc_now_iso()
        assert s.endswith("+00:00"), f"expected UTC timezone suffix, got {s!r}"

    def test_has_millisecond_precision(self) -> None:
        s = utc_now_iso()
        # 形如 2026-05-04T03:12:45.678+00:00
        pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}\+00:00$"
        assert re.match(pattern, s), f"format should be YYYY-MM-DDTHH:MM:SS.sss+00:00, got {s!r}"

    def test_roundtrip_parseable(self) -> None:
        s = utc_now_iso()
        parsed = datetime.fromisoformat(s)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timezone.utc.utcoffset(None)


class TestRuntimeStateManager:
    def test_ensure_directories(self, tmp_path: Path) -> None:
        rsm = RuntimeStateManager(runtime_dir=tmp_path)
        rsm.ensure_directories()

        # M7 后 runtime/ 只保留过程数据相关目录，交付物去项目根（见 ArtifactRecorder）
        for sub in [
            "state",
            "state/members",
            "messages",
            "commands/pending",
            "commands/processed",
            "adapter-intents",
            "adapter-results",
            "cost",
            "review",
            "reports",
            "logs",
            "archive",
        ]:
            assert (tmp_path / sub).is_dir()

        # M7 后老的 artifacts/** 不应被自动创建
        for legacy in ["artifacts", "artifacts/code", "artifacts/design"]:
            assert not (tmp_path / legacy).exists(), (
                f"legacy subdir {legacy} should not be created after M7"
            )

    def test_write_run_metadata(self, tmp_path: Path) -> None:
        rsm = RuntimeStateManager(runtime_dir=tmp_path)
        rsm.ensure_directories()

        rsm.write_run_metadata(
            run_id="abc12345",
            requirement="做一个计算器",
            mode="standard",
        )

        data = yaml.safe_load((tmp_path / "current-run.yaml").read_text(encoding="utf-8"))
        assert data["run_id"] == "abc12345"
        assert data["requirement"] == "做一个计算器"
        assert data["mode"] == "standard"
        assert data["status"] == "running"
        assert "started_at" in data

    def test_read_run_metadata_missing(self, tmp_path: Path) -> None:
        rsm = RuntimeStateManager(runtime_dir=tmp_path)
        assert rsm.read_run_metadata() is None

    def test_update_run_status(self, tmp_path: Path) -> None:
        rsm = RuntimeStateManager(runtime_dir=tmp_path)
        rsm.ensure_directories()
        rsm.write_run_metadata("x", "req", "lite")

        rsm.update_run_status("stopped")
        data = rsm.read_run_metadata()
        assert data is not None
        assert data["status"] == "stopped"
        assert "updated_at" in data

    def test_write_team_state(self, tmp_path: Path) -> None:
        rsm = RuntimeStateManager(runtime_dir=tmp_path)
        rsm.ensure_directories()
        rsm.write_team_state(status="running", team_id="t-1")

        data = yaml.safe_load((tmp_path / "state" / "team.yaml").read_text(encoding="utf-8"))
        assert data["status"] == "running"
        assert data["team_id"] == "t-1"

    def test_write_member_state(self, tmp_path: Path) -> None:
        rsm = RuntimeStateManager(runtime_dir=tmp_path)
        rsm.ensure_directories()
        rsm.write_member_state(
            instance_name="architect",
            role="architect",
            status="working",
            current_task="设计接口",
            progress="50%",
        )

        data = rsm.read_member_state("architect")
        assert data is not None
        assert data["name"] == "architect"
        assert data["status"] == "working"
        assert data["progress"] == "50%"

    def test_list_member_states(self, tmp_path: Path) -> None:
        rsm = RuntimeStateManager(runtime_dir=tmp_path)
        rsm.ensure_directories()
        rsm.write_member_state("architect", "architect", status="idle")
        rsm.write_member_state("developer_1", "developer", status="working")

        all_members = rsm.list_member_states()
        assert set(all_members.keys()) == {"architect", "developer_1"}
        assert all_members["developer_1"]["status"] == "working"

    def test_write_roster(self, tmp_path: Path) -> None:
        rsm = RuntimeStateManager(runtime_dir=tmp_path)
        rsm.ensure_directories()
        rsm.write_roster([("architect", "architect"), ("developer_1", "developer")])

        data = yaml.safe_load((tmp_path / "state" / "roster.yaml").read_text(encoding="utf-8"))
        assert len(data["members"]) == 2
        assert data["members"][0]["role"] == "architect"

    def test_append_event(self, tmp_path: Path) -> None:
        rsm = RuntimeStateManager(runtime_dir=tmp_path)
        rsm.ensure_directories()
        rsm.append_event("run_started", run_id="x", member_count=3)
        rsm.append_event("member_spawned", member_id="architect")

        lines = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        entry0 = json.loads(lines[0])
        assert entry0["event"] == "run_started"
        assert entry0["run_id"] == "x"
        assert entry0["member_count"] == 3

    def test_write_message_record(self, tmp_path: Path) -> None:
        rsm = RuntimeStateManager(runtime_dir=tmp_path)
        rsm.ensure_directories()
        path = rsm.write_message_record(
            from_member="main",
            to_member="architect",
            msg_type="message",
            content="启动",
            summary="开始工作",
        )
        assert path.is_file()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["from"] == "main"
        assert data["to"] == "architect"
        assert data["content"] == "启动"

    def test_safe_filename_for_special_chars(self, tmp_path: Path) -> None:
        """to=all 不应产生不合法文件名。"""
        rsm = RuntimeStateManager(runtime_dir=tmp_path)
        rsm.ensure_directories()
        # 含斜杠的 member name 应被转义
        rsm.write_message_record(
            from_member="main",
            to_member="all",
            msg_type="broadcast",
            content="hi",
        )
        # 写入成功（具体文件名不重要）
        files = list((tmp_path / "messages").glob("*.json"))
        assert len(files) == 1


class TestArtifactRecorder:
    """M7：ArtifactRecorder 新接口（5 个 write_* 方法）冒烟测试。

    更深入的 layout × 方法组合覆盖见 test_recorder_layout.py。
    """

    def _make_recorder(
        self, tmp_path: Path, layout: ProjectLayout | None = None
    ) -> ArtifactRecorder:
        project_root = tmp_path / "project"
        runtime_dir = project_root / ".ai-rd-team" / "runtime"
        project_root.mkdir(parents=True, exist_ok=True)
        return ArtifactRecorder(
            project_root=project_root,
            runtime_dir=runtime_dir,
            layout=layout or DEFAULT_LAYOUTS["fallback"],
        )

    def test_old_signature_rejected(self, tmp_path: Path) -> None:
        """老 `ArtifactRecorder(artifacts_dir=...)` 签名应报 TypeError。"""
        with pytest.raises(TypeError):
            ArtifactRecorder(artifacts_dir=tmp_path)  # type: ignore[call-arg]

    def test_write_code_falls_back_to_module_name(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path, DEFAULT_LAYOUTS["go"])
        path = rec.write_code(
            module="mysh",
            filename="main.go",
            content="package main\n",
            producer="developer_1",
        )
        assert path == tmp_path / "project" / "mysh" / "main.go"
        assert path.read_text() == "package main\n"

    def test_write_code_honors_layout(self, tmp_path: Path) -> None:
        layout = DEFAULT_LAYOUTS["go"].with_overrides(
            {"code_dirs": {"backend": "services/backend"}}
        )
        rec = self._make_recorder(tmp_path, layout)
        path = rec.write_code(
            module="backend",
            filename="server.go",
            content="",
            producer="developer_1",
        )
        assert path == tmp_path / "project" / "services" / "backend" / "server.go"

    def test_write_doc_goes_to_docs_root(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path)
        path = rec.write_doc(
            category="design",
            filename="ARCHITECTURE.md",
            content="# 架构",
            producer="architect",
        )
        assert path == tmp_path / "project" / "docs" / "design" / "ARCHITECTURE.md"

    def test_write_doc_rejects_unknown_category(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path)
        with pytest.raises(ValueError, match="invalid category"):
            rec.write_doc(
                category="unknown",
                filename="x.md",
                content="",
                producer="architect",
            )

    def test_write_test_separate_mode(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path, DEFAULT_LAYOUTS["python"])
        path = rec.write_test(
            module=None,
            filename="test_user.py",
            content="",
            producer="tester",
        )
        assert path == tmp_path / "project" / "tests" / "test_user.py"

    def test_write_test_alongside_mode(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path, DEFAULT_LAYOUTS["go"])
        path = rec.write_test(
            module="mysh",
            filename="user_test.go",
            content="",
            producer="tester",
        )
        assert path == tmp_path / "project" / "mysh" / "user_test.go"

    def test_write_test_alongside_requires_module(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path, DEFAULT_LAYOUTS["go"])
        with pytest.raises(ValueError, match="alongside mode requires module"):
            rec.write_test(
                module=None,
                filename="x.go",
                content="",
                producer="tester",
            )

    def test_write_deploy_root_level_file(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path)
        path = rec.write_deploy(
            filename="Dockerfile",
            content="FROM python:3.11\n",
            producer="devops",
        )
        assert path == tmp_path / "project" / "Dockerfile"

    def test_write_deploy_subdir_file(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path)
        path = rec.write_deploy(
            filename="k8s-user.yaml",
            content="",
            producer="devops",
        )
        assert path == tmp_path / "project" / "deploy" / "k8s-user.yaml"

    def test_write_process_to_runtime(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path)
        path = rec.write_process(
            kind="review",
            name="spec-review-user",
            content="# Review\n",
            producer="reviewer",
        )
        assert (
            path
            == tmp_path / "project" / ".ai-rd-team" / "runtime" / "review" / "spec-review-user.md"
        )

    def test_write_process_rejects_unknown_kind(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path)
        with pytest.raises(ValueError, match="invalid kind"):
            rec.write_process(
                kind="delivery",
                name="x",
                content="",
                producer="pm",
            )

    def test_manifest_stores_delivery_path_relative_to_project_root(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path, DEFAULT_LAYOUTS["go"])
        rec.write_code(
            module="mysh",
            filename="main.go",
            content="",
            producer="developer_1",
        )

        manifest = rec.read_manifest()
        assert len(manifest["artifacts"]) == 1
        entry = manifest["artifacts"][0]
        assert entry["path"] == "mysh/main.go"
        assert entry["category"] == CATEGORY_DELIVERY
        assert entry["kind"] == "code"
        assert entry["producer"] == "developer_1"

    def test_manifest_stores_process_path_relative_to_runtime(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path)
        rec.write_process(
            kind="report",
            name="report-phase-dev",
            content="",
            producer="pm",
        )
        manifest = rec.read_manifest()
        entry = manifest["artifacts"][0]
        # path 含 kind 子目录前缀，以便在同一 manifest 中区分同名文件
        assert entry["path"] == "report/report-phase-dev.md"
        assert entry["category"] == CATEGORY_PROCESS

    def test_manifest_location_under_runtime(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path)
        assert rec.manifest_path == (
            tmp_path / "project" / ".ai-rd-team" / "runtime" / "manifest.yaml"
        )

    def test_manifest_overwrite_same_path_same_category(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path, DEFAULT_LAYOUTS["go"])
        rec.write_code(module="mysh", filename="main.go", content="v1", producer="d1")
        rec.write_code(module="mysh", filename="main.go", content="v2", producer="d1")

        manifest = rec.read_manifest()
        assert len(manifest["artifacts"]) == 1
        path = tmp_path / "project" / "mysh" / "main.go"
        assert path.read_text() == "v2"

    def test_list_artifacts_filtering(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path, DEFAULT_LAYOUTS["go"])
        rec.write_code(module="mysh", filename="main.go", content="", producer="d1")
        rec.write_code(module="mysqler", filename="main.go", content="", producer="d2")
        rec.write_process(kind="review", name="r1", content="", producer="reviewer")

        assert len(rec.list_artifacts()) == 3
        assert len(rec.list_artifacts(category=CATEGORY_DELIVERY)) == 2
        assert len(rec.list_artifacts(category=CATEGORY_PROCESS)) == 1
        assert len(rec.list_artifacts(producer="d1")) == 1
        assert len(rec.list_artifacts(kind="code")) == 2

    def test_legacy_manifest_warning(self, tmp_path: Path, caplog) -> None:
        """发现老位置的 manifest.yaml 时应打 warning 指引迁移。"""
        project_root = tmp_path / "project"
        runtime_dir = project_root / ".ai-rd-team" / "runtime"
        legacy = runtime_dir / "artifacts"
        legacy.mkdir(parents=True, exist_ok=True)
        (legacy / "manifest.yaml").write_text("artifacts: []\n", encoding="utf-8")

        with caplog.at_level("WARNING"):
            ArtifactRecorder(
                project_root=project_root,
                runtime_dir=runtime_dir,
                layout=DEFAULT_LAYOUTS["fallback"],
            )
        assert any("legacy manifest" in rec.message for rec in caplog.records)

    def test_filename_with_slash_rejected(self, tmp_path: Path) -> None:
        rec = self._make_recorder(tmp_path)
        with pytest.raises(ValueError, match="simple name"):
            rec.write_code(
                module="main",
                filename="nested/main.go",
                content="",
                producer="developer_1",
            )

    def test_write_doc_flat_subdirs_via_override(self, tmp_path: Path) -> None:
        """架构师把 docs_subdirs[category] 置空实现扁平化。"""
        layout = DEFAULT_LAYOUTS["python"].with_overrides(
            {"docs_subdirs": {"design": "", "requirements": "", "delivery": "", "research": ""}}
        )
        rec = self._make_recorder(tmp_path, layout)
        path = rec.write_doc(
            category="design",
            filename="ARCHITECTURE.md",
            content="",
            producer="architect",
        )
        assert path == tmp_path / "project" / "docs" / "ARCHITECTURE.md"
