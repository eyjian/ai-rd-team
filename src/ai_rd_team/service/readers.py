"""读类 API 端点（T3.2）。

设计原则（03-service-api.md §5.3）：
  读类 API 直接读 runtime/ 文件，不经过 Engine。
  好处：
  - 解耦 Web 与 Engine 的生命周期（Engine 不在也能看历史）
  - Engine 忙碌时不阻塞 Web
  - runtime/ 是 Single Source of Truth
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Query, Request

from ai_rd_team.service.proxy import EngineProxy

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# 辅助
# ============================================================


def _runtime(request: Request) -> Path:
    return request.app.state.runtime_dir  # type: ignore[no-any-return]


def _workspace(request: Request) -> Path:
    return request.app.state.workspace  # type: ignore[no-any-return]


def _read_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        logger.warning("yaml parse failed for %s: %s", path, e)
        return {}


def _read_jsonl(path: Path, limit: int = 200) -> list[dict]:
    if not path.is_file():
        return []
    entries: list[dict] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        logger.warning("read failed for %s: %s", path, e)
        return []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return entries


def _safe_path(base: Path, rel: str) -> Path:
    """防路径穿越：确保 rel 解析后仍在 base 内。"""
    if rel.startswith("/"):
        rel = rel.lstrip("/")
    target = (base / rel).resolve()
    try:
        target.relative_to(base.resolve())
    except ValueError as e:
        raise HTTPException(status_code=400, detail="path escapes base") from e
    return target


# ============================================================
# Run
# ============================================================


@router.get("/run/current")
def get_current_run(request: Request) -> dict:
    """当前运行状态（合并 current-run.yaml + Engine state）。"""
    runtime = _runtime(request)
    data = _read_yaml(runtime / "current-run.yaml")

    proxy = EngineProxy(request.app.state.engine)
    data["engine_state"] = proxy.state()
    data["engine_run"] = proxy.current_run()
    return data


# ============================================================
# Team
# ============================================================


@router.get("/team/state")
def get_team_state(request: Request) -> dict:
    return _read_yaml(_runtime(request) / "state" / "team.yaml")


@router.get("/team/roster")
def get_team_roster(request: Request) -> dict:
    return _read_yaml(_runtime(request) / "state" / "roster.yaml")


@router.get("/team/members")
def list_members(request: Request) -> dict:
    members_dir = _runtime(request) / "state" / "members"
    members = []
    if members_dir.is_dir():
        for f in sorted(members_dir.glob("*.yaml")):
            data = _read_yaml(f)
            if data:
                members.append(data)
    return {"members": members, "count": len(members)}


@router.get("/team/members/{member_id}")
def get_member(request: Request, member_id: str) -> dict:
    path = _runtime(request) / "state" / "members" / f"{member_id}.yaml"
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"member {member_id} not found")
    return _read_yaml(path)


@router.get("/team/messages")
def list_messages(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    messages_dir = _runtime(request) / "messages"
    if not messages_dir.is_dir():
        return {"messages": [], "count": 0}
    entries = []
    for f in sorted(messages_dir.glob("*.json"))[-limit:]:
        try:
            entries.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return {"messages": entries, "count": len(entries)}


# ============================================================
# Events
# ============================================================


@router.get("/events")
def list_events(
    request: Request,
    limit: int = Query(default=200, ge=1, le=2000),
) -> dict:
    """最近 N 条事件（倒序）。SSE 流见 /api/stream/events。"""
    entries = _read_jsonl(_runtime(request) / "events.jsonl", limit=limit)
    return {"events": entries, "count": len(entries)}


# ============================================================
# Artifacts
# ============================================================


@router.get("/artifacts")
def list_artifacts(request: Request) -> dict:
    artifacts_dir = _runtime(request) / "artifacts"
    if not artifacts_dir.is_dir():
        return {"artifacts": [], "count": 0, "manifest": {}}

    manifest = _read_yaml(artifacts_dir / "manifest.yaml")

    # 扫描文件
    files = []
    for p in artifacts_dir.rglob("*"):
        if p.is_file() and p.name not in ("manifest.yaml",):
            rel = p.relative_to(artifacts_dir)
            files.append(
                {
                    "path": str(rel).replace("\\", "/"),
                    "size": p.stat().st_size,
                    "category": rel.parts[0] if rel.parts else "",
                }
            )
    return {"artifacts": files, "count": len(files), "manifest": manifest}


@router.get("/artifacts/file")
def read_artifact_file(
    request: Request,
    path: str = Query(...),
) -> dict:
    base = _runtime(request) / "artifacts"
    target = _safe_path(base, path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    # 只读文本（二进制返回 null）
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {
            "path": path,
            "content": None,
            "binary": True,
            "size": target.stat().st_size,
        }
    return {
        "path": path,
        "content": content,
        "binary": False,
        "size": len(content),
    }


# ============================================================
# Memory
# ============================================================


@router.get("/memory/agent-d")
def list_agent_d(request: Request) -> dict:
    ws = _workspace(request)
    base = ws / ".ai-rd-team" / "memory" / "agent.d"
    return _list_memory_files(base)


@router.get("/memory/decisions")
def list_decisions(request: Request) -> dict:
    ws = _workspace(request)
    base = ws / ".ai-rd-team" / "memory" / "decisions"
    return _list_memory_files(base)


@router.get("/memory/memory-d")
def list_memory_d(request: Request) -> dict:
    ws = _workspace(request)
    base = ws / ".ai-rd-team" / "memory" / "memory.d"
    return _list_memory_files(base)


def _list_memory_files(base: Path) -> dict:
    if not base.is_dir():
        return {"files": [], "count": 0}
    files = []
    for p in sorted(base.rglob("*.md")):
        rel = p.relative_to(base)
        files.append(
            {
                "name": p.stem,
                "path": str(rel).replace("\\", "/"),
                "size": p.stat().st_size,
            }
        )
    return {"files": files, "count": len(files)}


@router.get("/memory/file")
def read_memory_file(
    request: Request,
    path: str = Query(...),
) -> dict:
    ws = _workspace(request)
    base = ws / ".ai-rd-team" / "memory"
    target = _safe_path(base, path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return {"path": path, "content": target.read_text(encoding="utf-8")}


# ============================================================
# Cost
# ============================================================


@router.get("/cost/snapshot")
def cost_snapshot(request: Request) -> dict:
    # 优先从 Engine 拿实时快照；退化读 resource-points.yaml
    proxy = EngineProxy(request.app.state.engine)
    snap = proxy.cost_snapshot()
    if snap is not None:
        return snap
    return _read_yaml(_runtime(request) / "cost" / "resource-points.yaml")


@router.get("/cost/history")
def cost_history(
    request: Request,
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    entries = _read_jsonl(_runtime(request) / "cost" / "post-run.jsonl", limit=limit)
    return {"runs": entries, "count": len(entries)}


@router.get("/cost/budget-check")
def cost_budget_check(request: Request) -> dict:
    """当前预算状态（action / reason / message）。"""
    proxy = EngineProxy(request.app.state.engine)
    result = proxy.check_budget()
    if result is None:
        return {"action": "unavailable", "reason": "none", "message": "engine not running"}
    return result


# ============================================================
# Config
# ============================================================


@router.get("/config/effective")
def get_effective_config(request: Request) -> dict:
    proxy = EngineProxy(request.app.state.engine)
    cfg = proxy.effective_config()
    if cfg is None:
        raise HTTPException(status_code=503, detail="engine not initialized")
    return cfg


@router.get("/config/basic")
def get_basic_config(request: Request) -> dict:
    ws = _workspace(request)
    return _read_yaml(ws / ".ai-rd-team" / "config.yaml")


@router.get("/config/advanced")
def get_advanced_config(request: Request) -> dict:
    ws = _workspace(request)
    return _read_yaml(ws / ".ai-rd-team" / "config.advanced.yaml")


# ============================================================
# Skills
# ============================================================


@router.get("/skills")
def list_skills(request: Request) -> dict:
    from ai_rd_team.roles.skills_loader import SkillsLoader

    ws = _workspace(request)
    loader = SkillsLoader.create_default(workspace=ws / ".ai-rd-team")
    return loader.list_available()


@router.get("/skills/file")
def read_skill_file(
    request: Request,
    scope: str = Query(...),
    name: str = Query(...),
) -> dict:
    from ai_rd_team.roles.skills_loader import SkillNotFoundError, SkillsLoader

    if scope not in ("builtin", "global", "workspace"):
        raise HTTPException(status_code=400, detail="invalid scope")
    ws = _workspace(request)
    loader = SkillsLoader.create_default(workspace=ws / ".ai-rd-team")
    try:
        skill = loader.load(f"{scope}:{name}")
    except SkillNotFoundError:
        raise HTTPException(status_code=404, detail=f"skill {scope}:{name} not found") from None
    return {
        "name": skill.name,
        "scope": skill.scope,
        "content": skill.content,
        "estimated_tokens": skill.estimated_tokens,
    }


# ============================================================
# Adapter 能力
# ============================================================


@router.get("/adapter/capabilities")
def adapter_capabilities(request: Request) -> dict:
    engine = request.app.state.engine
    if engine is None or engine._adapter is None:
        return {}
    caps = engine._adapter.capabilities
    return {
        "platform": engine._adapter.platform_name,
        "supports_broadcast": caps.supports_broadcast,
        "supports_shutdown_request": caps.supports_shutdown_request,
        "supports_role_specific_model": caps.supports_role_specific_model,
        "supports_member_state_query": caps.supports_member_state_query,
        "max_concurrent_members": caps.max_concurrent_members,
    }


__all__ = ["router"]
