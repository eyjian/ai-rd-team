"""写类 API 端点（T3.2）。

通过 EngineProxy 代理 Engine 调用。写类需要 Engine 处于 RUNNING（个别例外）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ai_rd_team.service.proxy import EngineProxy

logger = logging.getLogger(__name__)

router = APIRouter()


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    summary: str = ""
    from_member: str = "main"


class BroadcastRequest(BaseModel):
    content: str = Field(..., min_length=1)
    summary: str = ""
    from_member: str = "main"


class StopRunRequest(BaseModel):
    reason: str = "user-stopped"


class EscalateRequest(BaseModel):
    new_mode: str = Field(..., pattern="^(standard|full)$")


# ============================================================
# 成员消息
# ============================================================


@router.post("/team/members/{member_id}/message")
def send_message_to_member(
    request: Request,
    member_id: str,
    body: SendMessageRequest,
) -> dict:
    proxy = EngineProxy(request.app.state.engine)
    try:
        return proxy.send_message_to(
            member_id=member_id,
            content=body.content,
            summary=body.summary,
            from_member=body.from_member,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None


# ============================================================
# 广播
# ============================================================


@router.post("/team/broadcast")
def broadcast(request: Request, body: BroadcastRequest) -> dict:
    proxy = EngineProxy(request.app.state.engine)
    try:
        return proxy.broadcast(
            content=body.content,
            summary=body.summary,
            from_member=body.from_member,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None


# ============================================================
# 运行控制
# ============================================================


@router.post("/run/stop")
def stop_run(request: Request, body: StopRunRequest) -> dict:
    proxy = EngineProxy(request.app.state.engine)
    try:
        return proxy.stop_run(reason=body.reason)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None


@router.post("/run/escalate")
def escalate_run(request: Request, body: EscalateRequest) -> dict:
    proxy = EngineProxy(request.app.state.engine)
    try:
        return proxy.escalate_mode(new_mode=body.new_mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from None


__all__ = ["router"]
