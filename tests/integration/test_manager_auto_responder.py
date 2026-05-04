"""TeamEnvironmentManager 与 AutoBridgeResponder 集成测试（M5）。

覆盖：
- 默认配置下（CodeBuddyAdapter + auto_bridge 未设置）启动 responder
- 显式 auto_bridge=false 不启动
- 非 CodeBuddyAdapter（注入 fake）不启动
- stop_run 后 responder 线程干净退出
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai_rd_team.adapter.base import (
    BaseAdapter,
    Capabilities,
    MemberHandle,
    MemberStatus,
    Message,
    TeamHandle,
    TeamStatus,
    VersionInfo,
)
from ai_rd_team.adapter.bridge import FileBasedBridge, InMemoryBridge
from ai_rd_team.adapter.bridge_simulator import BridgeSimulator
from ai_rd_team.engine.manager import TeamEnvironmentManager


def _write_config(ws: Path, **adapter_overrides: object) -> None:
    """写 Basic config.yaml；adapter 高级选项只能走 config.advanced.yaml（Basic schema 无 adapter 字段）。"""
    d = ws / ".ai-rd-team"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "config_version": "1.0",
                "run_mode": "lite",
                "project": {"description": "M5 集成测试"},
                "budget": {"per_run": 120, "per_day": 500},
            }
        ),
        encoding="utf-8",
    )
    # adapter 高级选项走 advanced
    adapter_section: dict = {"bridge_timeout_seconds": 5}
    adapter_section.update(adapter_overrides)
    (d / "config.advanced.yaml").write_text(
        yaml.safe_dump(
            {
                "config_version": "1.0",
                "adapter": adapter_section,
            }
        ),
        encoding="utf-8",
    )


# ============================================================
# Fake adapter：用于验证"非 CodeBuddyAdapter 时不启用 responder"
# ============================================================


class FakeAdapter(BaseAdapter):
    """最小 fake adapter，不继承 CodeBuddyAdapter。"""

    PLATFORM = "fake-platform"

    def __init__(self, config: dict) -> None:
        super().__init__(config)

    def initialize(self) -> None:
        from datetime import datetime

        self._version_info = VersionInfo(
            platform=self.PLATFORM,
            version="fake-1.0",
            detected_at=datetime.now(),
            available_tools=frozenset({"team_create", "team_delete", "task", "send_message"}),
        )
        self._capabilities = Capabilities(
            supports_team_lifecycle=True,
            supports_async_member_spawn=True,
            supports_p2p_messaging=True,
            supports_broadcast=True,
            supports_shutdown_request=True,
            supports_role_specific_model=False,
            supports_runtime_model_switch=False,
            supports_member_state_query=False,
            max_concurrent_members=4,
            message_size_limit_bytes=16 * 1024,
            spawn_timeout_seconds=30,
        )

    def create_team(self, team_id: str, description: str = "") -> TeamHandle:
        from datetime import datetime

        return TeamHandle(
            team_id=team_id,
            platform_id=team_id,
            created_at=datetime.now(),
            platform=self.PLATFORM,
        )

    def delete_team(self, team: TeamHandle) -> None:
        pass

    def get_team_status(self, team: TeamHandle) -> TeamStatus:
        return TeamStatus.RUNNING

    def spawn_member(
        self,
        team: TeamHandle,
        member_id: str,
        role: str,
        display_name: str,
        rendered_prompt: str,
        options: dict | None = None,
    ) -> MemberHandle:
        from datetime import datetime

        return MemberHandle(
            member_id=member_id,
            team_id=team.team_id,
            platform_id=member_id,
            role=role,
            display_name=display_name,
            created_at=datetime.now(),
        )

    def request_member_shutdown(self, member: MemberHandle, reason: str = "") -> None:
        pass

    def get_member_status(self, member: MemberHandle) -> MemberStatus:
        return MemberStatus.IDLE

    def send_message(self, msg: Message) -> None:
        pass


# ============================================================
# 测试
# ============================================================


@pytest.fixture
def prepared_workspace(tmp_workspace: Path) -> tuple[Path, Path]:
    _write_config(tmp_workspace)
    runtime = tmp_workspace / ".ai-rd-team" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    return tmp_workspace, runtime


class TestAutoResponderIntegration:
    def test_enabled_by_default_with_codebuddy_adapter(
        self, prepared_workspace: tuple[Path, Path]
    ) -> None:
        ws, runtime = prepared_workspace

        # 用 InMemoryBridge，initialize 后 F 优化不会调 bridge
        bridge = InMemoryBridge()
        engine = TeamEnvironmentManager(workspace=ws, bridge=bridge)
        engine.initialize(allow_onboarding=False, interactive=False)

        assert engine._auto_responder is not None
        assert engine._auto_responder._thread is not None
        assert engine._auto_responder._thread.is_alive()

        # 清理
        engine._auto_responder.stop(timeout=1.0)

    def test_disabled_when_auto_bridge_false(self, tmp_workspace: Path) -> None:
        _write_config(tmp_workspace, auto_bridge=False)
        runtime = tmp_workspace / ".ai-rd-team" / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)

        bridge = InMemoryBridge()
        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
        engine.initialize(allow_onboarding=False, interactive=False)

        assert engine._auto_responder is None

    def test_disabled_for_non_codebuddy_adapter(
        self, prepared_workspace: tuple[Path, Path]
    ) -> None:
        ws, _ = prepared_workspace

        fake = FakeAdapter(config={})
        engine = TeamEnvironmentManager(workspace=ws, adapter=fake)
        engine.initialize(allow_onboarding=False, interactive=False)

        assert engine._auto_responder is None

    def test_stopped_cleanly_after_full_run(self, prepared_workspace: tuple[Path, Path]) -> None:
        """集成：真实 FileBasedBridge + BridgeSimulator 跑完整 run，验证 responder 干净退出。"""
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

            # auto-responder 已启动
            assert engine._auto_responder is not None
            t = engine._auto_responder._thread
            assert t is not None and t.is_alive()

            engine.start_run(requirement="做一个计算器")
            engine.stop_run(reason="test")

            # stop_run 后 responder 应已被置空且线程结束
            assert engine._auto_responder is None
            assert not t.is_alive()
        finally:
            sim.stop()
