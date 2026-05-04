"""测试 CodeBuddyAdapter + Bridge。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from ai_rd_team.adapter.base import (
    AdapterInitError,
    MemberOperationError,
    MemberStatus,
    Message,
    MessageDeliveryError,
    MessageType,
    TeamOperationError,
    TeamStatus,
)
from ai_rd_team.adapter.bridge import (
    BridgeToolError,
    CodeBuddyToolBridge,
    InMemoryBridge,
)
from ai_rd_team.adapter.codebuddy import CodeBuddyAdapter


def _make_adapter(
    runtime_dir: Path,
    bridge: CodeBuddyToolBridge | None = None,
) -> tuple[CodeBuddyAdapter, CodeBuddyToolBridge]:
    bridge = bridge or InMemoryBridge()
    adapter = CodeBuddyAdapter(
        config={"spawn_timeout_seconds": 30},
        bridge=bridge,
        runtime_dir=runtime_dir,
    )
    return adapter, bridge


@pytest.fixture
def runtime_dir(tmp_workspace: Path) -> Path:
    d = tmp_workspace / ".ai-rd-team" / "runtime"
    d.mkdir(parents=True)
    return d


class TestInitialize:
    def test_initialize_success(self, runtime_dir: Path) -> None:
        adapter, _ = _make_adapter(runtime_dir)
        adapter.initialize()

        assert adapter.version_info.platform == "codebuddy"
        caps = adapter.capabilities
        assert caps.supports_p2p_messaging is True
        assert caps.supports_broadcast is True
        assert caps.supports_role_specific_model is False  # M1 不支持

    def test_initialize_fails_when_core_tools_missing(
        self,
        runtime_dir: Path,
    ) -> None:
        # 缺少 team_create
        bridge = InMemoryBridge(probe_tools={"task", "send_message"})
        adapter, _ = _make_adapter(runtime_dir, bridge=bridge)

        with pytest.raises(AdapterInitError):
            adapter.initialize()

    def test_platform_name(self, runtime_dir: Path) -> None:
        adapter, _ = _make_adapter(runtime_dir)
        assert adapter.platform_name == "codebuddy"


class TestTeamLifecycle:
    def test_create_team(self, runtime_dir: Path) -> None:
        adapter, bridge = _make_adapter(runtime_dir)
        adapter.initialize()

        team = adapter.create_team("run-001", description="test")
        assert team.team_id == "run-001"
        assert team.platform == "codebuddy"
        assert team.platform_id  # Bridge 分配了 ID

        # Bridge 记录了调用
        ops = [c["op"] for c in bridge.calls]  # type: ignore[attr-defined]
        assert "team_create" in ops

    def test_delete_team(self, runtime_dir: Path) -> None:
        adapter, bridge = _make_adapter(runtime_dir)
        adapter.initialize()
        team = adapter.create_team("run-001")

        adapter.delete_team(team)

        ops = [c["op"] for c in bridge.calls]  # type: ignore[attr-defined]
        assert "team_delete" in ops

    def test_get_team_status_no_state_file(self, runtime_dir: Path) -> None:
        adapter, _ = _make_adapter(runtime_dir)
        adapter.initialize()
        team = adapter.create_team("run-001")

        # 未写 state/team.yaml → CREATING
        status = adapter.get_team_status(team)
        assert status == TeamStatus.CREATING

    def test_get_team_status_from_state_file(self, runtime_dir: Path) -> None:
        adapter, _ = _make_adapter(runtime_dir)
        adapter.initialize()
        team = adapter.create_team("run-001")

        (runtime_dir / "state").mkdir(exist_ok=True)
        (runtime_dir / "state" / "team.yaml").write_text(
            yaml.safe_dump({"status": "running"}),
            encoding="utf-8",
        )

        assert adapter.get_team_status(team) == TeamStatus.RUNNING


class TestMember:
    def test_spawn_member(self, runtime_dir: Path) -> None:
        adapter, bridge = _make_adapter(runtime_dir)
        adapter.initialize()
        team = adapter.create_team("run-001")

        member = adapter.spawn_member(
            team=team,
            member_id="architect",
            role="architect",
            display_name="陈架构",
            rendered_prompt="你是架构师...",
        )

        assert member.member_id == "architect"
        assert member.role == "architect"
        assert member.display_name == "陈架构"
        assert member.team_id == "run-001"

        # Bridge 调用了 task
        task_calls = [
            c
            for c in bridge.calls
            if c["op"] == "task"  # type: ignore[attr-defined]
        ]
        assert len(task_calls) == 1
        assert task_calls[0]["name"] == "architect"
        assert task_calls[0]["team_name"] == "run-001"

    def test_get_member_status_no_file(self, runtime_dir: Path) -> None:
        """state 文件不存在 → SPAWNING。"""
        adapter, _ = _make_adapter(runtime_dir)
        adapter.initialize()

        from ai_rd_team.adapter.base import MemberHandle

        member = MemberHandle(
            member_id="dev_1",
            team_id="t",
            platform_id=None,
            role="developer",
            display_name="林小开",
            created_at=datetime.now(),
        )
        assert adapter.get_member_status(member) == MemberStatus.SPAWNING

    def test_get_member_status_from_state_file(self, runtime_dir: Path) -> None:
        adapter, _ = _make_adapter(runtime_dir)
        adapter.initialize()

        members_dir = runtime_dir / "state" / "members"
        members_dir.mkdir(parents=True)
        (members_dir / "architect.yaml").write_text(
            yaml.safe_dump({"name": "architect", "status": "working"}),
            encoding="utf-8",
        )

        from ai_rd_team.adapter.base import MemberHandle

        member = MemberHandle(
            member_id="architect",
            team_id="t",
            platform_id=None,
            role="architect",
            display_name="陈架构",
            created_at=datetime.now(),
        )
        assert adapter.get_member_status(member) == MemberStatus.WORKING

    def test_request_shutdown(self, runtime_dir: Path) -> None:
        adapter, bridge = _make_adapter(runtime_dir)
        adapter.initialize()
        team = adapter.create_team("r")
        member = adapter.spawn_member(
            team=team,
            member_id="m",
            role="developer",
            display_name="开发",
            rendered_prompt="...",
        )

        adapter.request_member_shutdown(member, reason="任务完成")

        shutdown_calls = [
            c
            for c in bridge.calls  # type: ignore[attr-defined]
            if c["op"] == "send_message" and c.get("type") == "shutdown_request"
        ]
        assert len(shutdown_calls) == 1
        assert shutdown_calls[0]["recipient"] == "m"


class TestSendMessage:
    def test_message_p2p(self, runtime_dir: Path) -> None:
        adapter, bridge = _make_adapter(runtime_dir)
        adapter.initialize()

        msg = Message(
            from_member="main",
            to_member="architect",
            msg_type=MessageType.MESSAGE,
            content="请开始设计",
            summary="启动任务",
        )
        adapter.send_message(msg)

        calls = [
            c
            for c in bridge.calls  # type: ignore[attr-defined]
            if c["op"] == "send_message" and c.get("type") == "message"
        ]
        assert len(calls) == 1
        assert calls[0]["recipient"] == "architect"
        assert calls[0]["content"] == "请开始设计"
        assert calls[0]["summary"] == "启动任务"

    def test_broadcast(self, runtime_dir: Path) -> None:
        adapter, bridge = _make_adapter(runtime_dir)
        adapter.initialize()

        msg = Message(
            from_member="main",
            to_member="all",
            msg_type=MessageType.BROADCAST,
            content="项目启动！",
        )
        adapter.send_message(msg)

        bcast = [
            c
            for c in bridge.calls  # type: ignore[attr-defined]
            if c["op"] == "send_message" and c.get("type") == "broadcast"
        ]
        assert len(bcast) == 1
        # broadcast 不需要 recipient
        assert "recipient" not in bcast[0]

    def test_message_size_limit(self, runtime_dir: Path) -> None:
        adapter, _ = _make_adapter(runtime_dir)
        adapter.initialize()

        # 用一段远超 64KB 的内容
        huge = "A" * (100 * 1024)
        msg = Message(
            from_member="main",
            to_member="architect",
            msg_type=MessageType.MESSAGE,
            content=huge,
        )
        with pytest.raises(MessageDeliveryError):
            adapter.send_message(msg)

    def test_default_summary_generated(self, runtime_dir: Path) -> None:
        adapter, bridge = _make_adapter(runtime_dir)
        adapter.initialize()

        msg = Message(
            from_member="main",
            to_member="architect",
            msg_type=MessageType.MESSAGE,
            content="请实现一个用户管理模块包括登录注册",
            # 故意不传 summary
        )
        adapter.send_message(msg)

        calls = [
            c
            for c in bridge.calls  # type: ignore[attr-defined]
            if c["op"] == "send_message"
        ]
        # 自动生成了 summary（≤10 字）
        assert calls[0]["summary"]
        assert len(calls[0]["summary"]) <= 10


class TestLogging:
    def test_adapter_calls_logged(self, runtime_dir: Path) -> None:
        adapter, _ = _make_adapter(runtime_dir)
        adapter.initialize()
        adapter.create_team("run-001")

        log_file = runtime_dir / "logs" / "adapter-calls.jsonl"
        assert log_file.is_file()

        lines = log_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert entry["platform"] == "codebuddy"
        assert entry["op"] == "create_team"
        assert entry["team_id"] == "run-001"


class TestBridgeErrorPropagation:
    """Bridge 抛异常 → Adapter 包装为业务异常。"""

    def test_team_create_bridge_error(self, runtime_dir: Path) -> None:
        class FailingBridge(InMemoryBridge):
            def call_team_create(self, team_name, description):  # type: ignore[no-untyped-def]
                raise BridgeToolError("mock failure")

        adapter, _ = _make_adapter(runtime_dir, bridge=FailingBridge())
        adapter.initialize()

        with pytest.raises(TeamOperationError):
            adapter.create_team("r")

    def test_spawn_member_bridge_timeout(self, runtime_dir: Path) -> None:
        class TimeoutBridge(InMemoryBridge):
            def call_task_async(self, **kwargs):  # type: ignore[no-untyped-def]
                raise TimeoutError("mock timeout")

        adapter, _ = _make_adapter(runtime_dir, bridge=TimeoutBridge())
        adapter.initialize()
        team = adapter.create_team("r")

        with pytest.raises(MemberOperationError):
            adapter.spawn_member(
                team=team,
                member_id="m",
                role="developer",
                display_name="x",
                rendered_prompt="p",
            )
