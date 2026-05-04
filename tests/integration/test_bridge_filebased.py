"""FileBasedBridge 的集成测试（需要真实文件 IO）。

验证 intent/result 协议的完整往返。
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from ai_rd_team.adapter.bridge import BridgeToolError, FileBasedBridge


@pytest.fixture
def runtime_dir(tmp_path: Path) -> Path:
    d = tmp_path / "runtime"
    d.mkdir()
    return d


def _simulate_agent_worker(
    runtime_dir: Path,
    response: dict,
    stop_after: int = 1,
    error: bool = False,
) -> threading.Thread:
    """模拟主 Agent：读 intent 并写 result。

    - stop_after：处理多少个 intent 后退出
    - error：True 则写 error 响应
    """
    intent_dir = runtime_dir / "adapter-intents"
    result_dir = runtime_dir / "adapter-results"
    stop_event = threading.Event()

    def loop() -> None:
        processed = 0
        deadline = time.monotonic() + 10
        while not stop_event.is_set() and time.monotonic() < deadline:
            for intent_file in intent_dir.glob("*.json"):
                try:
                    # 验证 intent 可解析（但不使用内容）
                    json.loads(intent_file.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                payload = {"error": "mock error"} if error else {"data": response}
                result_path = result_dir / intent_file.name
                result_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                processed += 1
                if processed >= stop_after:
                    return
            time.sleep(0.05)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return t


class TestFileBasedBridgeHappyPath:
    def test_team_create_roundtrip(self, runtime_dir: Path) -> None:
        bridge = FileBasedBridge(runtime_dir, timeout_seconds=5, poll_interval_seconds=0.05)

        worker = _simulate_agent_worker(
            runtime_dir,
            response={"platform_id": "team-abc"},
        )

        result = bridge.call_team_create("run-001", "test")
        worker.join(timeout=2)

        assert result == {"platform_id": "team-abc"}

    def test_task_async_roundtrip(self, runtime_dir: Path) -> None:
        bridge = FileBasedBridge(runtime_dir, timeout_seconds=5, poll_interval_seconds=0.05)

        worker = _simulate_agent_worker(
            runtime_dir,
            response={"name": "architect", "platform_id": "member-1"},
        )

        result = bridge.call_task_async(
            subagent_name="code-explorer",
            description="test",
            prompt="你是架构师",
            name="architect",
            team_name="run-001",
        )
        worker.join(timeout=2)

        assert result["name"] == "architect"

    def test_send_message_roundtrip(self, runtime_dir: Path) -> None:
        bridge = FileBasedBridge(runtime_dir, timeout_seconds=5, poll_interval_seconds=0.05)

        worker = _simulate_agent_worker(runtime_dir, response={"ok": True})

        result = bridge.call_send_message(
            type="message",
            recipient="architect",
            content="hi",
            summary="hi",
        )
        worker.join(timeout=2)

        assert result == {"ok": True}

    def test_cleans_up_files_after_roundtrip(self, runtime_dir: Path) -> None:
        bridge = FileBasedBridge(runtime_dir, timeout_seconds=5, poll_interval_seconds=0.05)

        worker = _simulate_agent_worker(runtime_dir, response={"ok": True})
        bridge.call_team_delete()
        worker.join(timeout=2)

        # intent 和 result 文件都应被清理
        assert list((runtime_dir / "adapter-intents").glob("*.json")) == []
        assert list((runtime_dir / "adapter-results").glob("*.json")) == []


class TestFileBasedBridgeError:
    def test_error_result_raises(self, runtime_dir: Path) -> None:
        bridge = FileBasedBridge(runtime_dir, timeout_seconds=5, poll_interval_seconds=0.05)

        worker = _simulate_agent_worker(runtime_dir, response={}, error=True)

        with pytest.raises(BridgeToolError, match="mock error"):
            bridge.call_team_create("r", "")
        worker.join(timeout=2)


class TestFileBasedBridgeTimeout:
    def test_timeout_when_no_agent(self, runtime_dir: Path) -> None:
        """没有 agent worker 响应时应超时抛 TimeoutError。"""
        bridge = FileBasedBridge(
            runtime_dir,
            timeout_seconds=0.5,
            poll_interval_seconds=0.05,
        )
        with pytest.raises(TimeoutError):
            bridge.call_team_delete()

    def test_timeout_message_mentions_op_and_hint(self, runtime_dir: Path) -> None:
        """M7：超时 error 应带 op 名 + 指引主 Agent 排查。"""
        bridge = FileBasedBridge(
            runtime_dir,
            timeout_seconds=0.3,
            poll_interval_seconds=0.05,
        )
        with pytest.raises(TimeoutError) as exc_info:
            bridge.call_team_create("run-001", "desc")

        msg = str(exc_info.value)
        # op 名一定在
        assert "team_create" in msg
        # 超时秒数提示
        assert "waited" in msg
        # 针对 manual-op 的指引
        assert "ai-rd-team-bridge" in msg or "adapter-intents" in msg

        # 超时后应清理 intent 文件
        # (result 本来就没有)
        assert list((runtime_dir / "adapter-intents").glob("*.json")) == []


class TestProbe:
    def test_probe_roundtrip(self, runtime_dir: Path) -> None:
        bridge = FileBasedBridge(runtime_dir, timeout_seconds=5, poll_interval_seconds=0.05)

        worker = _simulate_agent_worker(
            runtime_dir,
            response={
                "available_tools": [
                    "team_create",
                    "team_delete",
                    "task",
                    "send_message",
                ],
            },
        )

        tools = bridge.probe_available_tools()
        worker.join(timeout=2)

        assert "team_create" in tools
        assert "task" in tools

    def test_version_query_roundtrip(self, runtime_dir: Path) -> None:
        bridge = FileBasedBridge(runtime_dir, timeout_seconds=5, poll_interval_seconds=0.05)

        worker = _simulate_agent_worker(runtime_dir, response={"version": "4.3.3"})

        version = bridge.query_version_string()
        worker.join(timeout=2)

        assert version == "4.3.3"

    def test_version_query_timeout_returns_none(self, runtime_dir: Path) -> None:
        """版本查询超时不抛异常，返回 None（方便 Adapter 宽容处理）。"""
        bridge = FileBasedBridge(
            runtime_dir,
            timeout_seconds=0.5,
            poll_interval_seconds=0.05,
        )
        # 没有 worker
        assert bridge.query_version_string() is None
