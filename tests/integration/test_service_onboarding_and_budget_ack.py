"""T3.8 集成测试：首次启动 Web 引导 + smart_pause 预算响应。"""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from ai_rd_team.service.app import create_app


def _write_basic_config(ws: Path, mode: str = "lite") -> None:
    d = ws / ".ai-rd-team"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "config_version": "1.0",
                "run_mode": mode,
                "project": {"description": "e2e test"},
                "budget": {"per_run": 120, "per_day": 500},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


class TestOnboardingStatus:
    """GET /api/onboarding/status"""

    def test_uninitialized_workspace(self, tmp_workspace: Path) -> None:
        """config.yaml 不存在时 initialized=false。"""
        app = create_app(workspace=tmp_workspace, engine=None)
        client = TestClient(app)

        r = client.get("/api/onboarding/status")
        assert r.status_code == 200
        data = r.json()
        assert data["initialized"] is False
        assert data["has_advanced"] is False
        assert data["workspace"] == str(tmp_workspace)
        # 推断字段总是返回（即便为空 dict）
        assert "inferred" in data

    def test_initialized_workspace(self, tmp_workspace: Path) -> None:
        """config.yaml 存在时 initialized=true。"""
        _write_basic_config(tmp_workspace)
        app = create_app(workspace=tmp_workspace, engine=None)
        client = TestClient(app)

        r = client.get("/api/onboarding/status")
        assert r.status_code == 200
        assert r.json()["initialized"] is True

    def test_inferred_contains_project_name(self, tmp_workspace: Path) -> None:
        """推断字段能返回项目名（来自目录名）。"""
        app = create_app(workspace=tmp_workspace, engine=None)
        client = TestClient(app)

        r = client.get("/api/onboarding/status")
        data = r.json()
        assert data["inferred"] is not None
        # tmp_workspace 目录名是 "workspace"
        assert data["inferred"]["project_name"] == "workspace"


