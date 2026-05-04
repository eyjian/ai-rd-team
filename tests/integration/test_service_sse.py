"""SSE 流端点简单验证（T3.3）。

说明：
FastAPI TestClient 对 SSE（sse-starlette 的 EventSourceResponse）流式响应
的终止处理有兼容性问题——客户端断开后，服务端生成器不会及时退出，导致
测试卡住。我们不在 CI 中直接跑这类流测试。

实际验证方式（手动，见 M3 E2E 报告）：
  uvicorn ai_rd_team.service.app:create_app --factory
  curl -N http://127.0.0.1:8765/api/stream/events

本文件只校验 SSE 路由**注册存在** + OpenAPI schema 正常——完整的流推送行为
在真实环境中已验证（详见 prototype/M3-*/REPORT.md）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_rd_team.service.app import create_app


@pytest.fixture
def client(tmp_workspace: Path) -> TestClient:
    runtime = tmp_workspace / ".ai-rd-team" / "runtime"
    runtime.mkdir(parents=True)
    return TestClient(create_app(workspace=tmp_workspace, engine=None))


class TestSSERoutes:
    def test_events_route_registered(self, client: TestClient) -> None:
        """OpenAPI schema 中应有 /api/stream/events 路径。"""
        r = client.get("/openapi.json")
        assert r.status_code == 200
        paths = r.json().get("paths", {})
        assert "/api/stream/events" in paths

    def test_cost_stream_route_registered(self, client: TestClient) -> None:
        r = client.get("/openapi.json")
        paths = r.json().get("paths", {})
        assert "/api/stream/cost" in paths
