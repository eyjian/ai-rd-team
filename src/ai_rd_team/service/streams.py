"""SSE 实时事件推送（T3.3）。

对应设计文档：03-service-api.md §6

实现：
- 轮询 runtime/events.jsonl 文件位置，新追加的行推给客户端
- 每 30 秒发 keep-alive 注释防断连
- Last-Event-ID header 支持断线续传（基于行号）
- 使用 sse-starlette 的 EventSourceResponse
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)

router = APIRouter()

KEEP_ALIVE_INTERVAL = 30  # 秒
POLL_INTERVAL = 0.5  # 秒


async def _events_generator(
    events_file: Path,
    start_line: int = 0,
    disconnect_check=None,
):
    """异步生成 events.jsonl 的新行。"""
    last_line = start_line
    last_ka = asyncio.get_event_loop().time()

    while True:
        if disconnect_check is not None and await disconnect_check():
            logger.debug("SSE client disconnected")
            break

        # 读文件
        if events_file.is_file():
            try:
                lines = events_file.read_text(encoding="utf-8").splitlines()
            except OSError as e:
                logger.warning("read events failed: %s", e)
                lines = []
            if len(lines) > last_line:
                for i in range(last_line, len(lines)):
                    line = lines[i].strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    yield {
                        "id": str(i + 1),
                        "event": data.get("event", "message"),
                        "data": json.dumps(data, ensure_ascii=False),
                    }
                last_line = len(lines)
                last_ka = asyncio.get_event_loop().time()

        # keep-alive
        now = asyncio.get_event_loop().time()
        if now - last_ka >= KEEP_ALIVE_INTERVAL:
            yield {
                "event": "keep-alive",
                "data": json.dumps({"ts": now}),
            }
            last_ka = now

        await asyncio.sleep(POLL_INTERVAL)


@router.get("/events")
async def stream_events(request: Request) -> EventSourceResponse:
    """SSE 事件流：订阅 runtime/events.jsonl 的新增事件。

    支持 ``Last-Event-ID`` 头部（值为行号）作为断点续传锚。
    """
    runtime_dir = request.app.state.runtime_dir
    events_file = runtime_dir / "events.jsonl"

    start_line = 0
    last_id = request.headers.get("last-event-id")
    if last_id:
        try:
            start_line = int(last_id)
        except ValueError:
            start_line = 0

    async def disconnect() -> bool:
        return await request.is_disconnected()

    return EventSourceResponse(
        _events_generator(
            events_file=events_file,
            start_line=start_line,
            disconnect_check=disconnect,
        )
    )


@router.get("/cost")
async def stream_cost(request: Request) -> EventSourceResponse:
    """SSE 成本快照：定期推送 resource-points.yaml 的当前值。"""
    import yaml

    runtime_dir = request.app.state.runtime_dir
    cost_file = runtime_dir / "cost" / "resource-points.yaml"

    async def disconnect() -> bool:
        return await request.is_disconnected()

    async def gen():
        last_payload = ""
        while True:
            if await disconnect():
                break
            if cost_file.is_file():
                try:
                    data = yaml.safe_load(cost_file.read_text(encoding="utf-8")) or {}
                except (OSError, yaml.YAMLError):
                    data = {}
                payload = json.dumps(data, ensure_ascii=False)
                if payload != last_payload:
                    last_payload = payload
                    yield {"event": "cost", "data": payload}
            await asyncio.sleep(1.0)

    return EventSourceResponse(gen())


__all__ = ["router"]
