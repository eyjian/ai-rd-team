"""静态文件托管（Web 面板 HTML）。

Web 面板是单 HTML + Vue3 CDN 架构，打包进 Python 包分发：
  src/ai_rd_team/service/web/index.html
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, Response


def register_static(app: FastAPI) -> None:
    """注册前端静态文件路由。"""
    web_dir: Path = app.state.web_dir
    index_html = web_dir / "index.html"

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def root() -> HTMLResponse:
        if index_html.is_file():
            return HTMLResponse(content=index_html.read_text(encoding="utf-8"))
        return HTMLResponse(
            content=(
                "<html><body><h1>ai-rd-team</h1>"
                "<p>Web 面板未找到。请确认 src/ai_rd_team/service/web/index.html 存在。</p>"
                "</body></html>"
            ),
            status_code=404,
        )

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        # 避免 404 刷屏；返回空
        return Response(status_code=204)

    @app.get("/static/{filename:path}", include_in_schema=False, response_model=None)
    def static(filename: str):  # type: ignore[no-untyped-def]
        target = web_dir / filename
        if not target.is_file():
            return HTMLResponse(content="not found", status_code=404)
        return FileResponse(target)


__all__ = ["register_static"]
