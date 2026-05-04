"""端到端烟测：FileBasedBridge + BridgeSimulator 模拟真实主 Agent。

这是 M1 最关键的集成测试：
- 不绕过 Bridge 文件协议（与真实 CodeBuddy 等价）
- 用 BridgeSimulator 替代人工主 Agent
- 验证 Python 引擎完整跑通 initialize → start_run → stop_run
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ai_rd_team.adapter.bridge import FileBasedBridge
from ai_rd_team.adapter.bridge_simulator import BridgeSimulator
from ai_rd_team.engine.manager import EngineState, TeamEnvironmentManager


def _write_basic_config(ws: Path, mode: str = "lite") -> None:
    d = ws / ".ai-rd-team"
    d.mkdir(parents=True, exist_ok=True)
    budgets = {"lite": (120, 500), "standard": (400, 2000), "full": (1500, 6000)}
    per_run, per_day = budgets[mode]
    (d / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "config_version": "1.0",
                "run_mode": mode,
                "project": {"description": "测试项目"},
                "budget": {"per_run": per_run, "per_day": per_day},
                "adapter": {"bridge_timeout_seconds": 5},
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def prepared_workspace(tmp_workspace: Path) -> tuple[Path, Path]:
    """准备工作区 + config，返回 (workspace, runtime_dir)。"""
    _write_basic_config(tmp_workspace, mode="lite")
    runtime = tmp_workspace / ".ai-rd-team" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    return tmp_workspace, runtime


class TestE2ELite:
    """Lite 档位的完整流程。"""

    def test_initialize_with_real_bridge(
        self,
        prepared_workspace: tuple[Path, Path],
    ) -> None:
        ws, runtime = prepared_workspace

        # 启动 Bridge 模拟器
        sim = BridgeSimulator(runtime_dir=runtime, poll_interval=0.05)
        sim.start()

        try:
            # 使用真实 FileBasedBridge（不是 InMemory）
            bridge = FileBasedBridge(
                runtime_dir=runtime,
                timeout_seconds=5,
                poll_interval_seconds=0.05,
            )
            engine = TeamEnvironmentManager(workspace=ws, bridge=bridge)
            engine.initialize(allow_onboarding=False, interactive=False)

            assert engine.state == EngineState.IDLE
            assert engine.config.active_mode == "lite"
        finally:
            sim.stop()

        # M5：initialize 不再通过 bridge 发 _probe / _version intent（本地常量化）
        # 因此 simulator 不应处理这类 intent
        probe_entries = [p for p in sim.processed if p["op"] == "_probe"]
        version_entries = [p for p in sim.processed if p["op"] == "_version"]
        assert len(probe_entries) == 0
        assert len(version_entries) == 0

    def test_full_run_lifecycle(
        self,
        prepared_workspace: tuple[Path, Path],
    ) -> None:
        """完整 initialize → start_run → stop_run。"""
        ws, runtime = prepared_workspace

        sim = BridgeSimulator(runtime_dir=runtime, poll_interval=0.05)
        sim.start()

        try:
            bridge = FileBasedBridge(
                runtime_dir=runtime,
                timeout_seconds=5,
                poll_interval_seconds=0.05,
            )
            engine = TeamEnvironmentManager(workspace=ws, bridge=bridge)
            engine.initialize(allow_onboarding=False, interactive=False)

            ctx = engine.start_run(requirement="做一个计算器")
            assert engine.state == EngineState.RUNNING
            assert ctx.mode == "lite"
            assert len(ctx.members) == 1  # lite = 1 developer
            assert "developer" in ctx.members

            engine.stop_run(reason="test")
            assert engine.state == EngineState.STOPPED
        finally:
            sim.stop()

        # 验证调用顺序（M5：_probe 不再出现在 ops 里，因为 initialize 本地化了）
        ops = [p["op"] for p in sim.processed]
        assert "_probe" not in ops  # M5 行为变更
        assert "team_create" in ops
        assert "task" in ops
        # 启动消息 + shutdown_request
        send_message_count = ops.count("send_message")
        assert send_message_count >= 2
        assert "team_delete" in ops

    def test_runtime_files_written(
        self,
        prepared_workspace: tuple[Path, Path],
    ) -> None:
        ws, runtime = prepared_workspace

        sim = BridgeSimulator(runtime_dir=runtime, poll_interval=0.05)
        sim.start()

        try:
            bridge = FileBasedBridge(
                runtime_dir=runtime,
                timeout_seconds=5,
                poll_interval_seconds=0.05,
            )
            engine = TeamEnvironmentManager(workspace=ws, bridge=bridge)
            engine.initialize(allow_onboarding=False, interactive=False)
            engine.start_run("test")
        finally:
            sim.stop()

        # 验证关键文件
        assert (runtime / "current-run.yaml").is_file()
        assert (runtime / "state" / "team.yaml").is_file()
        assert (runtime / "state" / "roster.yaml").is_file()
        assert (runtime / "state" / "members" / "developer.yaml").is_file()
        assert (runtime / "events.jsonl").is_file()

        # 验证成员 state 数据
        member_state = yaml.safe_load(
            (runtime / "state" / "members" / "developer.yaml").read_text()
        )
        assert member_state["name"] == "developer"
        assert member_state["role"] == "developer"


class TestE2EStandard:
    """Standard 档位的完整流程。"""

    def test_standard_team_composition(
        self,
        tmp_workspace: Path,
    ) -> None:
        _write_basic_config(tmp_workspace, mode="standard")
        runtime = tmp_workspace / ".ai-rd-team" / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)

        sim = BridgeSimulator(runtime_dir=runtime, poll_interval=0.05)
        sim.start()

        try:
            bridge = FileBasedBridge(
                runtime_dir=runtime,
                timeout_seconds=5,
                poll_interval_seconds=0.05,
            )
            engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
            engine.initialize(allow_onboarding=False, interactive=False)
            ctx = engine.start_run("实现用户管理")
        finally:
            sim.stop()

        # Standard = architect + developer × 2 + tester
        role_names = {m.role for m in ctx.members.values()}
        assert role_names == {"architect", "developer", "tester"}

        # developer 有 2 个实例
        dev_instances = [k for k in ctx.members if k.startswith("developer")]
        assert len(dev_instances) == 2


class TestE2EBridgeProtocol:
    """Bridge 协议边界行为验证。"""

    def test_custom_responder(
        self,
        prepared_workspace: tuple[Path, Path],
    ) -> None:
        """可注入自定义响应器模拟特殊场景。"""
        ws, runtime = prepared_workspace

        sim = BridgeSimulator(runtime_dir=runtime, poll_interval=0.05)

        custom_called = []

        def custom_team_create(intent):
            custom_called.append(intent)
            return {
                "team_name": intent["team_name"],
                "platform_id": "custom-id",
            }

        sim.register_responder("team_create", custom_team_create)
        sim.start()

        try:
            bridge = FileBasedBridge(
                runtime_dir=runtime,
                timeout_seconds=5,
                poll_interval_seconds=0.05,
            )
            engine = TeamEnvironmentManager(workspace=ws, bridge=bridge)
            engine.initialize(allow_onboarding=False, interactive=False)
            ctx = engine.start_run("test")
        finally:
            sim.stop()

        assert len(custom_called) == 1
        assert ctx.team_handle is not None
        assert ctx.team_handle.platform_id == "custom-id"

    def test_error_responder_propagates(
        self,
        prepared_workspace: tuple[Path, Path],
    ) -> None:
        """响应器抛异常 → Bridge 抛 BridgeToolError → Adapter 包装为 TeamOperationError。"""
        from ai_rd_team.adapter.base import TeamOperationError

        ws, runtime = prepared_workspace

        sim = BridgeSimulator(runtime_dir=runtime, poll_interval=0.05)

        def broken_create(_intent):
            raise RuntimeError("mock failure")

        sim.register_responder("team_create", broken_create)
        sim.start()

        try:
            bridge = FileBasedBridge(
                runtime_dir=runtime,
                timeout_seconds=5,
                poll_interval_seconds=0.05,
            )
            engine = TeamEnvironmentManager(workspace=ws, bridge=bridge)
            engine.initialize(allow_onboarding=False, interactive=False)

            with pytest.raises(TeamOperationError):
                engine.start_run("test")
        finally:
            sim.stop()


class TestMessageFileRecording:
    """验证 runtime/messages/ 记录正确。"""

    def test_start_message_recorded(
        self,
        prepared_workspace: tuple[Path, Path],
    ) -> None:
        ws, runtime = prepared_workspace

        sim = BridgeSimulator(runtime_dir=runtime, poll_interval=0.05)
        sim.start()

        try:
            bridge = FileBasedBridge(
                runtime_dir=runtime,
                timeout_seconds=5,
                poll_interval_seconds=0.05,
            )
            engine = TeamEnvironmentManager(workspace=ws, bridge=bridge)
            engine.initialize(allow_onboarding=False, interactive=False)
            engine.start_run("做一个日报系统")
        finally:
            sim.stop()

        # messages/ 下有记录
        messages = list((runtime / "messages").glob("*.json"))
        assert len(messages) >= 1

        # 首条应是 main → developer 的启动消息
        first = json.loads(messages[0].read_text(encoding="utf-8"))
        assert first["from"] == "main"
        assert first["to"] == "developer"
        assert "做一个日报系统" in first["content"]
