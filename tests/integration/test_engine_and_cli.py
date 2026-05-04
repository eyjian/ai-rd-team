"""Engine 和 CLI 的集成测试（T1.10 + T1.13）。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from ai_rd_team.adapter.bridge import InMemoryBridge
from ai_rd_team.cli.main import app
from ai_rd_team.engine.manager import EngineState, TeamEnvironmentManager


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _write_basic_config(ws: Path, mode: str = "lite") -> None:
    """写一份最小 config.yaml，避免引导触发。"""
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
                "project": {"description": "测试项目"},
                "budget": {"per_run": per_run, "per_day": per_day},
            }
        ),
        encoding="utf-8",
    )


class TestEngineLifecycle:
    """Engine 的完整生命周期（使用 InMemoryBridge 避免真实 CodeBuddy）。"""

    def test_initialize(self, tmp_workspace: Path) -> None:
        _write_basic_config(tmp_workspace, mode="lite")
        bridge = InMemoryBridge()

        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
        engine.initialize(allow_onboarding=False, interactive=False)

        assert engine.state == EngineState.IDLE
        assert engine.config.active_mode == "lite"

    def test_start_run_lite(self, tmp_workspace: Path) -> None:
        _write_basic_config(tmp_workspace, mode="lite")
        bridge = InMemoryBridge()

        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
        engine.initialize(allow_onboarding=False, interactive=False)

        ctx = engine.start_run(requirement="写一个计算器")

        assert engine.state == EngineState.RUNNING
        assert ctx.mode == "lite"
        # Lite 模式只有 1 个 developer
        assert len(ctx.members) == 1
        assert "developer" in ctx.members

        # Bridge 记录了所有调用
        ops = [c["op"] for c in bridge.calls]
        assert "team_create" in ops
        assert "task" in ops
        assert "send_message" in ops

    def test_start_run_standard(self, tmp_workspace: Path) -> None:
        _write_basic_config(tmp_workspace, mode="standard")
        bridge = InMemoryBridge()

        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
        engine.initialize(allow_onboarding=False, interactive=False)
        ctx = engine.start_run("实现用户管理")

        # Standard = architect + developer × default_instances + tester
        assert "architect" in ctx.members
        assert any(m.startswith("developer") for m in ctx.members)
        assert "tester" in ctx.members

        # 启动消息应发给 architect（pm 不存在时）
        send_calls = [c for c in bridge.calls if c["op"] == "send_message"]
        starter_msg = [c for c in send_calls if c.get("type") == "message"]
        assert len(starter_msg) == 1
        assert starter_msg[0]["recipient"] == "architect"

    def test_runtime_files_created(self, tmp_workspace: Path) -> None:
        """启动后关键 runtime 文件应存在。"""
        _write_basic_config(tmp_workspace, mode="lite")
        bridge = InMemoryBridge()

        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")

        runtime = tmp_workspace / ".ai-rd-team" / "runtime"
        assert (runtime / "current-run.yaml").is_file()
        assert (runtime / "state" / "team.yaml").is_file()
        assert (runtime / "state" / "roster.yaml").is_file()
        assert (runtime / "events.jsonl").is_file()
        # 至少一条消息被记录
        assert any((runtime / "messages").glob("*.json"))
        # 成员 state 文件被创建
        assert (runtime / "state" / "members" / "developer.yaml").is_file()

    def test_events_jsonl_has_key_events(self, tmp_workspace: Path) -> None:
        _write_basic_config(tmp_workspace, mode="lite")
        bridge = InMemoryBridge()

        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")

        import json

        events_file = tmp_workspace / ".ai-rd-team" / "runtime" / "events.jsonl"
        events = [json.loads(line) for line in events_file.read_text().splitlines()]
        event_types = {e["event"] for e in events}

        assert "run_starting" in event_types
        assert "run_started" in event_types
        assert "member_spawned" in event_types

    def test_stop_run(self, tmp_workspace: Path) -> None:
        _write_basic_config(tmp_workspace, mode="lite")
        bridge = InMemoryBridge()

        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")
        engine.stop_run(reason="test done")

        assert engine.state == EngineState.STOPPED

        # 触发了 shutdown_request 和 team_delete
        ops = [c["op"] for c in bridge.calls]
        assert "team_delete" in ops
        shutdown_calls = [
            c
            for c in bridge.calls
            if c["op"] == "send_message" and c.get("type") == "shutdown_request"
        ]
        assert len(shutdown_calls) >= 1

    def test_preset_overrides_config(self, tmp_workspace: Path) -> None:
        """CLI 的 --mode 覆盖 config.yaml 中的 run_mode。"""
        _write_basic_config(tmp_workspace, mode="lite")
        bridge = InMemoryBridge()

        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
        engine.initialize(
            preset="standard",
            allow_onboarding=False,
            interactive=False,
        )
        ctx = engine.start_run("test")

        assert ctx.mode == "standard"


class TestCli:
    """CLI 端到端烟测。"""

    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "ai-rd-team" in result.stdout

    def test_init_yes_mode(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        """ai-rd-team init --yes 非交互式生成 config.yaml。"""
        result = runner.invoke(
            app,
            ["init", "--yes", "-w", str(tmp_workspace)],
        )
        assert result.exit_code == 0

        config_path = tmp_workspace / ".ai-rd-team" / "config.yaml"
        assert config_path.is_file()

        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert data["run_mode"] == "standard"

    def test_config_show_when_missing(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["config", "show", "--layer", "basic", "-w", str(tmp_workspace)],
        )
        assert result.exit_code != 0  # basic 不存在时报错

    def test_config_show_effective(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        _write_basic_config(tmp_workspace, mode="standard")
        result = runner.invoke(
            app,
            ["config", "show", "-w", str(tmp_workspace)],
        )
        assert result.exit_code == 0
        assert "standard" in result.stdout

    def test_config_advanced_generate(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        _write_basic_config(tmp_workspace, mode="standard")
        result = runner.invoke(
            app,
            ["config", "advanced", "-w", str(tmp_workspace)],
        )
        assert result.exit_code == 0

        adv_path = tmp_workspace / ".ai-rd-team" / "config.advanced.yaml"
        assert adv_path.is_file()

        content = adv_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert "cost_control" in data
        assert "budget_lite" in data["cost_control"]

    def test_config_validate_ok(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        _write_basic_config(tmp_workspace, mode="lite")
        result = runner.invoke(
            app,
            ["config", "validate", "-w", str(tmp_workspace)],
        )
        assert result.exit_code == 0

    def test_config_validate_bad_mode(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        d = tmp_workspace / ".ai-rd-team"
        d.mkdir()
        (d / "config.yaml").write_text(
            yaml.safe_dump({"run_mode": "bogus"}),
            encoding="utf-8",
        )
        result = runner.invoke(
            app,
            ["config", "validate", "-w", str(tmp_workspace)],
        )
        assert result.exit_code != 0
