"""AutoBridgeResponder 单元测试（M5）。

覆盖：
- _decide() 决策表对 7 种 intent 的返回
- start/stop 幂等与线程生命周期
- 自动应答写 result + 事件
- 真工具类 intent 不被应答
- 竞态保护：已存在 result 时跳过
- 广播 intent 的 warning 路径
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from ai_rd_team.adapter.auto_responder import (
    AutoBridgeResponder,
    AutoResponderDecision,
    _decide,
)
from ai_rd_team.adapter.codebuddy import DEFAULT_AVAILABLE_TOOLS, DEFAULT_CODEBUDDY_VERSION

# ============================================================
# 决策表单测
# ============================================================


class TestDecisionTable:
    def test_version_handled(self) -> None:
        d = _decide({"op": "_version"})
        assert d.handled is True
        assert d.data == {"version": DEFAULT_CODEBUDDY_VERSION}

    def test_probe_handled(self) -> None:
        d = _decide({"op": "_probe"})
        assert d.handled is True
        assert set(d.data["available_tools"]) == DEFAULT_AVAILABLE_TOOLS

    def test_shutdown_request_handled(self) -> None:
        d = _decide({"op": "send_message", "type": "shutdown_request", "recipient": "x"})
        assert d.handled is True
        assert d.data == {"ok": True}

    def test_shutdown_response_handled(self) -> None:
        d = _decide({"op": "send_message", "type": "shutdown_response", "approve": True})
        assert d.handled is True

    def test_broadcast_handled_with_warning(self) -> None:
        d = _decide({"op": "send_message", "type": "broadcast", "content": "..."})
        assert d.handled is True
        assert d.log_level == "warning"

    def test_message_not_handled(self) -> None:
        d = _decide({"op": "send_message", "type": "message", "recipient": "x", "content": "c"})
        assert d.handled is False

    def test_plan_approval_not_handled(self) -> None:
        d = _decide({"op": "send_message", "type": "plan_approval_response", "approve": True})
        assert d.handled is False

    def test_team_create_not_handled(self) -> None:
        d = _decide({"op": "team_create", "team_name": "t"})
        assert d.handled is False

    def test_task_not_handled(self) -> None:
        d = _decide({"op": "task", "name": "architect", "team_name": "t"})
        assert d.handled is False

    def test_team_delete_not_handled(self) -> None:
        d = _decide({"op": "team_delete"})
        assert d.handled is False

    def test_unknown_op_not_handled(self) -> None:
        d = _decide({"op": "foo_bar"})
        assert d.handled is False


# ============================================================
# fixtures
# ============================================================


@pytest.fixture
def runtime_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".ai-rd-team" / "runtime"
    d.mkdir(parents=True)
    (d / "adapter-intents").mkdir()
    (d / "adapter-results").mkdir()
    return d


def _write_intent(runtime_dir: Path, intent_id: str, payload: dict) -> Path:
    p = runtime_dir / "adapter-intents" / f"{intent_id}.json"
    payload.setdefault("_id", intent_id)
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _wait_for_result(runtime_dir: Path, intent_id: str, timeout: float = 2.0) -> Path | None:
    p = runtime_dir / "adapter-results" / f"{intent_id}.json"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if p.exists():
            return p
        time.sleep(0.02)
    return None


# ============================================================
# 生命周期 / 线程行为
# ============================================================


class TestLifecycle:
    def test_start_stop_idempotent(self, runtime_dir: Path) -> None:
        r = AutoBridgeResponder(runtime_dir=runtime_dir, poll_interval=0.05)
        r.start()
        r.start()  # 再次 start 应无副作用
        assert r._thread is not None
        assert r._thread.is_alive()

        r.stop()
        r.stop()  # 再次 stop 应无副作用
        assert r._thread is None

    def test_thread_exits_within_timeout(self, runtime_dir: Path) -> None:
        r = AutoBridgeResponder(runtime_dir=runtime_dir, poll_interval=0.05)
        r.start()
        t = r._thread
        assert t is not None
        r.stop(timeout=1.0)
        assert not t.is_alive()


# ============================================================
# 自动应答路径
# ============================================================


class TestAutoResponding:
    def test_responds_to_shutdown_request(self, runtime_dir: Path) -> None:
        events_file = runtime_dir / "events.jsonl"
        r = AutoBridgeResponder(
            runtime_dir=runtime_dir, poll_interval=0.05, events_file=events_file
        )
        r.start()
        try:
            _write_intent(
                runtime_dir,
                "abc-123",
                {"op": "send_message", "type": "shutdown_request", "recipient": "arch"},
            )
            result_path = _wait_for_result(runtime_dir, "abc-123")
            assert result_path is not None
            result = json.loads(result_path.read_text())
            assert result == {"data": {"ok": True}}
        finally:
            r.stop()

        # 事件已写入
        assert events_file.exists()
        lines = [json.loads(line) for line in events_file.read_text().splitlines() if line.strip()]
        shutdown_events = [e for e in lines if e["event"] == "bridge_auto_responded"]
        assert len(shutdown_events) == 1
        e = shutdown_events[0]
        assert e["intent_id"] == "abc-123"
        assert e["op"] == "send_message"
        assert e["type"] == "shutdown_request"
        assert e["decision"] == "auto"

    def test_does_not_respond_to_task(self, runtime_dir: Path) -> None:
        r = AutoBridgeResponder(runtime_dir=runtime_dir, poll_interval=0.05)
        r.start()
        try:
            _write_intent(
                runtime_dir,
                "task-1",
                {"op": "task", "name": "arch", "team_name": "t", "prompt": "p"},
            )
            # 等 0.5s 确保若会应答肯定已发生
            time.sleep(0.5)
            assert not (runtime_dir / "adapter-results" / "task-1.json").exists()
        finally:
            r.stop()

        # 原 intent 保留可读
        assert (runtime_dir / "adapter-intents" / "task-1.json").exists()

        # stats 反映 skipped
        stats = r.stats
        assert stats["skipped"].get("task", 0) >= 1

    def test_skips_intent_with_existing_result(self, runtime_dir: Path) -> None:
        # 主 Agent 已抢先写了 result
        _write_intent(runtime_dir, "race-1", {"op": "_version"})
        existing = runtime_dir / "adapter-results" / "race-1.json"
        existing.write_text(
            json.dumps({"data": {"version": "main-agent-wrote-this"}}), encoding="utf-8"
        )

        r = AutoBridgeResponder(runtime_dir=runtime_dir, poll_interval=0.05)
        r.start()
        try:
            time.sleep(0.3)
        finally:
            r.stop()

        # responder 不得覆盖已有 result
        result = json.loads(existing.read_text())
        assert result == {"data": {"version": "main-agent-wrote-this"}}

    def test_responds_to_version_and_probe(self, runtime_dir: Path) -> None:
        r = AutoBridgeResponder(runtime_dir=runtime_dir, poll_interval=0.05)
        r.start()
        try:
            _write_intent(runtime_dir, "v1", {"op": "_version"})
            _write_intent(runtime_dir, "p1", {"op": "_probe"})

            r_v = _wait_for_result(runtime_dir, "v1")
            r_p = _wait_for_result(runtime_dir, "p1")
            assert r_v is not None and r_p is not None

            v = json.loads(r_v.read_text())
            p = json.loads(r_p.read_text())
            assert v["data"]["version"] == DEFAULT_CODEBUDDY_VERSION
            assert set(p["data"]["available_tools"]) == DEFAULT_AVAILABLE_TOOLS
        finally:
            r.stop()

    def test_broadcast_responds_with_warning(self, runtime_dir: Path) -> None:
        events_file = runtime_dir / "events.jsonl"
        r = AutoBridgeResponder(
            runtime_dir=runtime_dir, poll_interval=0.05, events_file=events_file
        )
        r.start()
        try:
            _write_intent(
                runtime_dir,
                "bc-1",
                {"op": "send_message", "type": "broadcast", "content": "all"},
            )
            result_path = _wait_for_result(runtime_dir, "bc-1")
            assert result_path is not None
            assert json.loads(result_path.read_text()) == {"data": {"ok": True}}
        finally:
            r.stop()

    def test_stats_counts(self, runtime_dir: Path) -> None:
        r = AutoBridgeResponder(runtime_dir=runtime_dir, poll_interval=0.05)
        r.start()
        try:
            _write_intent(
                runtime_dir,
                "s1",
                {"op": "send_message", "type": "shutdown_request", "recipient": "x"},
            )
            _write_intent(
                runtime_dir,
                "s2",
                {"op": "send_message", "type": "shutdown_request", "recipient": "y"},
            )
            _write_intent(runtime_dir, "t1", {"op": "team_create", "team_name": "t"})
            # 等每个 intent 被处理
            _wait_for_result(runtime_dir, "s1")
            _wait_for_result(runtime_dir, "s2")
            time.sleep(0.2)  # 给 skipped 计数器刷新时间
        finally:
            r.stop()

        stats = r.stats
        assert stats["responded"].get("send_message", 0) == 2
        assert stats["skipped"].get("team_create", 0) >= 1


# ============================================================
# 额外：AutoResponderDecision dataclass 冻结
# ============================================================


def test_decision_is_frozen() -> None:
    d = AutoResponderDecision(handled=False)
    with pytest.raises((AttributeError, Exception)):
        d.handled = True  # type: ignore[misc]
