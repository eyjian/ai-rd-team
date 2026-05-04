"""EngineProxy：Web 层与 Engine 交互的中间层（T3.1）。

对应设计文档：03-service-api.md §5.2

设计目的：
- 封装对 Engine 的调用，便于测试时注入 Fake Engine
- 把 Engine 的返回值转成 API 友好的 dict（无 dataclass、无 enum）
- 统一错误处理（调用失败返回 None，由上层决定 404 or 500）

注意：M3 不做写类并发控制。Engine 自身状态机（EngineState）负责。
"""

from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class EngineProxy:
    """对 TeamEnvironmentManager 的薄封装。"""

    def __init__(self, engine: Any | None):
        self._engine = engine

    @property
    def available(self) -> bool:
        return self._engine is not None

    # ------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------

    def state(self) -> str:
        if self._engine is None:
            return "unavailable"
        state = self._engine.state
        return state.value if isinstance(state, Enum) else str(state)

    def current_run(self) -> dict | None:
        if self._engine is None:
            return None
        ctx = self._engine.get_current_run()
        if ctx is None:
            return None
        return {
            "run_id": ctx.run_id,
            "mode": ctx.mode,
            "started_at": ctx.started_at.isoformat(),
            "requirement": ctx.requirement,
            "team_id": ctx.team_handle.team_id if ctx.team_handle else None,
            "member_ids": list(ctx.members.keys()),
        }

    def cost_snapshot(self) -> dict | None:
        if self._engine is None:
            return None
        snap = self._engine.cost_snapshot()
        if snap is None:
            return None
        return _to_dict(snap)

    def check_budget(self) -> dict | None:
        if self._engine is None:
            return None
        res = self._engine.check_budget()
        if res is None:
            return None
        return {
            "action": res.action.value,
            "reason": res.reason.value,
            "message": res.message,
            "snapshot": _to_dict(res.snapshot),
        }

    def effective_config(self) -> dict | None:
        if self._engine is None:
            return None
        try:
            cfg = self._engine.config
        except RuntimeError:
            return None
        return _effective_config_to_dict(cfg)

    # ------------------------------------------------------------
    # 写类操作
    # ------------------------------------------------------------

    def send_message_to(
        self,
        member_id: str,
        content: str,
        summary: str = "",
        from_member: str = "main",
    ) -> dict:
        """通过 Engine 的 Adapter 向成员发消息。"""
        if self._engine is None:
            raise RuntimeError("engine unavailable")
        ctx = self._engine.get_current_run()
        if ctx is None:
            raise RuntimeError("no active run")
        if member_id not in ctx.members:
            raise LookupError(f"member {member_id!r} not found")

        from ai_rd_team.adapter.base import Message, MessageType

        msg = Message(
            from_member=from_member,
            to_member=member_id,
            msg_type=MessageType.MESSAGE,
            content=content,
            summary=summary,
        )
        self._engine._adapter.send_message(msg)  # type: ignore[union-attr]
        # 同步写 runtime/messages/
        if self._engine._runtime_state is not None:
            self._engine._runtime_state.write_message_record(
                from_member=from_member,
                to_member=member_id,
                msg_type="message",
                content=content,
                summary=summary,
            )
        # 成本
        if self._engine._cost_tracker is not None:
            self._engine._cost_tracker.record_message(
                from_=from_member, to=member_id, msg_type="message"
            )
        return {"ok": True}

    def broadcast(
        self,
        content: str,
        summary: str = "",
        from_member: str = "main",
    ) -> dict:
        if self._engine is None:
            raise RuntimeError("engine unavailable")
        self._engine.broadcast(content=content, summary=summary, from_member=from_member)
        return {"ok": True}

    def stop_run(self, reason: str = "user-stopped") -> dict:
        if self._engine is None:
            raise RuntimeError("engine unavailable")
        self._engine.stop_run(reason=reason)
        return {"ok": True, "state": self.state()}

    def escalate_mode(self, new_mode: str) -> dict:
        if self._engine is None:
            raise RuntimeError("engine unavailable")
        if new_mode not in ("lite", "standard", "full"):
            raise ValueError(f"invalid mode: {new_mode}")
        ctx = self._engine.escalate_mode(new_mode)  # type: ignore[arg-type]
        return {
            "ok": True,
            "new_mode": ctx.mode,
            "member_count": len(ctx.members),
        }


# ============================================================
# 转换辅助
# ============================================================


def _to_dict(obj: Any) -> dict:
    """把 dataclass/Enum → JSON 友好的 dict。"""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if is_dataclass(obj):
        return {k: _sanitize(v) for k, v in asdict(obj).items()}
    return {"value": str(obj)}


def _sanitize(v: Any) -> Any:
    if isinstance(v, Enum):
        return v.value
    if is_dataclass(v):
        return {k: _sanitize(x) for k, x in asdict(v).items()}
    if isinstance(v, dict):
        return {k: _sanitize(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_sanitize(x) for x in v]
    return v


def _effective_config_to_dict(cfg: Any) -> dict:
    """EffectiveConfig 比较复杂（含嵌套 dataclass + RunMode 属性），手工挑关键字段。"""
    from ai_rd_team.config.models import EffectiveConfig

    if not isinstance(cfg, EffectiveConfig):
        return {}

    return {
        "config_version": cfg.config_version,
        "active_mode": cfg.active_mode,
        "active_budget": _to_dict(cfg.active_budget),
        "project": _to_dict(cfg.project),
        "roles": {
            name: {
                "name": role.name,
                "display_name": role.display_name,
                "enabled": role.enabled,
                "scalable": role.scalable,
                "default_instances": role.default_instances,
                "max_instances": role.max_instances,
                "skills": list(role.skills),
                "memory_scope": dict(role.memory_scope),
            }
            for name, role in cfg.roles.items()
        },
        "tech_stack": dict(cfg.tech_stack),
        "cost_control": {
            "billing_mode": cfg.cost_control.billing_mode,
            "display_currency": cfg.cost_control.display_currency,
            "budget_lite": _to_dict(cfg.cost_control.budget_lite),
            "budget_standard": _to_dict(cfg.cost_control.budget_standard),
            "budget_full": _to_dict(cfg.cost_control.budget_full),
            "quota_windows": _to_dict(cfg.cost_control.quota_windows),
        },
        "web": dict(cfg.web),
    }


__all__ = ["EngineProxy"]
