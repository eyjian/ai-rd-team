"""测试 BaseAdapter 的值对象、能力检查、异常等。"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from ai_rd_team.adapter.base import (
    AdapterError,
    BaseAdapter,
    Capabilities,
    Message,
    MessageType,
)


class _MinimalAdapter(BaseAdapter):
    """最小实现，用于测试 BaseAdapter 的非抽象行为。"""

    def initialize(self) -> None:
        self._version_info = None  # 仍保留未初始化以测异常
        self._capabilities = None

    def create_team(self, team_id, description=""):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def delete_team(self, team):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def get_team_status(self, team):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def spawn_member(self, *a, **kw):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def request_member_shutdown(self, *a, **kw):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def get_member_status(self, member):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def send_message(self, msg):  # type: ignore[no-untyped-def]
        raise NotImplementedError


class TestValueObjects:
    def test_message_is_frozen(self) -> None:
        msg = Message(
            from_member="main",
            to_member="architect",
            msg_type=MessageType.MESSAGE,
            content="hi",
        )
        with pytest.raises(FrozenInstanceError):
            msg.content = "bye"  # type: ignore[misc]

    def test_message_default_ts(self) -> None:
        msg = Message(
            from_member="main",
            to_member="architect",
            msg_type=MessageType.MESSAGE,
            content="hi",
        )
        assert isinstance(msg.ts, datetime)

    def test_capabilities_defaults_conservative(self) -> None:
        """默认所有能力都 False（符合基类的保守假设）。"""
        caps = Capabilities()
        assert caps.supports_p2p_messaging is False
        assert caps.supports_broadcast is False
        assert caps.supports_team_lifecycle is False
        assert caps.max_concurrent_members == 1


class TestBaseAdapterHelpers:
    def test_platform_name_from_class_name(self) -> None:
        a = _MinimalAdapter(config={})
        # _MinimalAdapter → "_minimal"
        assert "minimal" in a.platform_name.lower()

    def test_access_capabilities_before_init_raises(self) -> None:
        a = _MinimalAdapter(config={})
        with pytest.raises(AdapterError):
            _ = a.capabilities

    def test_access_version_before_init_raises(self) -> None:
        a = _MinimalAdapter(config={})
        with pytest.raises(AdapterError):
            _ = a.version_info

    def test_validate_capabilities_returns_missing(self) -> None:
        a = _MinimalAdapter(config={})
        # 手工设置 capabilities 以便测试
        a._capabilities = Capabilities(
            supports_team_lifecycle=True,
            supports_p2p_messaging=False,
        )

        missing = a.validate_capabilities_for(
            {
                "supports_team_lifecycle": True,
                "supports_p2p_messaging": True,
                "supports_broadcast": True,
            }
        )
        assert "supports_team_lifecycle" not in missing
        assert "supports_p2p_messaging" in missing
        assert "supports_broadcast" in missing

    def test_validate_capabilities_empty_when_all_ok(self) -> None:
        a = _MinimalAdapter(config={})
        a._capabilities = Capabilities(
            supports_team_lifecycle=True,
            supports_p2p_messaging=True,
        )
        missing = a.validate_capabilities_for(
            {"supports_team_lifecycle": True, "supports_p2p_messaging": True}
        )
        assert missing == []

    def test_switch_model_default_unsupported(self) -> None:
        from ai_rd_team.adapter.base import (
            CapabilityNotSupportedError,
            MemberHandle,
        )

        a = _MinimalAdapter(config={})
        member = MemberHandle(
            member_id="x",
            team_id="t",
            platform_id=None,
            role="dev",
            display_name="X",
            created_at=datetime.now(),
        )
        with pytest.raises(CapabilityNotSupportedError):
            a.switch_member_model(member, "some-model")