class TestOnboardingInit:
    """POST /api/onboarding/init"""

    def test_init_with_defaults(self, tmp_workspace: Path) -> None:
        """最小参数（只给 run_mode）就能生成 config.yaml。"""
        app = create_app(workspace=tmp_workspace, engine=None)
        client = TestClient(app)

        r = client.post(
            "/api/onboarding/init",
            json={"run_mode": "lite"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["run_mode"] == "lite"
        assert data["budget"]["per_run"] == 120  # lite 默认

        config_path = tmp_workspace / ".ai-rd-team" / "config.yaml"
        assert config_path.is_file()
        saved = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert saved["run_mode"] == "lite"
        assert saved["budget"]["per_run"] == 120

    def test_init_with_full_params(self, tmp_workspace: Path) -> None:
        """完整参数（含自定义预算、描述、技术栈）。"""
        app = create_app(workspace=tmp_workspace, engine=None)
        client = TestClient(app)

        r = client.post(
            "/api/onboarding/init",
            json={
                "run_mode": "standard",
                "description": "一个测试项目",
                "tech_stack_backend": "python",
                "tech_stack_frontend": "vue3",
                "budget_per_run": 250,
                "budget_per_day": 1000,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["budget"]["per_run"] == 250

        saved = yaml.safe_load(
            (tmp_workspace / ".ai-rd-team" / "config.yaml").read_text(encoding="utf-8")
        )
        assert saved["project"]["description"] == "一个测试项目"
        assert saved["tech_stack"]["backend"] == "python"
        assert saved["tech_stack"]["frontend"] == "vue3"

    def test_init_refuses_when_exists(self, tmp_workspace: Path) -> None:
        """config.yaml 已存在时返回 409。"""
        _write_basic_config(tmp_workspace)
        app = create_app(workspace=tmp_workspace, engine=None)
        client = TestClient(app)

        r = client.post(
            "/api/onboarding/init",
            json={"run_mode": "lite"},
        )
        assert r.status_code == 409
        assert "已存在" in r.json()["detail"]

    def test_init_validates_run_mode(self, tmp_workspace: Path) -> None:
        """非法 run_mode 返回 422。"""
        app = create_app(workspace=tmp_workspace, engine=None)
        client = TestClient(app)

        r = client.post(
            "/api/onboarding/init",
            json={"run_mode": "hyper"},
        )
        assert r.status_code == 422


class TestBudgetAck:
    """POST /api/run/budget-ack"""

    def _app_with_engine(self, tmp_workspace: Path, tmp_quota_home: Path):
        """启动带 Engine 的服务（用于 raise_budget 测试）。"""
        from ai_rd_team.adapter.bridge import InMemoryBridge
        from ai_rd_team.engine.manager import TeamEnvironmentManager

        _write_basic_config(tmp_workspace, mode="lite")
        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")

        app = create_app(workspace=tmp_workspace, engine=engine)
        return TestClient(app), engine

    def test_budget_ack_requires_engine(self, tmp_workspace: Path) -> None:
        """没有 engine 时返回 503。"""
        _write_basic_config(tmp_workspace)
        app = create_app(workspace=tmp_workspace, engine=None)
        client = TestClient(app)

        r = client.post("/api/run/budget-ack", json={"action": "continue"})
        assert r.status_code == 503

    def test_continue_action(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        """continue 动作：返回 ok 且写入 events.jsonl。"""
        client, engine = self._app_with_engine(tmp_workspace, tmp_quota_home)

        r = client.post("/api/run/budget-ack", json={"action": "continue"})
        assert r.status_code == 200
        assert r.json()["action"] == "continue"

        import json

        events_file = tmp_workspace / ".ai-rd-team" / "runtime" / "events.jsonl"
        events = [json.loads(line) for line in events_file.read_text().splitlines()]
        assert any(e["event"] == "budget_ack" for e in events)

        engine.stop_run(reason="test-done")

    def test_raise_budget_action(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        """raise_budget 动作：调整 RP 硬限并反映到 snapshot。"""
        client, engine = self._app_with_engine(tmp_workspace, tmp_quota_home)

        # 验证当前预算是 lite=120
        snap = engine.cost_snapshot()
        assert snap.rp_budget == 120

        r = client.post(
            "/api/run/budget-ack",
            json={"action": "raise_budget", "raise_to": 500},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["action"] == "raise_budget"
        assert data["new_rp_budget"] == 500

        # 再次查询 snapshot 已反映新值
        new_snap = engine.cost_snapshot()
        assert new_snap.rp_budget == 500

        engine.stop_run(reason="test-done")

    def test_raise_budget_requires_raise_to(
        self, tmp_workspace: Path, tmp_quota_home: Path
    ) -> None:
        """raise_budget 缺 raise_to 时返回 400。"""
        client, engine = self._app_with_engine(tmp_workspace, tmp_quota_home)

        r = client.post("/api/run/budget-ack", json={"action": "raise_budget"})
        assert r.status_code == 400

        engine.stop_run(reason="test-done")

    def test_raise_budget_rejects_lower_value(
        self, tmp_workspace: Path, tmp_quota_home: Path
    ) -> None:
        """raise_to 不大于当前预算时返回 400。"""
        client, engine = self._app_with_engine(tmp_workspace, tmp_quota_home)

        r = client.post(
            "/api/run/budget-ack",
            json={"action": "raise_budget", "raise_to": 50},
        )
        assert r.status_code == 400

        engine.stop_run(reason="test-done")

    def test_stop_action(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        """stop 动作：等价 stop_run。"""
        client, _engine = self._app_with_engine(tmp_workspace, tmp_quota_home)

        r = client.post("/api/run/budget-ack", json={"action": "stop"})
        assert r.status_code == 200
        # stop_run 的返回结构由 EngineProxy 决定
        # 至少校验 HTTP 200

    def test_invalid_action(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        """非法 action 返回 422（pydantic 校验失败）。"""
        client, engine = self._app_with_engine(tmp_workspace, tmp_quota_home)

        r = client.post("/api/run/budget-ack", json={"action": "explode"})
        assert r.status_code == 422

        engine.stop_run(reason="test-done")
