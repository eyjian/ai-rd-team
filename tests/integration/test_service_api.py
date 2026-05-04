"""测试 FastAPI 服务层（T3.1-T3.3）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from ai_rd_team.service.app import create_app


@pytest.fixture
def app_client(tmp_workspace: Path) -> TestClient:
    """只读模式（无 Engine）的 TestClient。"""
    # 准备一些 runtime 数据
    runtime = tmp_workspace / ".ai-rd-team" / "runtime"
    runtime.mkdir(parents=True)

    (runtime / "current-run.yaml").write_text(
        yaml.safe_dump(
            {
                "run_id": "test-123",
                "mode": "lite",
                "requirement": "测试需求",
                "status": "stopped",
                "started_at": "2026-05-04T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    (runtime / "state").mkdir()
    (runtime / "state" / "team.yaml").write_text(
        yaml.safe_dump(
            {
                "status": "shut_down",
                "team_id": "ai-rd-team-test",
                "last_updated": "2026-05-04T00:05:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    (runtime / "state" / "roster.yaml").write_text(
        yaml.safe_dump(
            {
                "members": [{"instance_name": "developer", "role": "developer"}],
                "last_updated": "2026-05-04T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    (runtime / "state" / "members").mkdir()
    (runtime / "state" / "members" / "developer.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "developer",
                "role": "developer",
                "status": "done",
                "current_task": "test",
                "progress": "100%",
                "last_updated": "2026-05-04T00:05:00+00:00",
                "produced_files": ["artifacts/code/x.py"],
                "blocking_issues": [],
            }
        ),
        encoding="utf-8",
    )

    # events.jsonl
    (runtime / "events.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "ts": "2026-05-04T00:00:00+00:00",
                        "event": "run_starting",
                        "run_id": "test-123",
                    }
                ),
                json.dumps(
                    {
                        "ts": "2026-05-04T00:05:00+00:00",
                        "event": "run_stopped",
                        "run_id": "test-123",
                        "reason": "test",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # 制品（M7：交付物落项目根，manifest 在 runtime/manifest.yaml）
    code_dir = tmp_workspace / "code"
    code_dir.mkdir(parents=True)
    (code_dir / "hello.py").write_text("print('hi')\n", encoding="utf-8")
    (runtime / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "artifacts": [
                    {
                        "path": "code/hello.py",
                        "kind": "code",
                        "category": "delivery",
                        "producer": "developer_1",
                        "created_at": "2026-05-04T00:00:00",
                    }
                ],
                "last_updated": "2026-05-04T00:00:00",
            }
        ),
        encoding="utf-8",
    )

    # cost
    cost_dir = runtime / "cost"
    cost_dir.mkdir()
    (cost_dir / "resource-points.yaml").write_text(
        yaml.safe_dump(
            {
                "run_id": "test-123",
                "mode": "lite",
                "resource_points": 42,
                "rp_budget": 120,
                "rp_usage_ratio": 0.35,
            }
        ),
        encoding="utf-8",
    )
    (cost_dir / "post-run.jsonl").write_text(
        json.dumps(
            {
                "run_id": "test-123",
                "ended_at": "2026-05-04T00:05:00+00:00",
                "mode": "lite",
                "rp_used": 42,
                "members_spawned": 1,
                "messages": 1,
                "broadcasts": 0,
                "minutes": 0.0,
                "iterations": 0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # basic + advanced config
    (tmp_workspace / ".ai-rd-team" / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "config_version": "1.0",
                "run_mode": "lite",
                "project": {"description": "测试项目"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_workspace / ".ai-rd-team" / "config.advanced.yaml").write_text(
        yaml.safe_dump({"hooks": {"enabled": True}}),
        encoding="utf-8",
    )

    # memory
    agent_d = tmp_workspace / ".ai-rd-team" / "memory" / "agent.d"
    agent_d.mkdir(parents=True)
    (agent_d / "team-roster.md").write_text(
        "---\ntype: memory\nlayer: agent.d\nauthor: test\n"
        "created: 2026-05-04\nupdated: 2026-05-04\nestimated_tokens: 50\n---\n\n"
        "# Team Roster\n\n- developer\n",
        encoding="utf-8",
    )

    # messages
    msgs = runtime / "messages"
    msgs.mkdir()
    (msgs / "20260504-000030-main-developer.json").write_text(
        json.dumps(
            {
                "ts": "2026-05-04T00:00:30+00:00",
                "from": "main",
                "to": "developer",
                "type": "message",
                "content": "开始工作",
                "summary": "启动任务",
            }
        ),
        encoding="utf-8",
    )

    app = create_app(workspace=tmp_workspace, engine=None)
    return TestClient(app)


# ============================================================
# Meta
# ============================================================


class TestMeta:
    def test_health(self, app_client: TestClient) -> None:
        r = app_client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_version(self, app_client: TestClient) -> None:
        r = app_client.get("/api/version")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "ai-rd-team"
        assert "version" in data


# ============================================================
# Run
# ============================================================


class TestRun:
    def test_current_run_merges_runtime_and_engine(self, app_client: TestClient) -> None:
        r = app_client.get("/api/run/current")
        assert r.status_code == 200
        data = r.json()
        assert data["run_id"] == "test-123"
        # 无 Engine 时 engine_state == unavailable
        assert data["engine_state"] == "unavailable"


# ============================================================
# Team
# ============================================================


class TestTeam:
    def test_team_state(self, app_client: TestClient) -> None:
        r = app_client.get("/api/team/state")
        assert r.status_code == 200
        data = r.json()
        assert data["team_id"] == "ai-rd-team-test"
        assert data["status"] == "shut_down"

    def test_members_list(self, app_client: TestClient) -> None:
        r = app_client.get("/api/team/members")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["members"][0]["name"] == "developer"
        assert data["members"][0]["status"] == "done"

    def test_member_detail(self, app_client: TestClient) -> None:
        r = app_client.get("/api/team/members/developer")
        assert r.status_code == 200
        assert r.json()["status"] == "done"

    def test_member_not_found(self, app_client: TestClient) -> None:
        r = app_client.get("/api/team/members/unknown")
        assert r.status_code == 404

    def test_roster(self, app_client: TestClient) -> None:
        r = app_client.get("/api/team/roster")
        assert r.status_code == 200
        assert len(r.json()["members"]) == 1

    def test_messages(self, app_client: TestClient) -> None:
        r = app_client.get("/api/team/messages")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["messages"][0]["content"] == "开始工作"


# ============================================================
# Events
# ============================================================


class TestEvents:
    def test_events_list(self, app_client: TestClient) -> None:
        r = app_client.get("/api/events")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        assert data["events"][0]["event"] == "run_starting"


# ============================================================
# Artifacts
# ============================================================


class TestArtifacts:
    def test_list_artifacts(self, app_client: TestClient) -> None:
        r = app_client.get("/api/artifacts")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        entry = data["artifacts"][0]
        # M7 后：path 是项目根相对；category 是 delivery/process
        assert entry["path"] == "code/hello.py"
        assert entry["category"] == "delivery"
        assert entry["kind"] == "code"
        assert entry["exists"] is True
        assert entry["size"] > 0

    def test_read_artifact_file(self, app_client: TestClient) -> None:
        # M7 后：默认 category=delivery（相对项目根）
        r = app_client.get("/api/artifacts/file?path=code/hello.py")
        assert r.status_code == 200
        assert "print" in r.json()["content"]

    def test_read_artifact_404(self, app_client: TestClient) -> None:
        r = app_client.get("/api/artifacts/file?path=code/missing.py")
        assert r.status_code == 404

    def test_path_traversal_blocked(self, app_client: TestClient) -> None:
        r = app_client.get("/api/artifacts/file?path=../../../etc/passwd")
        assert r.status_code == 400


# ============================================================
# Memory
# ============================================================


class TestMemory:
    def test_list_agent_d(self, app_client: TestClient) -> None:
        r = app_client.get("/api/memory/agent-d")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["files"][0]["name"] == "team-roster"

    def test_read_memory_file(self, app_client: TestClient) -> None:
        r = app_client.get("/api/memory/file?path=agent.d/team-roster.md")
        assert r.status_code == 200
        assert "Team Roster" in r.json()["content"]


# ============================================================
# Cost
# ============================================================


class TestCost:
    def test_snapshot_from_file(self, app_client: TestClient) -> None:
        r = app_client.get("/api/cost/snapshot")
        assert r.status_code == 200
        data = r.json()
        assert data["resource_points"] == 42

    def test_history(self, app_client: TestClient) -> None:
        r = app_client.get("/api/cost/history")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["runs"][0]["rp_used"] == 42

    def test_budget_check_without_engine(self, app_client: TestClient) -> None:
        r = app_client.get("/api/cost/budget-check")
        assert r.status_code == 200
        data = r.json()
        assert data["action"] == "unavailable"


# ============================================================
# Config
# ============================================================


class TestConfig:
    def test_basic(self, app_client: TestClient) -> None:
        r = app_client.get("/api/config/basic")
        assert r.status_code == 200
        data = r.json()
        assert data["run_mode"] == "lite"

    def test_advanced(self, app_client: TestClient) -> None:
        r = app_client.get("/api/config/advanced")
        assert r.status_code == 200
        assert "hooks" in r.json()

    def test_effective_without_engine_returns_503(self, app_client: TestClient) -> None:
        r = app_client.get("/api/config/effective")
        assert r.status_code == 503


# ============================================================
# Skills
# ============================================================


class TestSkills:
    def test_list_skills(self, app_client: TestClient) -> None:
        r = app_client.get("/api/skills")
        assert r.status_code == 200
        data = r.json()
        # builtin 目录至少有 3 个：python-best-practices / code-review-checklist / pytest-guide
        assert len(data["builtin"]) >= 3

    def test_read_builtin_skill(self, app_client: TestClient) -> None:
        r = app_client.get("/api/skills/file?scope=builtin&name=python-best-practices")
        assert r.status_code == 200
        assert "Python Best Practices" in r.json()["content"]

    def test_invalid_scope(self, app_client: TestClient) -> None:
        r = app_client.get("/api/skills/file?scope=evil&name=x")
        assert r.status_code == 400


# ============================================================
# Static HTML
# ============================================================


class TestStatic:
    def test_root_returns_html(self, app_client: TestClient) -> None:
        r = app_client.get("/")
        assert r.status_code == 200
        assert "ai-rd-team" in r.text
        assert "Vue" in r.text or "vue" in r.text

    def test_favicon_no_404(self, app_client: TestClient) -> None:
        r = app_client.get("/favicon.ico")
        assert r.status_code == 204


# ============================================================
# Writers（无 Engine 时应返回 409/503）
# ============================================================


class TestWritersWithoutEngine:
    def test_send_message_no_engine(self, app_client: TestClient) -> None:
        r = app_client.post(
            "/api/team/members/developer/message",
            json={"content": "hello"},
        )
        # 无 engine → 409
        assert r.status_code == 409

    def test_broadcast_no_engine(self, app_client: TestClient) -> None:
        r = app_client.post("/api/team/broadcast", json={"content": "hi"})
        assert r.status_code == 409

    def test_stop_run_no_engine(self, app_client: TestClient) -> None:
        r = app_client.post("/api/run/stop", json={"reason": "x"})
        assert r.status_code == 409
