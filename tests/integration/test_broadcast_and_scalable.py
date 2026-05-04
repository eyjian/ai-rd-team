"""Broadcast 功能测试（T2.6）。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai_rd_team.adapter.base import (
    Capabilities,
    CapabilityNotSupportedError,
    Message,
    TeamHandle,
    VersionInfo,
)
from ai_rd_team.adapter.bridge import InMemoryBridge
from ai_rd_team.adapter.codebuddy import CodeBuddyAdapter
from ai_rd_team.engine.manager import TeamEnvironmentManager


def _write_basic_config(ws: Path, mode: str = "standard") -> None:
    d = ws / ".ai-rd-team"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "config_version": "1.0",
                "run_mode": mode,
                "project": {"description": "测试广播"},
                "budget": {"per_run": 400, "per_day": 2000},
            }
        ),
        encoding="utf-8",
    )


class TestAdapterBroadcast:
    def test_broadcast_sends_broadcast_message(
        self, tmp_workspace: Path
    ) -> None:
        bridge = InMemoryBridge()
        adapter = CodeBuddyAdapter(
            config={},
            bridge=bridge,
            runtime_dir=tmp_workspace / ".ai-rd-team" / "runtime",
        )
        adapter.initialize()
        adapter.broadcast(content="all hands on deck", summary="通知")

        sends = [
            c
            for c in bridge.calls
            if c["op"] == "send_message" and c.get("type") == "broadcast"
        ]
        assert len(sends) == 1
        assert sends[0]["content"] == "all hands on deck"

    def test_broadcast_raises_when_not_supported(self) -> None:
        """能力不支持时应抛 CapabilityNotSupportedError。"""
        from datetime import datetime

        from ai_rd_team.adapter.base import BaseAdapter, TeamStatus

        class StubAdapter(BaseAdapter):
            PLATFORM = "stub"

            def initialize(self) -> None:  # type: ignore[override]
                self._capabilities = Capabilities(supports_broadcast=False)
                self._version = VersionInfo(
                    platform="stub",
                    version="0.1.0",
                    detected_at=datetime.now(),
                )

            def create_team(self, team_id: str, description: str = "") -> TeamHandle:  # type: ignore[override]
                raise NotImplementedError

            def delete_team(self, team: TeamHandle) -> None:  # type: ignore[override]
                raise NotImplementedError

            def get_team_status(self, team: TeamHandle) -> TeamStatus:  # type: ignore[override]
                return TeamStatus.SHUT_DOWN

            def spawn_member(  # type: ignore[override]
                self, team, member_id, role, display_name, rendered_prompt
            ):
                raise NotImplementedError

            def request_member_shutdown(  # type: ignore[override]
                self, member, reason=""
            ):
                raise NotImplementedError

            def get_member_status(self, member):  # type: ignore[override]
                raise NotImplementedError

            def send_message(self, msg: Message) -> None:  # type: ignore[override]
                raise NotImplementedError

        adapter = StubAdapter(config={})
        adapter.initialize()

        with pytest.raises(CapabilityNotSupportedError):
            adapter.broadcast(content="hello")


class TestEngineBroadcast:
    def test_engine_broadcast_records_event_and_message(
        self, tmp_workspace: Path
    ) -> None:
        _write_basic_config(tmp_workspace, mode="standard")
        bridge = InMemoryBridge()
        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")

        engine.broadcast(content="集合开会", summary="开会")

        # bridge 收到 broadcast 调用
        sends = [
            c
            for c in bridge.calls
            if c["op"] == "send_message" and c.get("type") == "broadcast"
        ]
        assert len(sends) == 1

        # runtime/messages/ 有记录（文件中 "to": "*"）
        import json

        messages_dir = (
            tmp_workspace / ".ai-rd-team" / "runtime" / "messages"
        )
        bcast_records = []
        for p in messages_dir.glob("*.json"):
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("type") == "broadcast":
                bcast_records.append(data)
        assert len(bcast_records) == 1
        assert bcast_records[0]["from"] == "main"
        assert bcast_records[0]["to"] == "*"
        assert bcast_records[0]["content"] == "集合开会"

        # events.jsonl 包含 broadcast_sent
        events_file = (
            tmp_workspace / ".ai-rd-team" / "runtime" / "events.jsonl"
        )
        events = [
            json.loads(line)
            for line in events_file.read_text().splitlines()
        ]
        assert any(e["event"] == "broadcast_sent" for e in events)

    def test_broadcast_fails_before_start(
        self, tmp_workspace: Path
    ) -> None:
        _write_basic_config(tmp_workspace, mode="standard")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace, bridge=InMemoryBridge()
        )
        engine.initialize(allow_onboarding=False, interactive=False)

        with pytest.raises(RuntimeError):
            engine.broadcast(content="no run yet")


class TestScalableInstances:
    """T2.5：可伸缩角色的档位感知 + 配置覆盖。"""

    def test_lite_limits_to_one(self, tmp_workspace: Path) -> None:
        _write_basic_config(tmp_workspace, mode="lite")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace, bridge=InMemoryBridge()
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        ctx = engine.start_run("test")
        dev_members = [m for m in ctx.members if m.startswith("developer")]
        assert len(dev_members) == 1

    def test_standard_caps_at_two(self, tmp_workspace: Path) -> None:
        _write_basic_config(tmp_workspace, mode="standard")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace, bridge=InMemoryBridge()
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        ctx = engine.start_run("test")
        dev_members = [m for m in ctx.members if m.startswith("developer")]
        # builtin developer default_instances=2, standard 取 min(2,2)=2
        assert len(dev_members) == 2

    def test_full_uses_default_instances(self, tmp_workspace: Path) -> None:
        """Full 档：developer 应使用其 default_instances（默认 2）。"""
        _write_basic_config(tmp_workspace, mode="full")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace, bridge=InMemoryBridge()
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        ctx = engine.start_run("test")
        dev_members = [m for m in ctx.members if m.startswith("developer")]
        assert len(dev_members) == 2  # builtin default_instances=2
        # Full 档还有其他角色
        assert "pm" in ctx.members
        assert "analyst" in ctx.members
        assert "architect" in ctx.members
        assert any(m.startswith("reviewer") for m in ctx.members)
        assert any(m.startswith("tester") for m in ctx.members)
        assert "devops" in ctx.members
