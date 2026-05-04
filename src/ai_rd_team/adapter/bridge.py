"""CodeBuddy 工具调用 Bridge。

对应设计文档：openspec/specs/design/02-adapter.md §5

M1 采用模式 C：FileBased Bridge。
- 引擎写 intent 文件到 runtime/adapter-intents/
- 主 Agent（CodeBuddy 宿主）按 Skill 指引读 intent 并调用工具
- 工具结果写回 runtime/adapter-results/
- 引擎轮询 result 文件返回调用结果

M1 还提供 InMemoryBridge 和 RecordingBridge 供测试使用。
"""

from __future__ import annotations

import abc
import contextlib
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ai_rd_team.utils.file_ops import atomic_write, atomic_write_json

# ============================================================
# Bridge 抽象
# ============================================================


class CodeBuddyToolBridge(abc.ABC):
    """封装对 CodeBuddy 工具的调用。

    M1 采用模式 C：CodeBuddyAdapter 不直接调工具，而是通过 Bridge 间接发出请求，
    由主 Agent 根据 Skills 指引完成工具调用。
    """

    @abc.abstractmethod
    def call_team_create(self, team_name: str, description: str) -> dict[str, Any]:
        """调用 team_create 工具。"""

    @abc.abstractmethod
    def call_task_async(
        self,
        *,
        subagent_name: str,
        description: str,
        prompt: str,
        name: str,
        team_name: str,
        mode: str = "bypassPermissions",
        max_turns: int | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """调用 task 工具（异步团队成员模式）。"""

    @abc.abstractmethod
    def call_send_message(
        self,
        *,
        type: str,  # noqa: A002
        recipient: str | None = None,
        content: str | None = None,
        summary: str | None = None,
        request_id: str | None = None,
        approve: bool | None = None,
    ) -> dict[str, Any]:
        """调用 send_message 工具。"""

    @abc.abstractmethod
    def call_team_delete(self) -> dict[str, Any]:
        """调用 team_delete 工具。"""

    @abc.abstractmethod
    def probe_available_tools(self) -> set[str]:
        """探测当前环境可用的工具集。"""

    @abc.abstractmethod
    def query_version_string(self) -> str | None:
        """查询 CodeBuddy 版本字符串（可能返回 None）。"""


# ============================================================
# FileBased 实现（M1 核心）
# ============================================================


class FileBasedBridge(CodeBuddyToolBridge):
    """基于文件系统的 Bridge（M1 默认实现，对应设计 §5.2 模式 C）。

    写入：runtime/adapter-intents/{uuid}.json
    读取：runtime/adapter-results/{uuid}.json
    """

    def __init__(
        self,
        runtime_dir: Path,
        timeout_seconds: float = 60.0,
        poll_interval_seconds: float = 0.3,
    ):
        self.runtime_dir = runtime_dir
        self.intent_dir = runtime_dir / "adapter-intents"
        self.result_dir = runtime_dir / "adapter-results"
        self.intent_dir.mkdir(parents=True, exist_ok=True)
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout_seconds
        self.poll_interval = poll_interval_seconds

    def call_team_create(self, team_name: str, description: str) -> dict[str, Any]:
        return self._write_intent_and_wait(
            {
                "op": "team_create",
                "team_name": team_name,
                "description": description,
            }
        )

    def call_task_async(
        self,
        *,
        subagent_name: str,
        description: str,
        prompt: str,
        name: str,
        team_name: str,
        mode: str = "bypassPermissions",
        max_turns: int | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        intent: dict[str, Any] = {
            "op": "task",
            "subagent_name": subagent_name,
            "description": description,
            "prompt": prompt,
            "name": name,
            "team_name": team_name,
            "mode": mode,
        }
        if max_turns is not None:
            intent["max_turns"] = max_turns
        intent.update(extra)
        return self._write_intent_and_wait(intent)

    def call_send_message(
        self,
        *,
        type: str,  # noqa: A002
        recipient: str | None = None,
        content: str | None = None,
        summary: str | None = None,
        request_id: str | None = None,
        approve: bool | None = None,
    ) -> dict[str, Any]:
        intent: dict[str, Any] = {"op": "send_message", "type": type}
        if recipient is not None:
            intent["recipient"] = recipient
        if content is not None:
            intent["content"] = content
        if summary is not None:
            intent["summary"] = summary
        if request_id is not None:
            intent["request_id"] = request_id
        if approve is not None:
            intent["approve"] = approve
        return self._write_intent_and_wait(intent)

    def call_team_delete(self) -> dict[str, Any]:
        return self._write_intent_and_wait({"op": "team_delete"})

    def probe_available_tools(self) -> set[str]:
        result = self._write_intent_and_wait({"op": "_probe"})
        return set(result.get("available_tools", []))

    def query_version_string(self) -> str | None:
        try:
            result = self._write_intent_and_wait({"op": "_version"})
        except TimeoutError:
            return None
        v = result.get("version")
        return v if isinstance(v, str) else None

    # ------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------

    def _write_intent_and_wait(self, intent: dict[str, Any]) -> dict[str, Any]:
        intent_id = str(uuid.uuid4())
        intent["_id"] = intent_id
        intent["_ts"] = datetime.now().isoformat()

        intent_path = self.intent_dir / f"{intent_id}.json"
        result_path = self.result_dir / f"{intent_id}.json"

        atomic_write(intent_path, json.dumps(intent, ensure_ascii=False))

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if result_path.exists():
                try:
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    # 文件可能正在写入，再等一轮
                    time.sleep(self.poll_interval)
                    continue
                self._cleanup(intent_path, result_path)
                if result.get("error"):
                    raise BridgeToolError(result["error"])
                data = result.get("data")
                return data if isinstance(data, dict) else {}
            time.sleep(self.poll_interval)

        # 超时：尽量清理 intent 文件
        self._cleanup(intent_path, None)
        raise TimeoutError(f"Tool call timed out: op={intent.get('op')}")

    @staticmethod
    def _cleanup(intent_path: Path, result_path: Path | None) -> None:
        for p in (intent_path, result_path):
            if p is not None:
                with contextlib.suppress(OSError):
                    p.unlink()


class BridgeToolError(RuntimeError):
    """主 Agent 执行工具时返回的错误。"""


# ============================================================
# 测试/仿真 Bridge
# ============================================================


class InMemoryBridge(CodeBuddyToolBridge):
    """内存版 Bridge（测试用）。

    不涉及文件 IO，直接返回 canned 结果。
    可注入 probe_tools / version 以模拟不同 CodeBuddy 版本。
    """

    def __init__(
        self,
        probe_tools: set[str] | None = None,
        version: str | None = "test",
    ):
        self.calls: list[dict[str, Any]] = []
        self._probe_tools = probe_tools or {
            "team_create",
            "team_delete",
            "task",
            "send_message",
        }
        self._version = version
        self._team_counter = 0
        self._member_counter = 0

    def call_team_create(self, team_name: str, description: str) -> dict[str, Any]:
        self._team_counter += 1
        self.calls.append({"op": "team_create", "team_name": team_name})
        return {"team_name": team_name, "platform_id": f"team-{self._team_counter}"}

    def call_task_async(self, **kwargs: Any) -> dict[str, Any]:
        self._member_counter += 1
        self.calls.append({"op": "task", **kwargs})
        return {
            "name": kwargs.get("name"),
            "platform_id": f"member-{self._member_counter}",
        }

    def call_send_message(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"op": "send_message", **kwargs})
        return {"ok": True}

    def call_team_delete(self) -> dict[str, Any]:
        self.calls.append({"op": "team_delete"})
        return {"ok": True}

    def probe_available_tools(self) -> set[str]:
        return set(self._probe_tools)

    def query_version_string(self) -> str | None:
        return self._version


class RecordingBridge(CodeBuddyToolBridge):
    """代理 + 录制：真实调用 + 记录到文件（用于回放测试）。

    M1 仅提供骨架，M2 完善录制/回放。
    """

    def __init__(self, inner: CodeBuddyToolBridge, record_path: Path):
        self.inner = inner
        self.record_path = record_path
        self.record_path.parent.mkdir(parents=True, exist_ok=True)

    def _record(self, op: str, args: dict[str, Any], result: dict[str, Any]) -> None:
        entry = {
            "ts": datetime.now().isoformat(),
            "op": op,
            "args": args,
            "result": result,
        }
        # 追加模式（简单 JSONL）
        with open(self.record_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def call_team_create(self, team_name: str, description: str) -> dict[str, Any]:
        result = self.inner.call_team_create(team_name, description)
        self._record(
            "team_create",
            {"team_name": team_name, "description": description},
            result,
        )
        return result

    def call_task_async(self, **kwargs: Any) -> dict[str, Any]:
        result = self.inner.call_task_async(**kwargs)
        self._record("task", kwargs, result)
        return result

    def call_send_message(self, **kwargs: Any) -> dict[str, Any]:
        result = self.inner.call_send_message(**kwargs)
        self._record("send_message", kwargs, result)
        return result

    def call_team_delete(self) -> dict[str, Any]:
        result = self.inner.call_team_delete()
        self._record("team_delete", {}, result)
        return result

    def probe_available_tools(self) -> set[str]:
        return self.inner.probe_available_tools()

    def query_version_string(self) -> str | None:
        return self.inner.query_version_string()


__all__ = [
    "BridgeToolError",
    "CodeBuddyToolBridge",
    "FileBasedBridge",
    "InMemoryBridge",
    "RecordingBridge",
    "atomic_write_json",  # re-export for convenience
]
