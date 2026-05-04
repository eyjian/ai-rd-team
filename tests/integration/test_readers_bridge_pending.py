"""`/api/bridge/pending-intents` 端点契约测试（M5）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_rd_team.service.app import create_app


@pytest.fixture
def app_client(tmp_workspace: Path) -> TestClient:
    runtime = tmp_workspace / ".ai-rd-team" / "runtime"
    (runtime / "adapter-intents").mkdir(parents=True)
    (runtime / "adapter-results").mkdir(parents=True)
    app = create_app(workspace=tmp_workspace, engine=None)
    return TestClient(app)


def _write_intent(runtime: Path, intent_id: str, payload: dict) -> None:
    p = runtime / "adapter-intents" / f"{intent_id}.json"
    payload.setdefault("_id", intent_id)
    p.write_text(json.dumps(payload), encoding="utf-8")


def _write_result(runtime: Path, intent_id: str, payload: dict | None = None) -> None:
    p = runtime / "adapter-results" / f"{intent_id}.json"
    p.write_text(json.dumps(payload or {"data": {"ok": True}}), encoding="utf-8")


class TestPendingIntents:
    def test_empty_when_no_intents(self, app_client: TestClient) -> None:
        r = app_client.get("/api/bridge/pending-intents")
        assert r.status_code == 200
        assert r.json() == []

    def test_only_pending_listed(self, app_client: TestClient, tmp_workspace: Path) -> None:
        runtime = tmp_workspace / ".ai-rd-team" / "runtime"
        # 一个已应答的 _version（result 存在）
        _write_intent(runtime, "v1", {"op": "_version"})
        _write_result(runtime, "v1", {"data": {"version": "claude-opus-4.x"}})
        # 一个未应答的 task
        _write_intent(
            runtime,
            "t1",
            {
                "op": "task",
                "name": "architect",
                "team_name": "ai-rd-team-abcd",
                "subagent_name": "code-explorer",
                "prompt": "...",
            },
        )

        r = app_client.get("/api/bridge/pending-intents")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # 只有 t1 是 pending
        assert len(data) == 1
        entry = data[0]
        assert entry["_id"] == "t1"
        assert entry["op"] == "task"
        assert "task(" in entry["hint"]
        assert "architect" in entry["hint"]
        assert "ai-rd-team-abcd" in entry["hint"]
        assert entry["name"] == "architect"
        assert entry["team_name"] == "ai-rd-team-abcd"
        assert isinstance(entry["age_seconds"], float)

    def test_hint_content_by_op(self, app_client: TestClient, tmp_workspace: Path) -> None:
        runtime = tmp_workspace / ".ai-rd-team" / "runtime"
        _write_intent(
            runtime,
            "tc1",
            {"op": "team_create", "team_name": "t-xyz", "description": "demo"},
        )
        _write_intent(runtime, "td1", {"op": "team_delete"})
        _write_intent(
            runtime,
            "sm1",
            {
                "op": "send_message",
                "type": "message",
                "recipient": "architect",
                "content": "hi",
                "summary": "启动",
            },
        )

        r = app_client.get("/api/bridge/pending-intents")
        assert r.status_code == 200
        data = r.json()
        hints = {e["_id"]: e["hint"] for e in data}
        assert "team_create(" in hints["tc1"]
        assert "t-xyz" in hints["tc1"]
        assert "team_delete()" in hints["td1"]
        assert "send_message(" in hints["sm1"]
        assert "architect" in hints["sm1"]

    def test_unknown_op_has_fallback_hint(
        self, app_client: TestClient, tmp_workspace: Path
    ) -> None:
        runtime = tmp_workspace / ".ai-rd-team" / "runtime"
        _write_intent(runtime, "u1", {"op": "foo_bar", "foo": 1})

        r = app_client.get("/api/bridge/pending-intents")
        data = r.json()
        assert len(data) == 1
        assert "未知 op" in data[0]["hint"]

    def test_missing_intent_dir_returns_empty(self, tmp_workspace: Path) -> None:
        # 没创建 adapter-intents 目录
        app = create_app(workspace=tmp_workspace, engine=None)
        client = TestClient(app)
        r = client.get("/api/bridge/pending-intents")
        assert r.status_code == 200
        assert r.json() == []
