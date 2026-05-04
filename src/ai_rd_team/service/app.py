"""FastAPI 服务骨架（T3.1）。

对应设计文档：openspec/specs/design/03-service-api.md

M3 范围（MVP）：
- 读类端点（成员 / 消息 / 制品 / 成本 / 配置 / 事件）
- SSE 事件流 `/api/stream/events`
- 引擎命令：/api/team/members/{id}/message / /api/commands/broadcast
- 静态 HTML 托管

设计原则：
- 读类端点**直接读 runtime/ 文件**，不经过 Engine（单向数据流）
- 写类端点通过 ``EngineProxy`` 调用 Engine 方法
- 无鉴权（M3 只支持 127.0.0.1 本地使用）
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from ai_rd_team import __version__

logger = logging.getLogger(__name__)


def create_app(
    workspace: Path,
    engine: Any | None = None,
) -> FastAPI:
    """创建 FastAPI 应用实例。

    Args:
        workspace: 工作区根目录（``<workspace>/.ai-rd-team/runtime/`` 是主数据源）
        engine: 可选 TeamEnvironmentManager 实例。为 None 时只能提供只读功能。
    """
    app = FastAPI(
        title="ai-rd-team Service API",
        version=__version__,
        description="Web 面板的后端 API。读类端点直接读 runtime/ 文件，写类经引擎代理。",
    )

    # 工作区和 runtime 路径
    ws = workspace.resolve()
    runtime_dir = ws / ".ai-rd-team" / "runtime"

    app.state.workspace = ws
    app.state.runtime_dir = runtime_dir
    app.state.engine = engine
    app.state.web_dir = Path(__file__).resolve().parent / "web"

    # 注册路由模块
    from ai_rd_team.service import readers, streams, writers
    from ai_rd_team.service.static import register_static

    app.include_router(readers.router, prefix="/api", tags=["read"])
    app.include_router(writers.router, prefix="/api", tags=["write"])
    app.include_router(streams.router, prefix="/api/stream", tags=["stream"])
    register_static(app)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

    @app.get("/api/version")
    def version() -> dict:
        return {
            "service": "ai-rd-team",
            "version": __version__,
            "workspace": str(ws),
        }

    return app


__all__ = ["create_app"]
