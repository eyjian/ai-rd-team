"""运行时状态管理：runtime/ 目录的读写。

对应设计文档：
- openspec/specs/design/01-engine.md §6（RuntimeStateManager）
- openspec/specs/design/11-runtime-protocol.md（文件协议）

M1 范围：
- 写 current-run.yaml
- 写 state/team.yaml / state/members/{id}.yaml
- 追加 events.jsonl
- 创建所有必要子目录

M2+：commands/pending 处理、断点续跑、归档。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ai_rd_team.utils.file_ops import atomic_write, locked_append


def utc_now_iso() -> str:
    """返回带时区（UTC）+ 毫秒精度的 ISO 8601 时间戳。

    形如：``2026-05-04T03:12:45.678+00:00``

    为什么不用 ``datetime.now().isoformat()``：
    - 默认产生 naive datetime，无时区信息（分布式/跨时区分析时有歧义）
    - 默认微秒精度造成可读性差；毫秒精度对人类阅读更友好
    """
    now = datetime.now(timezone.utc)
    # 把微秒截断成毫秒（3 位）
    return now.isoformat(timespec="milliseconds")


# runtime/ 下的所有子目录
_RUNTIME_SUBDIRS = [
    "state",
    "state/members",
    "messages",
    "commands/pending",
    "commands/processed",
    "adapter-intents",
    "adapter-results",
    "cost",
    "artifacts",
    "artifacts/design",
    "artifacts/code",
    "artifacts/test",
    "artifacts/review",
    "artifacts/requirements",
    "artifacts/deployment",
    "artifacts/reports",
    "logs",
    "archive",
]


@dataclass
class RuntimeStateManager:
    """runtime/ 目录的读写封装。

    典型用法：
        rsm = RuntimeStateManager(runtime_dir=ws/".ai-rd-team/runtime")
        rsm.ensure_directories()
        rsm.write_run_metadata(run_id="...", requirement="...", mode="standard")
        rsm.write_team_state(status="running")
        rsm.append_event(event="run_started", run_id="...")
    """

    runtime_dir: Path

    # ------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------

    def ensure_directories(self) -> None:
        """创建 runtime/ 下所有必要子目录（idempotent）。"""
        for sub in _RUNTIME_SUBDIRS:
            (self.runtime_dir / sub).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # current-run.yaml
    # ------------------------------------------------------------

    def write_run_metadata(
        self,
        run_id: str,
        requirement: str,
        mode: str,
        extra: dict[str, Any] | None = None,
    ) -> Path:
        """写 current-run.yaml（原子写）。"""
        data = {
            "run_id": run_id,
            "started_at": utc_now_iso(),
            "requirement": requirement,
            "mode": mode,
            "status": "running",
        }
        if extra:
            data.update(extra)

        path = self.runtime_dir / "current-run.yaml"
        atomic_write(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
        return path

    def read_run_metadata(self) -> dict[str, Any] | None:
        """读 current-run.yaml（不存在返回 None）。"""
        path = self.runtime_dir / "current-run.yaml"
        if not path.is_file():
            return None
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return None

    def update_run_status(self, status: str) -> None:
        """更新 current-run.yaml 的 status 字段。"""
        data = self.read_run_metadata() or {}
        data["status"] = status
        data["updated_at"] = utc_now_iso()
        atomic_write(
            self.runtime_dir / "current-run.yaml",
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        )

    # ------------------------------------------------------------
    # state/team.yaml
    # ------------------------------------------------------------

    def write_team_state(
        self,
        status: str,
        team_id: str = "",
        extra: dict[str, Any] | None = None,
    ) -> Path:
        """写 state/team.yaml（原子写）。"""
        data: dict[str, Any] = {
            "status": status,
            "team_id": team_id,
            "last_updated": utc_now_iso(),
        }
        if extra:
            data.update(extra)

        path = self.runtime_dir / "state" / "team.yaml"
        atomic_write(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
        return path

    # ------------------------------------------------------------
    # state/members/{id}.yaml
    # ------------------------------------------------------------

    def write_member_state(
        self,
        instance_name: str,
        role: str,
        status: str = "idle",
        current_task: str = "",
        progress: str = "",
        produced_files: list[str] | None = None,
        blocking_issues: list[str] | None = None,
    ) -> Path:
        """写 state/members/{instance_name}.yaml（原子写）。"""
        data = {
            "name": instance_name,
            "role": role,
            "status": status,
            "current_task": current_task,
            "progress": progress,
            "last_updated": utc_now_iso(),
            "produced_files": produced_files or [],
            "blocking_issues": blocking_issues or [],
        }

        path = self.runtime_dir / "state" / "members" / f"{instance_name}.yaml"
        atomic_write(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
        return path

    def read_member_state(self, instance_name: str) -> dict[str, Any] | None:
        path = self.runtime_dir / "state" / "members" / f"{instance_name}.yaml"
        if not path.is_file():
            return None
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return None

    def list_member_states(self) -> dict[str, dict[str, Any]]:
        """列出所有成员的 state（key=instance_name）。"""
        result: dict[str, dict[str, Any]] = {}
        members_dir = self.runtime_dir / "state" / "members"
        if not members_dir.is_dir():
            return result
        for f in members_dir.glob("*.yaml"):
            data = self.read_member_state(f.stem)
            if data:
                result[f.stem] = data
        return result

    # ------------------------------------------------------------
    # roster.yaml
    # ------------------------------------------------------------

    def write_roster(self, members: list[tuple[str, str]]) -> Path:
        """写 state/roster.yaml。

        Args:
            members: [(instance_name, role_name), ...]
        """
        data = {
            "members": [{"instance_name": inst, "role": role} for inst, role in members],
            "last_updated": utc_now_iso(),
        }
        path = self.runtime_dir / "state" / "roster.yaml"
        atomic_write(path, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
        return path

    # ------------------------------------------------------------
    # events.jsonl
    # ------------------------------------------------------------

    def append_event(
        self,
        event: str,
        **details: Any,
    ) -> None:
        """向 events.jsonl 追加一条事件（带锁）。"""
        entry = {
            "ts": utc_now_iso(),
            "event": event,
            **details,
        }
        locked_append(
            self.runtime_dir / "events.jsonl",
            json.dumps(entry, ensure_ascii=False) + "\n",
        )

    # ------------------------------------------------------------
    # messages/
    # ------------------------------------------------------------

    def write_message_record(
        self,
        from_member: str,
        to_member: str,
        msg_type: str,
        content: str,
        summary: str = "",
    ) -> Path:
        """写一条消息到 messages/。

        文件名：YYYYMMDD-HHMMSS-{from}-{to}.json（本地时间，便于肉眼扫目录）
        内容 ts 字段：UTC ISO 8601 带毫秒精度（跨时区分析无歧义）
        """
        local_now = datetime.now()
        filename = (
            f"{local_now.strftime('%Y%m%d-%H%M%S')}"
            f"-{self._safe_filename_part(from_member)}"
            f"-{self._safe_filename_part(to_member)}.json"
        )
        path = self.runtime_dir / "messages" / filename

        data = {
            "ts": utc_now_iso(),
            "from": from_member,
            "to": to_member,
            "type": msg_type,
            "content": content,
            "summary": summary,
        }
        atomic_write(path, json.dumps(data, ensure_ascii=False, indent=2))
        return path

    @staticmethod
    def _safe_filename_part(raw: str) -> str:
        """把 all / 特殊字符 替换为文件名安全的形式。"""
        return raw.replace("/", "_").replace("\\", "_").replace(" ", "_").replace(":", "_")


__all__ = ["RuntimeStateManager", "utc_now_iso"]
