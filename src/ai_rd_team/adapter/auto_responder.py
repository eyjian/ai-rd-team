"""AutoBridgeResponder — 降低 main Agent 在 file bridge 协议下的手动应答负担（M5）。

设计：openspec/changes/reduce-bridge-burden/design.md D2
规格：openspec/specs/adapter-bridge-auto-responder/spec.md

职责：
- 后台线程轮询 ``runtime/adapter-intents/*.json``
- 对"不需要真实 CodeBuddy 工具能力"的 intent 自动写 result，不阻塞引擎
- 真工具类 intent（team_create / task / send_message type=message / team_delete）**不应答**，
  交给 main Agent 按 `skills/ai-rd-team-bridge.md` 手动处理
- 每次自动应答写一条 ``bridge_auto_responded`` 事件到 ``events.jsonl``

本组件完全运行在 bridge 文件协议之上，向后兼容——关闭 (``adapter.auto_bridge=false``)
时等价于 M4 行为。
"""

from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_rd_team.adapter.codebuddy import DEFAULT_AVAILABLE_TOOLS, DEFAULT_CODEBUDDY_VERSION
from ai_rd_team.utils.file_ops import atomic_write, locked_append

logger = logging.getLogger(__name__)


# ============================================================
# 决策表
# ============================================================


@dataclass(frozen=True)
class AutoResponderDecision:
    """对单个 intent 的决策结果。

    - ``handled=False``：不应答，交给 main Agent
    - ``handled=True``：写 ``{"data": data}`` 到 result；``log_level`` 可控警告
    """

    handled: bool
    data: dict[str, Any] | None = None
    log_level: str | None = None  # "info" / "warning" / None


def _decide(intent: dict[str, Any]) -> AutoResponderDecision:
    """按 design.md D2 决策表判断某 intent 是否自动应答。"""
    op = intent.get("op")

    # 纯信息类 intent（兜底；F 优化后正常路径不会再发）
    if op == "_version":
        return AutoResponderDecision(
            handled=True,
            data={"version": DEFAULT_CODEBUDDY_VERSION},
        )
    if op == "_probe":
        return AutoResponderDecision(
            handled=True,
            data={"available_tools": sorted(DEFAULT_AVAILABLE_TOOLS)},
        )

    # 礼节性通信（不需要真工具能力）
    if op == "send_message":
        msg_type = intent.get("type")
        if msg_type in {"shutdown_request", "shutdown_response"}:
            return AutoResponderDecision(handled=True, data={"ok": True})
        if msg_type == "broadcast":
            # Standard 档 role 约束本身已禁用；auto 回 ok + warning
            return AutoResponderDecision(
                handled=True,
                data={"ok": True},
                log_level="warning",
            )
        # type=message / plan_approval_response 或未知：留给 main Agent
        return AutoResponderDecision(handled=False)

    # 真工具类：team_create / task / team_delete / 未知 op 都交给 main Agent
    return AutoResponderDecision(handled=False)


# ============================================================
# 组件
# ============================================================


