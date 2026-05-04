"""测试 RuntimeStateManager（T1.11）和 ArtifactRecorder（T1.12）。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from ai_rd_team.artifacts.recorder import ArtifactRecorder
from ai_rd_team.runtime.state import RuntimeStateManager


class TestRuntimeStateManager:
    def test_ensure_directories(self, tmp_path: Path) -> None:
        rsm = RuntimeStateManager(runtime_dir=tmp_path)
        rsm.ensure_directories()

        for sub in [
            "state",
            "state/members",
            "messages",
            "commands/pending",
            "commands/processed",
            "adapter-intents",
            "adapter-results",
            "cost",
            "artifacts",
            "artifacts/design",
            "artifacts/code",
            "logs",
            "archive",
        ]:
            assert (tmp_path / sub).is_dir()

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
    def test_write_basic(self, tmp_path: Path) -> None:
        rec = ArtifactRecorder(artifacts_dir=tmp_path)
        path = rec.write(
            role_name="architect",
            kind="spec",
            name="design",
            ext="md",
            content="# 架构设计\n接口...",
            producer="architect",
        )

        # 路径符合规范
        assert path == tmp_path / "design" / "spec-design.md"
        assert path.is_file()
        assert path.read_text(encoding="utf-8").startswith("# 架构设计")

    def test_write_with_owner_prefix(self, tmp_path: Path) -> None:
        rec = ArtifactRecorder(artifacts_dir=tmp_path)
        path = rec.write(
            role_name="developer",
            kind="log",
            name="progress",
            ext="md",
            content="...",
            producer="developer_1",
            owner_prefix="developer_1",
        )
        assert path.name == "developer_1-log-progress.md"

    def test_manifest_updated(self, tmp_path: Path) -> None:
        rec = ArtifactRecorder(artifacts_dir=tmp_path)
        rec.write(
            role_name="architect",
            kind="spec",
            name="design",
            ext="md",
            content="...",
            producer="architect",
        )
        rec.write(
            role_name="developer",
            kind="log",
            name="progress",
            ext="md",
            content="...",
            producer="developer_1",
        )

        data = rec.read_manifest()
        assert len(data["artifacts"]) == 2
        assert data["last_updated"]

        kinds = {a["kind"] for a in data["artifacts"]}
        assert kinds == {"spec", "log"}

    def test_manifest_overwrite_same_path(self, tmp_path: Path) -> None:
        """同路径写两次只保留一条 manifest 记录。"""
        rec = ArtifactRecorder(artifacts_dir=tmp_path)
        rec.write(
            role_name="architect",
            kind="spec",
            name="design",
            ext="md",
            content="v1",
            producer="architect",
        )
        rec.write(
            role_name="architect",
            kind="spec",
            name="design",
            ext="md",
            content="v2",  # 覆盖
            producer="architect",
        )

        data = rec.read_manifest()
        assert len(data["artifacts"]) == 1

        # 内容已更新
        path = tmp_path / "design" / "spec-design.md"
        assert path.read_text() == "v2"

    def test_invalid_kind_raises(self, tmp_path: Path) -> None:
        import pytest

        rec = ArtifactRecorder(artifacts_dir=tmp_path)
        with pytest.raises(ValueError, match="unknown artifact kind"):
            rec.write(
                role_name="architect",
                kind="bogus",
                name="x",
                ext="md",
                content="",
                producer="architect",
            )

    def test_list_artifacts_filtering(self, tmp_path: Path) -> None:
        rec = ArtifactRecorder(artifacts_dir=tmp_path)
        rec.write("architect", "spec", "a", "md", "", "architect")
        rec.write("architect", "log", "b", "md", "", "architect")
        rec.write("developer", "log", "c", "md", "", "developer_1")

        assert len(rec.list_artifacts()) == 3
        assert len(rec.list_artifacts(kind="log")) == 2
        assert len(rec.list_artifacts(producer="developer_1")) == 1

    def test_write_raw(self, tmp_path: Path) -> None:
        """write_raw 允许任意文件名。"""
        rec = ArtifactRecorder(artifacts_dir=tmp_path)
        path = rec.write_raw(
            role_name="developer",
            filename="user-api.go",
            content="package user\n",
            producer="developer_1",
        )
        assert path.name == "user-api.go"
        # manifest 中推断 kind
        items = rec.list_artifacts()
        assert len(items) == 1
