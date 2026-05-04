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

    # ------------------------------------------------------------
    # 回归测试：M1 真实 E2E 发现的 3 个小问题（F1/F2/F3）
    # ------------------------------------------------------------

    def test_f1_timestamps_are_utc_with_timezone(self, tmp_workspace: Path) -> None:
        """F1：runtime 产出的时间戳必须带时区信息（非 naive datetime）。"""
        import json

        _write_basic_config(tmp_workspace, mode="lite")
        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=InMemoryBridge())
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")

        runtime = tmp_workspace / ".ai-rd-team" / "runtime"

        # current-run.yaml: started_at 必须带 +00:00 或 Z
        current = yaml.safe_load((runtime / "current-run.yaml").read_text(encoding="utf-8"))
        assert "+00:00" in current["started_at"] or current["started_at"].endswith("Z"), (
            f"started_at should have timezone info, got {current['started_at']!r}"
        )

        # team.yaml: last_updated 必须带时区
        team = yaml.safe_load((runtime / "state" / "team.yaml").read_text(encoding="utf-8"))
        assert "+00:00" in team["last_updated"] or team["last_updated"].endswith("Z")

        # events.jsonl 的 ts 字段必须带时区
        events = [json.loads(line) for line in (runtime / "events.jsonl").read_text().splitlines()]
        assert events, "events.jsonl should be non-empty"
        for evt in events:
            assert "+00:00" in evt["ts"] or evt["ts"].endswith("Z"), (
                f"event ts should have timezone info, got {evt['ts']!r}"
            )

    def test_f2_team_id_preserved_after_stop_run(self, tmp_workspace: Path) -> None:
        """F2：stop_run 后 team.yaml 仍应保留 team_id（不能因 write_team_state 默认参数丢失）。"""
        _write_basic_config(tmp_workspace, mode="lite")
        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=InMemoryBridge())
        engine.initialize(allow_onboarding=False, interactive=False)
        ctx = engine.start_run("test")
        expected_team_id = ctx.team_handle.team_id
        assert expected_team_id  # sanity

        engine.stop_run(reason="done")

        team_yaml = yaml.safe_load(
            (tmp_workspace / ".ai-rd-team" / "runtime" / "state" / "team.yaml").read_text(
                encoding="utf-8"
            )
        )
        assert team_yaml["status"] == "shut_down"
        assert team_yaml["team_id"] == expected_team_id, (
            f"team_id lost after stop_run; expected {expected_team_id!r}, "
            f"got {team_yaml['team_id']!r}"
        )

    def test_f3_member_states_finalized_on_stop(self, tmp_workspace: Path) -> None:
        """F3：stop_run 后所有成员 state 必须处于终态（非 spawning/working/idle）。"""
        _write_basic_config(tmp_workspace, mode="standard")
        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=InMemoryBridge())
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")
        engine.stop_run(reason="done")

        members_dir = tmp_workspace / ".ai-rd-team" / "runtime" / "state" / "members"
        terminal = {"done", "failed", "terminated"}
        for yaml_file in members_dir.glob("*.yaml"):
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            assert data["status"] in terminal, (
                f"{yaml_file.name}: status {data['status']!r} not in {terminal}"
            )

    def test_f3_respects_member_self_reported_done(self, tmp_workspace: Path) -> None:
        """F3：成员已把自己 state 写成 done 时，Engine 不应覆盖为 terminated。"""
        _write_basic_config(tmp_workspace, mode="lite")
        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=InMemoryBridge())
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")

        # 模拟成员主动把 state 更新为 done
        assert engine._runtime_state is not None
        engine._runtime_state.write_member_state(
            instance_name="developer",
            role="developer",
            status="done",
            progress="100%",
            produced_files=["hello.py"],
        )

        engine.stop_run(reason="done")

        state_file = (
            tmp_workspace / ".ai-rd-team" / "runtime" / "state" / "members" / "developer.yaml"
        )
        data = yaml.safe_load(state_file.read_text(encoding="utf-8"))
        assert data["status"] == "done", "done 状态应被保留，不能被兜底逻辑覆盖为 terminated"
        assert "hello.py" in data["produced_files"]

    def test_f3_shutdown_message_contains_state_hint(self, tmp_workspace: Path) -> None:
        """F3：shutdown 消息应包含'请更新 state=done'引导。"""
        _write_basic_config(tmp_workspace, mode="lite")
        bridge = InMemoryBridge()
        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")
        engine.stop_run(reason="done")

        shutdown_calls = [
            c
            for c in bridge.calls
            if c["op"] == "send_message" and c.get("type") == "shutdown_request"
        ]
        assert shutdown_calls
        content = shutdown_calls[0].get("content", "")
        assert "state" in content.lower() or "状态" in content
        assert "done" in content.lower()


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