@dataclass
class AutoBridgeResponder:
    """文件 bridge 协议之上的后台自动应答组件。

    用法：
        responder = AutoBridgeResponder(
            runtime_dir=ws / ".ai-rd-team/runtime",
            events_file=ws / ".ai-rd-team/runtime/events.jsonl",
        )
        responder.start()
        # ... 引擎运行 ...
        responder.stop()

    线程安全：
    - start/stop 幂等（重复调不抛异常）
    - 内部线程通过 ``_stop_event`` 协作退出
    - 应答竞态保护：写 result 前先检查是否已存在
    """

    runtime_dir: Path
    poll_interval: float = 0.3
    events_file: Path | None = None  # 若提供则 handled 时写事件

    # 运行期状态（对外只读）
    _responded: Counter[str] = field(default_factory=Counter)
    _skipped: Counter[str] = field(default_factory=Counter)
    _thread: threading.Thread | None = None
    _stop_event: threading.Event = field(default_factory=threading.Event)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self._intent_dir = self.runtime_dir / "adapter-intents"
        self._result_dir = self.runtime_dir / "adapter-results"
        self._intent_dir.mkdir(parents=True, exist_ok=True)
        self._result_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------

    def start(self) -> None:
        """启动后台线程（幂等）。"""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            t = threading.Thread(
                target=self._loop,
                daemon=True,
                name="ai-rd-team-auto-bridge",
            )
            t.start()
            self._thread = t
            logger.info("AutoBridgeResponder started: %s", self._intent_dir)

    def stop(self, timeout: float = 2.0) -> None:
        """停止后台线程并 join（幂等）。"""
        with self._lock:
            t = self._thread
            if t is None:
                return
            self._stop_event.set()
        t.join(timeout=timeout)
        with self._lock:
            if self._thread is t:
                self._thread = None
        if t.is_alive():
            logger.warning("AutoBridgeResponder did not stop within %.1fs", timeout)
        else:
            logger.info(
                "AutoBridgeResponder stopped; responded=%s skipped=%s",
                dict(self._responded),
                dict(self._skipped),
            )

    @property
    def stats(self) -> dict[str, dict[str, int]]:
        """返回 {'responded': {...}, 'skipped': {...}} 快照（线程安全）。"""
        with self._lock:
            return {
                "responded": dict(self._responded),
                "skipped": dict(self._skipped),
            }

    # ------------------------------------------------------------
    # 内部：主循环
    # ------------------------------------------------------------

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick_once()
            except Exception as exc:  # noqa: BLE001
                logger.exception("AutoBridgeResponder tick failed: %s", exc)
            # 用 wait 替代 sleep，让 stop() 能立刻打断
            self._stop_event.wait(timeout=self.poll_interval)

    def _tick_once(self) -> None:
        """扫一轮 intent 目录，按决策表处理。"""
        if not self._intent_dir.is_dir():
            return
        intent_files = sorted(
            self._intent_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0.0,
        )
        for intent_path in intent_files:
            if self._stop_event.is_set():
                return
            self._handle_intent_file(intent_path)

    def _handle_intent_file(self, intent_path: Path) -> None:
        intent_id = intent_path.stem
        result_path = self._result_dir / f"{intent_id}.json"

        # 竞态保护：已存在 result → 主 Agent 或前次循环已处理
        if result_path.exists():
            return

        try:
            raw = intent_path.read_text(encoding="utf-8")
            intent = json.loads(raw)
        except (OSError, ValueError):
            # 文件可能正被写入；下一轮再试
            return

        if not isinstance(intent, dict):
            return

        decision = _decide(intent)
        op = str(intent.get("op", "?"))

        if not decision.handled:
            with self._lock:
                self._skipped[op] += 1
            return

        # 再做一次竞态检查（决策期间主 Agent 也可能已写 result）
        if result_path.exists():
            return

        try:
            atomic_write(
                result_path,
                json.dumps({"data": decision.data or {}}, ensure_ascii=False),
            )
        except OSError as exc:
            logger.warning("auto-respond failed to write result for %s: %s", intent_id, exc)
            return

        with self._lock:
            self._responded[op] += 1

        self._log_event(intent_id=intent_id, op=op, intent=intent)

        if decision.log_level == "warning":
            logger.warning(
                "auto-responded suspicious intent: op=%s type=%s id=%s",
                op,
                intent.get("type"),
                intent_id,
            )

    def _log_event(self, *, intent_id: str, op: str, intent: dict[str, Any]) -> None:
        """写 events.jsonl（若配置了 events_file）。"""
        if self.events_file is None:
            return
        # 复用 RuntimeStateManager.append_event 的记录格式（ts + event + fields）
        from ai_rd_team.runtime.state import utc_now_iso

        entry = {
            "ts": utc_now_iso(),
            "event": "bridge_auto_responded",
            "intent_id": intent_id,
            "op": op,
            "decision": "auto",
        }
        msg_type = intent.get("type")
        if isinstance(msg_type, str):
            entry["type"] = msg_type
        try:
            locked_append(
                self.events_file,
                json.dumps(entry, ensure_ascii=False) + "\n",
            )
        except OSError as exc:
            logger.warning("auto-respond event log failed: %s", exc)


__all__ = [
    "AutoBridgeResponder",
    "AutoResponderDecision",
]
