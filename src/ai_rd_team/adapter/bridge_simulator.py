"""Bridge 模拟器：模拟主 Agent 处理 intent 文件。

完全按照 skills/ai-rd-team-bridge.md 的协议实现，用于：
- 自动化 E2E 测试（无需真实 CodeBuddy）
- 验证 bridge Skill 的协议正确性
- 开发者在本地调试引擎时使用

注意：本模拟器不调用真实 CodeBuddy 工具，而是模拟返回值。
真实场景由主 Agent（阅读 bridge.md Skill）手工处理 intent。
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# 默认响应器（返回 canned data）
# ============================================================


@dataclass
class BridgeSimulator:
    """E2E 测试/本地调试用的 bridge 模拟器。

    按 bridge.md §4 协议处理 intent：读 intent → 按 op 处理 → 写 result。
    支持：
    - 自定义 op 响应函数（响应器）
    - 记录所有处理的 intent（供断言）
    - 自动终止（team_delete 后退出）

    示例：
        sim = BridgeSimulator(runtime_dir=runtime)
        sim.start()
        # ... 引擎工作中 ...
        sim.stop()
        assert len(sim.processed) > 0
    """

    runtime_dir: Path
    poll_interval: float = 0.1
    """轮询间隔（秒）"""

    auto_stop_on_team_delete: bool = True
    """处理 team_delete 后自动停止"""

    processed: list[dict[str, Any]] = field(default_factory=list)
    """记录所有处理过的 intent（供断言）"""

    # 私有
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None
    _team_counter: int = 0
    _member_counter: int = 0
    _responders: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._intent_dir = self.runtime_dir / "adapter-intents"
        self._result_dir = self.runtime_dir / "adapter-results"
        self._intent_dir.mkdir(parents=True, exist_ok=True)
        self._result_dir.mkdir(parents=True, exist_ok=True)

        # 注册默认响应器
        if not self._responders:
            self._responders = {
                "team_create": self._default_team_create,
                "task": self._default_task,
                "send_message": self._default_send_message,
                "team_delete": self._default_team_delete,
                "_probe": self._default_probe,
                "_version": self._default_version,
            }

    # ------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------

    def start(self) -> None:
        """启动后台线程处理 intent。"""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """停止处理。"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def wait_for_intent(self, op: str, timeout: float = 5.0) -> dict[str, Any] | None:
        """等待指定 op 的 intent 被处理（测试辅助）。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for entry in self.processed:
                if entry.get("op") == op:
                    return entry
            time.sleep(0.05)
        return None

    # ------------------------------------------------------------
    # 响应器注册（供测试覆盖默认行为）
    # ------------------------------------------------------------

    def register_responder(
        self,
        op: str,
        responder: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        """注册/替换某个 op 的响应器。

        响应器接受 intent dict，返回要写到 result 文件的 data dict。
        """
        self._responders[op] = responder

    # ------------------------------------------------------------
    # 主循环
    # ------------------------------------------------------------

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._process_one_round()
            except Exception:
                logger.exception("bridge simulator loop error")
            time.sleep(self.poll_interval)

    def _process_one_round(self) -> None:
        # 按 _ts 排序处理
        intents: list[tuple[str, Path]] = []
        for intent_file in self._intent_dir.glob("*.json"):
            try:
                raw = intent_file.read_text(encoding="utf-8")
                data = json.loads(raw)
            except (OSError, ValueError):
                continue
            intents.append((data.get("_ts", ""), intent_file))

        intents.sort()

        for _ts, intent_file in intents:
            if self._stop_event.is_set():
                return
            self._handle_one(intent_file)

    def _handle_one(self, intent_file: Path) -> None:
        try:
            intent = json.loads(intent_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return

        op = intent.get("op", "")
        intent_id = intent.get("_id", intent_file.stem)

        responder = self._responders.get(op)
        if responder is None:
            result = {"error": f"no responder for op={op}"}
        else:
            try:
                data = responder(intent)
                result = {"data": data}
            except Exception as e:
                result = {"error": f"{type(e).__name__}: {e}"}

        # 写 result
        result_file = self._result_dir / f"{intent_id}.json"
        result_file.write_text(
            json.dumps(result, ensure_ascii=False),
            encoding="utf-8",
        )

        self.processed.append(
            {
                "op": op,
                "intent": intent,
                "result": result,
            }
        )

        # 自动停止
        if op == "team_delete" and self.auto_stop_on_team_delete:
            # 稍等一下让引擎读到 result
            time.sleep(self.poll_interval * 2)
            self._stop_event.set()

    # ------------------------------------------------------------
    # 默认响应器（按 bridge.md §4.1-§4.6）
    # ------------------------------------------------------------

    def _default_team_create(self, intent: dict[str, Any]) -> dict[str, Any]:
        self._team_counter += 1
        return {
            "team_name": intent["team_name"],
            "platform_id": f"sim-team-{self._team_counter}",
        }

    def _default_task(self, intent: dict[str, Any]) -> dict[str, Any]:
        self._member_counter += 1
        return {
            "name": intent["name"],
            "platform_id": f"sim-member-{self._member_counter}",
        }

    def _default_send_message(self, _intent: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    def _default_team_delete(self, _intent: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    def _default_probe(self, _intent: dict[str, Any]) -> dict[str, Any]:
        return {
            "available_tools": [
                "team_create",
                "team_delete",
                "task",
                "send_message",
            ]
        }

    def _default_version(self, _intent: dict[str, Any]) -> dict[str, Any]:
        return {"version": "simulated-4.3.3"}


__all__ = ["BridgeSimulator"]
