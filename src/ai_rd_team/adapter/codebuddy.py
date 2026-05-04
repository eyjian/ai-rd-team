"""CodeBuddy 平台 Adapter（M1 版本）。

对应设计文档：openspec/specs/design/02-adapter.md §6

设计要点：
- 通过 CodeBuddyToolBridge 间接调用 CodeBuddy 工具（M1 采用 FileBased Bridge）
- 成员状态查询：不直接走工具，退化为读 runtime/state/members/ 文件
- 版本探测：启动时调用 _probe 获取可用工具集，推导 Capabilities
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ai_rd_team.adapter.base import (
    AdapterError,
    AdapterInitError,
    BaseAdapter,
    Capabilities,
    MemberHandle,
    MemberOperationError,
    MemberStatus,
    Message,
    MessageDeliveryError,
    MessageType,
    TeamHandle,
    TeamOperationError,
    TeamStatus,
    VersionInfo,
)
from ai_rd_team.adapter.bridge import BridgeToolError, CodeBuddyToolBridge


class CodeBuddyAdapter(BaseAdapter):
    """CodeBuddy 平台适配器。

    用法：
        bridge = FileBasedBridge(runtime_dir=ws/".ai-rd-team/runtime")
        adapter = CodeBuddyAdapter(
            config={"bridge_timeout_seconds": 60},
            bridge=bridge,
            runtime_dir=ws/".ai-rd-team/runtime",
        )
        adapter.initialize()
    """

    PLATFORM = "codebuddy"

    # 关键工具必须齐备，否则初始化失败
    _CORE_TOOLS = {"team_create", "team_delete", "task", "send_message"}

    def __init__(
        self,
        config: dict[str, Any],
        bridge: CodeBuddyToolBridge,
        runtime_dir: Path,
    ):
        super().__init__(config)
        self._bridge = bridge
        self._runtime_dir = runtime_dir
        # 团队级状态：一次运行只有 1 个团队
        self._team_handle: TeamHandle | None = None

    # ------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------

    def initialize(self) -> None:
        # 1. 版本 + 工具探测
        try:
            version = self._bridge.query_version_string()
            available = self._bridge.probe_available_tools()
        except TimeoutError as e:
            raise AdapterInitError(
                "Bridge probe timed out. 主 Agent 的 bridge 监听 Skill 可能未启用。"
            ) from e
        except BridgeToolError as e:
            raise AdapterInitError(f"Bridge probe failed: {e}") from e

        # 2. 核心工具存在性检查
        missing = self._CORE_TOOLS - available
        if missing:
            raise AdapterInitError(
                f"CodeBuddy 缺少核心工具: {sorted(missing)}。请升级 CodeBuddy 或检查环境。"
            )

        self._version_info = VersionInfo(
            platform=self.PLATFORM,
            version=version,
            detected_at=datetime.now(),
            available_tools=frozenset(available),
            notes="probed via bridge",
        )

        # 3. 能力推导
        self._capabilities = Capabilities(
            supports_team_lifecycle=True,
            supports_async_member_spawn=True,
            supports_p2p_messaging=True,
            supports_broadcast=True,
            supports_shutdown_request=True,
            supports_role_specific_model=False,  # CodeBuddy 第一期不支持
            supports_runtime_model_switch=False,
            supports_member_state_query=False,  # 退化为读 state 文件
            max_concurrent_members=15,
            message_size_limit_bytes=64 * 1024,
            spawn_timeout_seconds=int(self._config.get("spawn_timeout_seconds", 60)),
        )

    # ------------------------------------------------------------
    # 团队生命周期
    # ------------------------------------------------------------

    def create_team(self, team_id: str, description: str = "") -> TeamHandle:
        try:
            result = self._bridge.call_team_create(
                team_name=team_id,
                description=description,
            )
        except (TimeoutError, BridgeToolError) as e:
            raise TeamOperationError(f"create_team failed: {e}") from e

        handle = TeamHandle(
            team_id=team_id,
            platform_id=result.get("platform_id", team_id),
            created_at=datetime.now(),
            platform=self.PLATFORM,
        )
        self._team_handle = handle
        self.log_call("create_team", team_id=team_id)
        return handle

    def delete_team(self, team: TeamHandle) -> None:
        try:
            self._bridge.call_team_delete()
        except (TimeoutError, BridgeToolError) as e:
            raise TeamOperationError(f"delete_team failed: {e}") from e
        self._team_handle = None
        self.log_call("delete_team", team_id=team.team_id)

    def get_team_status(self, team: TeamHandle) -> TeamStatus:
        """从 runtime/state/team.yaml 推导。M1 最小版本：基于句柄存在性。"""
        state = self._read_team_state()
        if state is None:
            if self._team_handle is None:
                return TeamStatus.SHUT_DOWN
            return TeamStatus.CREATING

        raw = state.get("status", "running")
        try:
            return TeamStatus(raw)
        except ValueError:
            return TeamStatus.RUNNING

    # ------------------------------------------------------------
    # 成员生命周期
    # ------------------------------------------------------------

    def spawn_member(
        self,
        team: TeamHandle,
        member_id: str,
        role: str,
        display_name: str,
        rendered_prompt: str,
        options: dict[str, Any] | None = None,
    ) -> MemberHandle:
        opts = dict(options or {})
        # 默认的 subagent 类型：M1 统一用 code-explorer（P1 原型验证过）
        subagent_name = opts.pop("subagent_name", "code-explorer")
        mode = opts.pop("mode", "bypassPermissions")
        max_turns = opts.pop("max_turns", None)

        try:
            result = self._bridge.call_task_async(
                subagent_name=subagent_name,
                description=f"{display_name}（{role}）",
                prompt=rendered_prompt,
                name=member_id,
                team_name=team.team_id,
                mode=mode,
                max_turns=max_turns,
                **opts,
            )
        except (TimeoutError, BridgeToolError) as e:
            raise MemberOperationError(f"spawn_member failed for {member_id}: {e}") from e

        self.log_call(
            "spawn_member",
            team_id=team.team_id,
            member_id=member_id,
            role=role,
        )
        return MemberHandle(
            member_id=member_id,
            team_id=team.team_id,
            platform_id=result.get("platform_id"),
            role=role,
            display_name=display_name,
            created_at=datetime.now(),
        )

    def request_member_shutdown(
        self,
        member: MemberHandle,
        reason: str = "",
    ) -> None:
        try:
            self._bridge.call_send_message(
                type=MessageType.SHUTDOWN_REQUEST.value,
                recipient=member.member_id,
                content=reason or "",
            )
        except (TimeoutError, BridgeToolError) as e:
            raise MemberOperationError(
                f"request_member_shutdown failed for {member.member_id}: {e}"
            ) from e
        self.log_call(
            "request_member_shutdown",
            member_id=member.member_id,
            reason=reason,
        )

    def get_member_status(self, member: MemberHandle) -> MemberStatus:
        """CodeBuddy 不提供成员状态查询工具 → 退化为读 state 文件（§3.2 注释）。"""
        state_file = self._runtime_dir / "state" / "members" / f"{member.member_id}.yaml"
        if not state_file.is_file():
            return MemberStatus.SPAWNING

        # state 文件是 YAML，但我们只关心 status 字段
        try:
            import yaml

            raw = yaml.safe_load(state_file.read_text(encoding="utf-8")) or {}
        except (OSError, Exception):
            return MemberStatus.IDLE

        status = raw.get("status", "idle")
        try:
            return MemberStatus(status)
        except ValueError:
            return MemberStatus.IDLE

    # ------------------------------------------------------------
    # 消息通信
    # ------------------------------------------------------------

    def send_message(self, msg: Message) -> None:
        # 校验长度
        if len(msg.content.encode("utf-8")) > self.capabilities.message_size_limit_bytes:
            raise MessageDeliveryError(f"message too large: {len(msg.content)} chars > limit")

        # 根据消息类型派发到 bridge
        try:
            if msg.msg_type == MessageType.MESSAGE:
                self._bridge.call_send_message(
                    type="message",
                    recipient=msg.to_member,
                    content=msg.content,
                    summary=msg.summary or self._default_summary(msg),
                )
            elif msg.msg_type == MessageType.BROADCAST:
                self._bridge.call_send_message(
                    type="broadcast",
                    content=msg.content,
                    summary=msg.summary or self._default_summary(msg),
                )
            elif msg.msg_type == MessageType.SHUTDOWN_REQUEST:
                self._bridge.call_send_message(
                    type="shutdown_request",
                    recipient=msg.to_member,
                    content=msg.content or "",
                )
            elif msg.msg_type == MessageType.SHUTDOWN_RESPONSE:
                self._bridge.call_send_message(
                    type="shutdown_response",
                    request_id=msg.request_id,
                    approve=msg.approve if msg.approve is not None else True,
                )
            elif msg.msg_type == MessageType.PLAN_APPROVAL_RESPONSE:
                self._bridge.call_send_message(
                    type="plan_approval_response",
                    recipient=msg.to_member,
                    request_id=msg.request_id,
                    approve=msg.approve if msg.approve is not None else True,
                )
            else:
                raise MessageDeliveryError(f"unsupported message type: {msg.msg_type}")
        except (TimeoutError, BridgeToolError) as e:
            raise MessageDeliveryError(f"send_message failed: {e}") from e

        self.log_call(
            "send_message",
            msg_type=msg.msg_type.value,
            from_=msg.from_member,
            to=msg.to_member,
        )

    # ------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------

    def _read_team_state(self) -> dict[str, Any] | None:
        """读 runtime/state/team.yaml（若存在）。"""
        team_file = self._runtime_dir / "state" / "team.yaml"
        if not team_file.is_file():
            return None
        try:
            import yaml

            return yaml.safe_load(team_file.read_text(encoding="utf-8")) or {}
        except (OSError, Exception):
            return None

    @staticmethod
    def _default_summary(msg: Message) -> str:
        """若调用方未提供 summary，从 content 截取前 10 个字符作为摘要。"""
        content = msg.content.strip().replace("\n", " ")
        return content[:10] if content else "消息"

    # ------------------------------------------------------------
    # 日志（覆盖 BaseAdapter 默认空实现）
    # ------------------------------------------------------------

    def log_call(self, operation: str, **details: Any) -> None:
        """追加到 runtime/logs/adapter-calls.jsonl。"""
        try:
            from ai_rd_team.utils.file_ops import locked_append

            entry = {
                "ts": datetime.now().isoformat(),
                "platform": self.PLATFORM,
                "op": operation,
                **details,
            }
            import json

            locked_append(
                self._runtime_dir / "logs" / "adapter-calls.jsonl",
                json.dumps(entry, ensure_ascii=False) + "\n",
            )
        except (OSError, AdapterError):
            # 日志失败不应中断业务
            pass


__all__ = ["CodeBuddyAdapter"]
