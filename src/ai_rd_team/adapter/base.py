"""平台无关的 Adapter 抽象接口。

对应设计文档：openspec/specs/design/02-adapter.md §3

核心设计原则：
- 所有方法名/参数/返回值都用 ai-rd-team 业务语义，不暴露平台工具名
- 通过 Capabilities 声明能力，上层根据能力降级
- 所有值对象 frozen=True 不可变
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# ============================================================
# 枚举
# ============================================================


class MessageType(str, Enum):
    """消息类型（§3.1）。"""

    MESSAGE = "message"
    BROADCAST = "broadcast"
    SHUTDOWN_REQUEST = "shutdown_request"
    SHUTDOWN_RESPONSE = "shutdown_response"
    PLAN_APPROVAL_RESPONSE = "plan_approval_response"


class MemberStatus(str, Enum):
    """成员状态。"""

    SPAWNING = "spawning"
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    DONE = "done"
    FAILED = "failed"
    TERMINATED = "terminated"


class TeamStatus(str, Enum):
    """团队状态。"""

    CREATING = "creating"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    SHUTTING_DOWN = "shutting_down"
    SHUT_DOWN = "shut_down"
    ERROR = "error"


# ============================================================
# 值对象
# ============================================================


@dataclass(frozen=True)
class TeamHandle:
    """团队句柄。"""

    team_id: str  # 业务层 ID
    platform_id: str  # 平台内部 ID（如 CodeBuddy team_name）
    created_at: datetime
    platform: str  # "codebuddy" / "trae" / "qoder"


@dataclass(frozen=True)
class MemberHandle:
    """成员句柄。"""

    member_id: str  # 业务层 ID（通常 instance_name）
    team_id: str
    platform_id: str | None  # 平台内部 ID
    role: str  # 角色名
    display_name: str
    created_at: datetime


@dataclass(frozen=True)
class Message:
    """成员间消息。"""

    from_member: str  # 发送者或 "main"
    to_member: str  # 接收者、"main" 或 "all"
    msg_type: MessageType
    content: str
    summary: str = ""
    ts: datetime = field(default_factory=datetime.now)
    # 可选：对 shutdown_response/plan_approval_response 等有用
    request_id: str | None = None
    approve: bool | None = None


@dataclass(frozen=True)
class Capabilities:
    """Adapter 能力声明（§3.1）。

    上层根据能力决定行为模式（例如不支持 P2P 则降级成 main 转发）。
    """

    supports_team_lifecycle: bool = False
    supports_async_member_spawn: bool = False
    supports_p2p_messaging: bool = False
    supports_broadcast: bool = False
    supports_shutdown_request: bool = False
    supports_role_specific_model: bool = False
    supports_runtime_model_switch: bool = False
    supports_member_state_query: bool = False
    max_concurrent_members: int = 1
    message_size_limit_bytes: int = 64 * 1024
    spawn_timeout_seconds: int = 60


@dataclass(frozen=True)
class VersionInfo:
    """平台版本信息。"""

    platform: str
    version: str | None  # 可能探测不到
    detected_at: datetime
    available_tools: frozenset[str] = frozenset()
    notes: str = ""


# ============================================================
# 异常
# ============================================================


class AdapterError(Exception):
    """所有 Adapter 层错误的基类。"""


class AdapterInitError(AdapterError):
    """Adapter 初始化失败。"""


class TeamOperationError(AdapterError):
    """团队操作失败。"""


class MemberOperationError(AdapterError):
    """成员操作失败。"""


class MessageDeliveryError(AdapterError):
    """消息投递失败。"""


class CapabilityNotSupportedError(AdapterError):
    """当前 Adapter 不支持请求的能力。"""


class RetryExhaustedError(AdapterError):
    """重试次数耗尽。"""


# ============================================================
# 抽象基类
# ============================================================


class BaseAdapter(abc.ABC):
    """所有平台 Adapter 的抽象基类。

    实现者必须覆盖 @abstractmethod 标注的方法。
    """

    def __init__(self, config: dict[str, Any]):
        """初始化。

        Args:
            config: EffectiveConfig.adapter 子 dict（不是整个 config）
        """
        self._config = config
        self._version_info: VersionInfo | None = None
        self._capabilities: Capabilities | None = None

    # ------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------

    @abc.abstractmethod
    def initialize(self) -> None:
        """首次使用前调用：版本探测、能力推导、连接测试等。

        Raises:
            AdapterInitError
        """

    # ------------------------------------------------------------
    # 元信息查询
    # ------------------------------------------------------------

    @property
    def platform_name(self) -> str:
        """平台名，如 'codebuddy'。"""
        return self.__class__.__name__.replace("Adapter", "").lower()

    @property
    def version_info(self) -> VersionInfo:
        if self._version_info is None:
            raise AdapterError("Adapter not initialized; call initialize() first")
        return self._version_info

    @property
    def capabilities(self) -> Capabilities:
        if self._capabilities is None:
            raise AdapterError("Adapter not initialized; call initialize() first")
        return self._capabilities

    # ------------------------------------------------------------
    # 团队生命周期
    # ------------------------------------------------------------

    @abc.abstractmethod
    def create_team(
        self,
        team_id: str,
        description: str = "",
    ) -> TeamHandle:
        """创建团队环境。

        Raises:
            TeamOperationError
        """

    @abc.abstractmethod
    def delete_team(self, team: TeamHandle) -> None:
        """删除团队。调用方应确保所有成员已关闭。"""

    @abc.abstractmethod
    def get_team_status(self, team: TeamHandle) -> TeamStatus:
        """查询团队状态。"""

    # ------------------------------------------------------------
    # 成员生命周期
    # ------------------------------------------------------------

    @abc.abstractmethod
    def spawn_member(
        self,
        team: TeamHandle,
        member_id: str,
        role: str,
        display_name: str,
        rendered_prompt: str,
        options: dict[str, Any] | None = None,
    ) -> MemberHandle:
        """在团队中派发一个成员。

        Args:
            rendered_prompt: PromptRenderer 产出的完整 prompt

        Raises:
            MemberOperationError
        """

    @abc.abstractmethod
    def request_member_shutdown(
        self,
        member: MemberHandle,
        reason: str = "",
    ) -> None:
        """请求成员优雅关闭。"""

    @abc.abstractmethod
    def get_member_status(self, member: MemberHandle) -> MemberStatus:
        """查询成员状态（不支持时退化为读 state 文件）。"""

    # ------------------------------------------------------------
    # 消息通信
    # ------------------------------------------------------------

    @abc.abstractmethod
    def send_message(self, msg: Message) -> None:
        """投递消息。

        Raises:
            MessageDeliveryError
            CapabilityNotSupportedError: 如请求 broadcast 但不支持
        """

    # ------------------------------------------------------------
    # 可选能力（默认不支持，实现类可覆盖）
    # ------------------------------------------------------------

    def switch_member_model(
        self,
        member: MemberHandle,
        target_model: str,
    ) -> None:
        """运行时切换成员模型。默认不支持。"""
        raise CapabilityNotSupportedError(
            f"{self.platform_name} does not support runtime model switch"
        )

    # ------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------

    def log_call(self, operation: str, **details: Any) -> None:
        """记录一次 Adapter 调用。子类可覆盖落盘到 adapter-calls.jsonl。"""
        return

    # ------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------

    def validate_capabilities_for(
        self,
        required: dict[str, bool],
    ) -> list[str]:
        """检查是否满足能力需求，返回缺失能力名的列表。"""
        caps = self.capabilities
        missing: list[str] = []
        for name, needed in required.items():
            if needed and not getattr(caps, name, False):
                missing.append(name)
        return missing
