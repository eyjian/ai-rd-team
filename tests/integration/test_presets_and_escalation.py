"""测试 Preset 加载 + 导出 + 升档（T2.14 + T2.15）。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai_rd_team.adapter.bridge import InMemoryBridge
from ai_rd_team.config.presets_loader import (
    PresetError,
    export_preset_to_workspace,
    list_presets,
    load_preset,
)
from ai_rd_team.engine.manager import TeamEnvironmentManager


class TestPresetListAndLoad:
    def test_three_presets_available(self) -> None:
        names = list_presets()
        assert "lite" in names
        assert "standard" in names
        assert "full" in names

    def test_load_lite(self) -> None:
        data = load_preset("lite")
        assert data["run_mode"] == "lite"
        assert "cost_control" in data
        assert data["cost_control"]["budget_lite"]["max_resource_points"] == 120

    def test_load_standard(self) -> None:
        data = load_preset("standard")
        assert data["run_mode"] == "standard"
        roles = data["roles"]
        assert "architect" in roles
        assert "developer" in roles
        assert "tester" in roles

    def test_load_full(self) -> None:
        data = load_preset("full")
        assert data["run_mode"] == "full"
        # Full 档启用全部 7 角色
        roles = data["roles"]
        for r in ("pm", "analyst", "architect", "developer", "reviewer", "tester", "devops"):
            assert r in roles

    def test_unknown_preset_raises(self) -> None:
        with pytest.raises(PresetError):
            load_preset("not-a-mode")


class TestPresetExport:
    def test_export_creates_advanced_yaml(self, tmp_workspace: Path) -> None:
        dst = export_preset_to_workspace("standard", tmp_workspace)
        assert dst.name == "config.advanced.yaml"
        assert dst.is_file()

        data = yaml.safe_load(dst.read_text(encoding="utf-8"))
        assert data["run_mode"] == "standard"

    def test_export_refuses_overwrite_without_force(self, tmp_workspace: Path) -> None:
        export_preset_to_workspace("standard", tmp_workspace)
        with pytest.raises(PresetError):
            export_preset_to_workspace("lite", tmp_workspace)

    def test_export_force_overwrites(self, tmp_workspace: Path) -> None:
        export_preset_to_workspace("lite", tmp_workspace)
        dst = export_preset_to_workspace("standard", tmp_workspace, force=True)
        data = yaml.safe_load(dst.read_text(encoding="utf-8"))
        assert data["run_mode"] == "standard"

    def test_export_accepts_workspace_ending_with_ai_rd_team(self, tmp_path: Path) -> None:
        ws_dir = tmp_path / ".ai-rd-team"
        ws_dir.mkdir()
        dst = export_preset_to_workspace("lite", ws_dir)
        # 不要嵌套两层
        assert dst == ws_dir / "config.advanced.yaml"


# =================================================================
# 升档（T2.15）
# =================================================================


def _write_basic_config(ws: Path, mode: str = "lite") -> None:
    d = ws / ".ai-rd-team"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "config_version": "1.0",
                "run_mode": mode,
                "project": {"description": "升档测试"},
                "budget": {"per_run": 120, "per_day": 500},
            }
        ),
        encoding="utf-8",
    )


class TestAddMember:
    def test_add_member_at_runtime(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        _write_basic_config(tmp_workspace, "lite")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        ctx = engine.start_run("test")
        assert len(ctx.members) == 1

        # 加一个 tester
        new_member = engine.add_member(role_name="tester")
        assert new_member.member_id == "tester"
        assert "tester" in ctx.members

    def test_add_member_scalable_auto_index(
        self, tmp_workspace: Path, tmp_quota_home: Path
    ) -> None:
        _write_basic_config(tmp_workspace, "lite")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        ctx = engine.start_run("test")
        # 已经有 developer，再加 1 个应该叫 developer_2
        engine.add_member(role_name="developer")
        assert any(n.startswith("developer_") for n in ctx.members)

    def test_add_member_records_event(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        import json

        _write_basic_config(tmp_workspace, "lite")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")
        engine.add_member(role_name="reviewer")

        events_file = tmp_workspace / ".ai-rd-team" / "runtime" / "events.jsonl"
        events = [json.loads(ln) for ln in events_file.read_text().splitlines() if ln.strip()]
        assert any(e["event"] == "member_added" for e in events)

    def test_add_member_fails_when_not_running(
        self, tmp_workspace: Path, tmp_quota_home: Path
    ) -> None:
        _write_basic_config(tmp_workspace, "lite")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        with pytest.raises(RuntimeError):
            engine.add_member(role_name="tester")


class TestEscalateMode:
    def test_escalate_lite_to_standard(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        _write_basic_config(tmp_workspace, "lite")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        ctx = engine.start_run("test")
        assert len(ctx.members) == 1

        new_ctx = engine.escalate_mode("standard")
        # Standard 有 architect + 2 dev + tester
        assert new_ctx.mode == "standard"
        assert "architect" in new_ctx.members
        assert "tester" in new_ctx.members
        # 至少 2 个 developer
        devs = [n for n in new_ctx.members if n.startswith("developer")]
        assert len(devs) >= 2

    def test_escalate_refuses_downgrade(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        _write_basic_config(tmp_workspace, "standard")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")
        with pytest.raises(RuntimeError):
            engine.escalate_mode("lite")

    def test_escalate_records_run_upgraded(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        import json

        _write_basic_config(tmp_workspace, "lite")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")
        engine.escalate_mode("standard")

        events_file = tmp_workspace / ".ai-rd-team" / "runtime" / "events.jsonl"
        events = [json.loads(ln) for ln in events_file.read_text().splitlines() if ln.strip()]
        upgraded = [e for e in events if e["event"] == "run_upgraded"]
        assert len(upgraded) == 1
        assert upgraded[0]["old_mode"] == "lite"
        assert upgraded[0]["new_mode"] == "standard"
