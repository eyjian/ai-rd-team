"""Engine 集成 CostTracker 测试（T2.7-T2.10）。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from ai_rd_team.adapter.bridge import InMemoryBridge
from ai_rd_team.cost.tracker import BudgetAction
from ai_rd_team.engine.manager import TeamEnvironmentManager


def _write_basic_config(ws: Path, mode: str = "lite") -> None:
    d = ws / ".ai-rd-team"
    d.mkdir(parents=True, exist_ok=True)
    budgets = {
        "lite": (120, 500),
        "standard": (400, 2000),
        "full": (1500, 6000),
    }
    per_run, per_day = budgets[mode]
    (d / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "config_version": "1.0",
                "run_mode": mode,
                "project": {"description": "成本测试"},
                "budget": {"per_run": per_run, "per_day": per_day},
            }
        ),
        encoding="utf-8",
    )


class TestEngineCostIntegration:
    def test_spawn_and_message_counted(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        _write_basic_config(tmp_workspace, "lite")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("测试成本")

        snap = engine.cost_snapshot()
        assert snap is not None
        # Lite 档 1 developer spawn + 1 启动消息
        assert snap.member_spawn_count == 1
        assert snap.message_count == 1
        # RP = 1 * 40 + 1 * 2 = 42
        assert snap.resource_points == 42

    def test_broadcast_counted(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        _write_basic_config(tmp_workspace, "standard")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("测试广播")

        engine.broadcast(content="通知", summary="开会")
        snap = engine.cost_snapshot()
        assert snap is not None
        assert snap.broadcast_count == 1
        # standard 有 architect + 2 developer + tester = 4 个成员
        assert snap.broadcast_target_count == 4

    def test_resource_points_yaml_written(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        _write_basic_config(tmp_workspace, "lite")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("测试")

        cost_yaml = tmp_workspace / ".ai-rd-team" / "runtime" / "cost" / "resource-points.yaml"
        assert cost_yaml.is_file()
        data = yaml.safe_load(cost_yaml.read_text(encoding="utf-8"))
        assert data["mode"] == "lite"
        assert data["resource_points"] > 0

    def test_check_budget_returns_continue_for_small_run(
        self, tmp_workspace: Path, tmp_quota_home: Path
    ) -> None:
        _write_basic_config(tmp_workspace, "standard")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("小任务")

        result = engine.check_budget()
        assert result is not None
        assert result.action == BudgetAction.CONTINUE

    def test_post_run_record_on_stop(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        _write_basic_config(tmp_workspace, "lite")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("测试")
        engine.stop_run(reason="done")

        post_run = tmp_workspace / ".ai-rd-team" / "runtime" / "cost" / "post-run.jsonl"
        assert post_run.is_file()
        entries = [json.loads(ln) for ln in post_run.read_text().splitlines() if ln.strip()]
        assert len(entries) == 1
        assert entries[0]["mode"] == "lite"
        assert entries[0]["rp_used"] > 0

    def test_quota_history_written_on_stop(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        _write_basic_config(tmp_workspace, "lite")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("测试")
        engine.stop_run(reason="done")

        history = tmp_quota_home / "quota-history.jsonl"
        assert history.is_file()
        entries = [json.loads(ln) for ln in history.read_text().splitlines() if ln.strip()]
        assert len(entries) == 1
        assert entries[0]["rp"] > 0

    def test_check_budget_returns_none_before_start(
        self, tmp_workspace: Path, tmp_quota_home: Path
    ) -> None:
        _write_basic_config(tmp_workspace, "lite")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        assert engine.check_budget() is None
