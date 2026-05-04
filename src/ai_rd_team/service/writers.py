"""写类 API 端点（T3.2）。

通过 EngineProxy 代理 Engine 调用。写类需要 Engine 处于 RUNNING（个别例外）。
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ai_rd_team.config.inference import ConfigInference
from ai_rd_team.config.models import (
    BasicBudget,
    BasicConfig,
    BasicProject,
    BasicTechStack,
)
from ai_rd_team.config.onboarding import ConfigOnboarding
from ai_rd_team.runtime.state import utc_now_iso
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


class OnboardingInitRequest(BaseModel):
    """首次启动引导请求（T3.8a）。"""

    run_mode: str = Field("standard", pattern="^(lite|standard|full)$")
    description: str = ""
    tech_stack_backend: str | None = None
    tech_stack_frontend: str | None = None
    budget_per_run: int | None = Field(None, ge=1, le=100000)
    budget_per_day: int | None = Field(None, ge=1, le=1000000)


class BudgetAckRequest(BaseModel):
    """smart_pause 用户响应（T3.8b）。"""

    action: str = Field(..., pattern="^(continue|stop|raise_budget)$")
    raise_to: int | None = Field(None, ge=1, le=100000)


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


# ============================================================
# 首次启动引导（T3.8a）
# ============================================================


@router.get("/onboarding/status")
def onboarding_status(request: Request) -> dict:
    """返回当前工作区是否已完成初始化。

    - initialized: config.yaml 是否存在
    - has_advanced: config.advanced.yaml 是否存在
    - workspace: 工作区绝对路径（只读展示）
    - inferred: ConfigInference 对项目的识别结果（可选，用于引导展示）
    """
    ws = request.app.state.workspace  # type: ignore[attr-defined]
    config_path = ws / ".ai-rd-team" / "config.yaml"
    advanced_path = ws / ".ai-rd-team" / "config.advanced.yaml"

    inferred_summary: dict | None = None
    try:
        inf = ConfigInference().infer(ws)
        proficiency = inf.tech_stack.get("proficiency") or {}
        detected = [k for k, v in proficiency.items() if v]
        inferred_summary = {
            "project_name": inf.project.get("name"),
            "description": inf.project.get("description"),
            "detected_languages": detected[:5],  # 避免过长
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("inference failed: %s", e)

    return {
        "initialized": config_path.is_file(),
        "has_advanced": advanced_path.is_file(),
        "workspace": str(ws),
        "inferred": inferred_summary,
    }


@router.post("/onboarding/init")
def onboarding_init(request: Request, body: OnboardingInitRequest) -> dict:
    """非交互式生成 config.yaml（Web 引导提交）。

    若已存在则返回 409（需要手动删除或修改）。
    """
    ws = request.app.state.workspace  # type: ignore[attr-defined]
    config_path = ws / ".ai-rd-team" / "config.yaml"
    if config_path.exists():
        raise HTTPException(
            status_code=409,
            detail="config.yaml 已存在；请手动编辑或删除后再引导",
        )

    # 使用默认预算（若用户未指定）
    default_budgets = {
        "lite": (120, 500),
        "standard": (400, 1500),
        "full": (1500, 5000),
    }
    default_run, default_day = default_budgets[body.run_mode]

    inferred_desc = ""
    if not body.description:
        try:
            inferred_desc = ConfigInference().infer(ws).project.get("description", "") or ""
        except Exception:  # noqa: BLE001
            inferred_desc = ""

    basic = BasicConfig(
        config_version="1.0",
        project=BasicProject(description=body.description or inferred_desc),
        run_mode=body.run_mode,  # type: ignore[arg-type]
        tech_stack=BasicTechStack(
            backend=body.tech_stack_backend,
            frontend=body.tech_stack_frontend,
        ),
        budget=BasicBudget(
            per_run=body.budget_per_run or default_run,
            per_day=body.budget_per_day or default_day,
        ),
    )

    # 复用 ConfigOnboarding._write
    onboarding = ConfigOnboarding()
    onboarding._write(ws, basic)  # noqa: SLF001

    return {
        "ok": True,
        "config_path": str(config_path),
        "run_mode": basic.run_mode,
        "budget": {
            "per_run": basic.budget.per_run,
            "per_day": basic.budget.per_day,
        },
    }


# ============================================================
# smart_pause 响应（T3.8b）
# ============================================================


@router.post("/run/budget-ack")
def budget_ack(request: Request, body: BudgetAckRequest) -> dict:
    """响应 smart_pause 告警：continue / stop / raise_budget。

    M3 只做最简实现：
    - continue: 记录事件，由前端停止弹窗即可（Engine 不自动 pause）
    - stop: 等价 stop_run(reason="user-budget-stop")
    - raise_budget: 需要 raise_to，通过 CostTracker.raise_rp_budget 调整
    """
    engine = request.app.state.engine  # type: ignore[attr-defined]
    if engine is None:
        raise HTTPException(status_code=503, detail="engine not initialized")

    ws = request.app.state.workspace  # type: ignore[attr-defined]
    events_file = ws / ".ai-rd-team" / "runtime" / "events.jsonl"

    # 记录用户响应到 events.jsonl
    entry = {
        "ts": utc_now_iso(),
        "event": "budget_ack",
        "action": body.action,
        "raise_to": body.raise_to,
    }
    if events_file.is_file():
        try:
            with events_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning("append budget_ack event failed: %s", e)

    if body.action == "stop":
        proxy = EngineProxy(engine)
        try:
            return proxy.stop_run(reason="user-budget-stop")
        except RuntimeError as e:
            raise HTTPException(status_code=409, detail=str(e)) from None

    if body.action == "raise_budget":
        if body.raise_to is None:
            raise HTTPException(
                status_code=400,
                detail="raise_to is required when action=raise_budget",
            )
        cost_tracker = getattr(engine, "_cost_tracker", None)
        if cost_tracker is None or cost_tracker.snapshot() is None:
            raise HTTPException(status_code=409, detail="cost tracker not ready")
        try:
            new_value = cost_tracker.raise_rp_budget(body.raise_to)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None
        return {
            "ok": True,
            "action": "raise_budget",
            "new_rp_budget": new_value,
        }

    # continue：仅记录，不改状态
    return {"ok": True, "action": "continue"}


__all__ = ["router"]
