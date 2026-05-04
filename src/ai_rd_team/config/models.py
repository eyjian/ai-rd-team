"""配置数据类定义。

对应设计文档：openspec/specs/design/10-config-schema.md §3A（Basic Schema）+ §8（EffectiveConfig）

设计要点：
- 所有配置对象用 @dataclass(frozen=True)，加载后不可变
- Basic 层是 Advanced 的严格子集（§3A.3 映射表）
- 预算档位 Lite=120 / Standard=400 / Full=1500 资源点
- 权重 v1：spawn=40, msg=2, bcast=2, min=5, iter=15（来自 P5 校准）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

# 档位字面量
RunMode = Literal["lite", "standard", "full"]

# 计费模式
BillingMode = Literal[
    "auto",
    "subscription",
    "resource_units",
    "estimated_cost",
    "central_quota",
]

# 超限行为
OnExceed = Literal[
    "smart_pause",
    "pause_and_ask",
    "warn_only",
    "terminate",
    "block_new_run",
    "warn_and_block",
    "block_and_report",
]


# ============================================================
# Basic 层 Schema（§3A）
# ============================================================


@dataclass(frozen=True)
class BasicTechStack:
    """Basic 层的技术栈偏好（null 表示架构师自主选择）。"""

    backend: str | None = None
    frontend: str | None = None
    mobile: str | None = None


@dataclass(frozen=True)
class BasicBudget:
    """Basic 层的预算配置（Resource Points）。"""

    per_run: int = 400  # Standard 档默认
    per_day: int = 2000


@dataclass(frozen=True)
class BasicProject:
    """Basic 层的项目信息。"""

    description: str = ""


@dataclass(frozen=True)
class BasicConfig:
    """Basic 层的完整配置（§3A.1）。

    这是 99% 用户实际看到的 config.yaml 的内存表示。
    """

    config_version: str = "1.0"
    project: BasicProject = field(default_factory=BasicProject)
    run_mode: RunMode = "standard"
    tech_stack: BasicTechStack = field(default_factory=BasicTechStack)
    budget: BasicBudget = field(default_factory=BasicBudget)


# ============================================================
# Advanced 层的细粒度数据类（§8.1）
# ============================================================


@dataclass(frozen=True)
class ProjectInfo:
    """项目信息（含工作区绝对路径）。"""

    name: str
    description: str
    workspace: Path


@dataclass(frozen=True)
class ResourcePointWeights:
    """Resource Points 权重（v1 来自 P5 校准）。"""

    per_member_spawn: int = 40
    per_message: int = 2
    per_broadcast_target: int = 2
    per_minute_runtime: int = 5
    per_iteration: int = 15
    version: str = "v1"


@dataclass(frozen=True)
class Budget:
    """单次运行预算（档位相关）。"""

    max_members: int
    max_messages: int
    max_broadcasts: int
    max_runtime_minutes: int
    max_total_iterations: int
    max_resource_points: int


@dataclass(frozen=True)
class QuotaWindows:
    """多级时间窗口额度（§3.11）。"""

    per_run: int = 400
    per_day: int = 2000
    per_week: int = 10000
    per_month: int = 30000


@dataclass(frozen=True)
class ModelFallback:
    """模型降级配置（第一期 semi_auto）。"""

    enabled: bool = True
    fallback_mode: Literal["auto", "semi_auto", "full_auto", "disabled"] = "auto"
    trigger_threshold: float = 0.75
    strategy: Literal["hybrid", "cascade", "role_based"] = "hybrid"
    model_chain: tuple[str, ...] = (
        "claude-sonnet-4",
        "claude-haiku",
        "deepseek-v3",
        "local-qwen",
    )
    role_priority: dict[str, int] = field(default_factory=dict)
    on_trigger: Literal["auto", "ask", "notify_only"] = "auto"


@dataclass(frozen=True)
class CostControl:
    """成本控制配置（§3.11 全量）。"""

    enabled: bool = True
    billing_mode: BillingMode = "auto"
    display_currency: str = "auto"
    confirm_currency_on_startup: bool = True
    resource_point_weights: ResourcePointWeights = field(default_factory=ResourcePointWeights)
    budget_lite: Budget = field(
        default_factory=lambda: Budget(
            max_members=2,
            max_messages=20,
            max_broadcasts=0,
            max_runtime_minutes=30,
            max_total_iterations=5,
            max_resource_points=120,
        )
    )
    budget_standard: Budget = field(
        default_factory=lambda: Budget(
            max_members=5,
            max_messages=100,
            max_broadcasts=3,
            max_runtime_minutes=120,
            max_total_iterations=15,
            max_resource_points=400,
        )
    )
    budget_full: Budget = field(
        default_factory=lambda: Budget(
            max_members=15,
            max_messages=500,
            max_broadcasts=10,
            max_runtime_minutes=480,
            max_total_iterations=50,
            max_resource_points=1500,
        )
    )
    on_budget_exceeded: OnExceed = "smart_pause"
    quota_enabled: bool = True
    quota_windows: QuotaWindows = field(default_factory=QuotaWindows)
    quota_on_exceed: dict[str, str] = field(default_factory=dict)
    model_fallback: ModelFallback = field(default_factory=ModelFallback)
    post_run_recording_enabled: bool = True
    default_mode: Literal["ask", "lite", "standard", "full"] = "ask"
    remembered_mode: RunMode | None = None


@dataclass(frozen=True)
class Role:
    """角色定义（§3.2）。"""

    name: str
    enabled: bool = True
    display_name: str = ""
    persona: str = ""
    scalable: bool = False
    max_instances: int = 1
    default_instances: int = 1
    skills: tuple[str, ...] = ()
    rules: tuple[str, ...] = ()
    memory_scope: dict[str, Any] = field(default_factory=dict)
    model: str | None = None


# ============================================================
# 顶层 EffectiveConfig
# ============================================================


@dataclass(frozen=True)
class EffectiveConfig:
    """合并后的最终配置对象（§8.1）。

    所有模块通过此对象只读访问配置。
    """

    config_version: str
    project: ProjectInfo
    roles: dict[str, Role] = field(default_factory=dict)
    tech_stack: dict[str, Any] = field(default_factory=dict)
    adapter: dict[str, Any] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    team: dict[str, Any] = field(default_factory=dict)
    security: dict[str, Any] = field(default_factory=dict)
    web: dict[str, Any] = field(default_factory=dict)
    hooks: dict[str, Any] = field(default_factory=dict)
    notifications: dict[str, Any] = field(default_factory=dict)
    quality_gates: dict[str, Any] = field(default_factory=dict)
    logging: dict[str, Any] = field(default_factory=dict)
    resource_limits: dict[str, Any] = field(default_factory=dict)
    cost_control: CostControl = field(default_factory=CostControl)
    role_models: dict[str, Any] = field(default_factory=dict)
    tools: dict[str, Any] = field(default_factory=dict)
    rules: dict[str, Any] = field(default_factory=dict)

    # 元信息
    source_files: tuple[Path, ...] = ()
    loaded_at: datetime = field(default_factory=datetime.now)

    # 便捷访问：当前运行档位
    @property
    def active_mode(self) -> RunMode:
        """当前生效的运行档位。"""
        if self.cost_control.remembered_mode is not None:
            return self.cost_control.remembered_mode
        if self.cost_control.default_mode in ("lite", "standard", "full"):
            return self.cost_control.default_mode  # type: ignore[return-value]
        return "standard"

    @property
    def active_budget(self) -> Budget:
        """当前档位对应的预算。"""
        mode = self.active_mode
        mapping = {
            "lite": self.cost_control.budget_lite,
            "standard": self.cost_control.budget_standard,
            "full": self.cost_control.budget_full,
        }
        return mapping[mode]
