"""测试 EngineProxy 和集成 Engine 的 Service API。"""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from ai_rd_team.adapter.bridge import InMemoryBridge
from ai_rd_team.engine.manager import TeamEnvironmentManager
from ai_rd_team.service.app import create_app
from ai_rd_team.service.proxy import EngineProxy


def _write_basic_config(ws: Path) -> None:
    d = ws / ".ai-rd-team"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "config_version": "1.0",
                "run_mode": "lite",
                "project": {"description": "Service API 集成测试"},
                "budget": {"per_run": 120, "per_day": 500},
            }
        ),
        encoding="utf-8",
    )


class TestEngineProxy:
    def test_unavailable_when_no_engine(self) -> None:
        p = EngineProxy(None)
        assert not p.available
        assert p.state() == "unavailable"
        assert p.current_run() is None
        assert p.cost_snapshot() is None

    def test_with_initialized_engine(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        _write_basic_config(tmp_workspace)
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        p = EngineProxy(engine)

        assert p.state() == "idle"
        assert p.current_run() is None  # 未 start
        cfg = p.effective_config()
        assert cfg is not None
        assert cfg["active_mode"] == "lite"

    def test_with_running_engine(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        _write_basic_config(tmp_workspace)
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")
        p = EngineProxy(engine)

        assert p.state() == "running"
        run = p.current_run()
        assert run is not None
        assert run["mode"] == "lite"
        assert "developer" in run["member_ids"]

        snap = p.cost_snapshot()
        assert snap is not None
        assert snap["member_spawn_count"] == 1

        bc = p.check_budget()
        assert bc is not None
        assert bc["action"] == "continue"


class TestServiceWithEngine:
    def _app_with_engine(
        self, tmp_workspace: Path, tmp_quota_home: Path, start_run: bool = False
    ) -> tuple[TestClient, TeamEnvironmentManager]:
        _write_basic_config(tmp_workspace)
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        if start_run:
            engine.start_run("API 集成测试")

        app = create_app(workspace=tmp_workspace, engine=engine)
        return TestClient(app), engine

    def test_effective_config_available(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        client, _ = self._app_with_engine(tmp_workspace, tmp_quota_home)
        r = client.get("/api/config/effective")
        assert r.status_code == 200
        data = r.json()
        assert data["active_mode"] == "lite"
        # roles 默认空（用户未在 config.yaml 声明）；Engine 的 _resolve_role 会回退到 builtin_roles
        assert "roles" in data
        assert "active_budget" in data
        assert data["active_budget"]["max_resource_points"] == 120

    def test_cost_snapshot_from_engine(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        client, _ = self._app_with_engine(tmp_workspace, tmp_quota_home, start_run=True)
        r = client.get("/api/cost/snapshot")
        assert r.status_code == 200
        data = r.json()
        # start_run 后：1 spawn + 1 message
        assert data["resource_points"] == 42
        assert data["mode"] == "lite"

    def test_budget_check(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        client, _ = self._app_with_engine(tmp_workspace, tmp_quota_home, start_run=True)
        r = client.get("/api/cost/budget-check")
        assert r.status_code == 200
        assert r.json()["action"] == "continue"

    def test_adapter_capabilities(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        client, _ = self._app_with_engine(tmp_workspace, tmp_quota_home)
        r = client.get("/api/adapter/capabilities")
        assert r.status_code == 200
        caps = r.json()
        assert caps["platform"] == "codebuddy"
        assert caps["supports_broadcast"] is True

    def test_send_message_to_member(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        client, engine = self._app_with_engine(tmp_workspace, tmp_quota_home, start_run=True)
        r = client.post(
            "/api/team/members/developer/message",
            json={"content": "你好", "summary": "问候"},
        )
        assert r.status_code == 200
        assert r.json()["ok"] is True

        # 验证 cost 增加了 1 条消息
        snap = engine.cost_snapshot()
        assert snap.message_count == 2  # 启动消息 + 本次

    def test_send_message_member_not_found(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        client, _ = self._app_with_engine(tmp_workspace, tmp_quota_home, start_run=True)
        r = client.post(
            "/api/team/members/ghost/message",
            json={"content": "hi"},
        )
        assert r.status_code == 404

    def test_broadcast(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        client, engine = self._app_with_engine(tmp_workspace, tmp_quota_home, start_run=True)
        r = client.post("/api/team/broadcast", json={"content": "集合"})
        assert r.status_code == 200

        snap = engine.cost_snapshot()
        assert snap.broadcast_count == 1

    def test_stop_run_via_api(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        client, engine = self._app_with_engine(tmp_workspace, tmp_quota_home, start_run=True)
        r = client.post("/api/run/stop", json={"reason": "api-test"})
        assert r.status_code == 200
        assert r.json()["state"] == "stopped"

    def test_escalate_run(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        client, engine = self._app_with_engine(tmp_workspace, tmp_quota_home, start_run=True)
        r = client.post("/api/run/escalate", json={"new_mode": "standard"})
        assert r.status_code == 200
        data = r.json()
        assert data["new_mode"] == "standard"
        assert data["member_count"] >= 2  # 至少 architect + developer

    def test_escalate_invalid_mode(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        client, _ = self._app_with_engine(tmp_workspace, tmp_quota_home, start_run=True)
        r = client.post("/api/run/escalate", json={"new_mode": "xxx"})
        assert r.status_code == 422  # pydantic 正则拒绝
