"""Web 服务层：FastAPI + SSE（M3）。

对应设计文档：
- openspec/specs/design/03-service-api.md
- openspec/specs/design/04-web-panel.md

主入口：``create_app(workspace, engine)``
"""

from ai_rd_team.service.app import create_app
from ai_rd_team.service.proxy import EngineProxy

__all__ = ["EngineProxy", "create_app"]
