"""团队环境管理器（Engine 主类）。

对应设计文档：openspec/specs/design/01-engine.md

M1 范围：
- initialize：加载配置 + 创建 Adapter
- start_run：创建团队 + 派发成员 + 发送启动消息
- stop_run：shutdown 所有成员 + delete_team + 归档
- get_state / get_current_run：查询状态

M2+：Hook 系统、CostTracker、FileWatcher、升档、断点续跑。
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from ai_rd_team.adapter.base import (
    BaseAdapter,
    MemberHandle,
    Message,
    MessageType,
    TeamHandle,
)
from ai_rd_team.adapter.bridge import CodeBuddyToolBridge, FileBasedBridge
from ai_rd_team.adapter.codebuddy import CodeBuddyAdapter
from ai_rd_team.artifacts.recorder import ArtifactRecorder
from ai_rd_team.config.loader import ConfigLoader
from ai_rd_team.config.models import EffectiveConfig, Role, RunMode
from ai_rd_team.memory.manager import MemoryItem, MemoryManager
from ai_rd_team.roles.prompt import PromptRenderer, builtin_roles
from ai_rd_team.roles.skills_loader import (
    LoadedSkill,
    SkillsLoader,
)
from ai_rd_team.runtime.state import RuntimeStateManager

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class EngineState(str, Enum):
    IDLE = "idle"
    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class RunContext:
    """一次运行的上下文。"""

    run_id: str
    mode: RunMode
    started_at: datetime
    requirement: str
    team_handle: TeamHandle | None = None
    members: dict[str, MemberHandle] = field(default_factory=dict)


# M1 默认启动角色（按档位）
_MODE_DEFAULT_ROLES: dict[RunMode, list[str]] = {
    "lite": ["developer"],
    "standard": ["architect", "developer", "tester"],
    "full": ["pm", "analyst", "architect", "developer", "reviewer", "tester", "devops"],
}

# 成员 state 的终态集合（stop_run 时不再兜底覆盖这些状态）
_MEMBER_TERMINAL_STATUSES = frozenset({"done", "failed", "terminated"})


class TeamEnvironmentManager:
    """引擎主类：管理团队环境的生命周期。

    注意：本类不调度工作流 —— 启动完成后，团队成员自主推进（见 P1 验证）。
    引擎只负责"环境准备 / 通道搭建 / 状态落盘"。

    典型用法：
        engine = TeamEnvironmentManager(workspace=Path.cwd())
        engine.initialize(preset="standard", interactive=False)

        ctx = engine.start_run(requirement="实现一个用户管理模块")
        # ... 团队工作中 ...
        engine.stop_run()
    """

    def __init__(
        self,
        workspace: Path,
        bridge: CodeBuddyToolBridge | None = None,
        adapter: BaseAdapter | None = None,
    ):
        """
        Args:
            workspace: 工作区根目录
            bridge: Bridge 实例（默认 FileBasedBridge）。测试可注入 InMemoryBridge
            adapter: Adapter 实例（默认根据 config 创建 CodeBuddyAdapter）。注入后会绕过默认工厂
        """
        self.workspace = workspace
        self._state: EngineState = EngineState.IDLE

        self._config: EffectiveConfig | None = None
        self._ctx: RunContext | None = None

        # 子模块（部分在 initialize 中懒初始化）
        self._bridge = bridge
        self._adapter = adapter
        self._runtime_state: RuntimeStateManager | None = None
        self._artifact_recorder: ArtifactRecorder | None = None
        self._prompt_renderer: PromptRenderer | None = None
        self._memory_manager: MemoryManager | None = None
        self._skills_loader: SkillsLoader | None = None

    # ------------------------------------------------------------
    # 状态查询
    # ------------------------------------------------------------

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def config(self) -> EffectiveConfig:
        if self._config is None:
            raise RuntimeError("Engine not initialized")
        return self._config

    def get_current_run(self) -> RunContext | None:
        return self._ctx

    # ------------------------------------------------------------
    # initialize
    # ------------------------------------------------------------

    def initialize(
        self,
        preset: RunMode | None = None,
        allow_onboarding: bool = True,
        interactive: bool = True,
    ) -> None:
        """加载配置、创建 Adapter、准备 runtime/ 目录。"""
        self._ensure_state(EngineState.IDLE, EngineState.STOPPED)
        self._state = EngineState.INITIALIZING

        try:
            # 1. 加载配置
            loader = ConfigLoader(
                workspace_dir=self.workspace / ".ai-rd-team",
            )
            self._config = loader.load(
                preset=preset,
                allow_onboarding=allow_onboarding,
                interactive=interactive,
            )
            logger.info(
                "Config loaded: mode=%s, workspace=%s",
                self._config.active_mode,
                self._config.project.workspace,
            )

            # 2. 准备 runtime 目录
            runtime_dir = self.workspace / ".ai-rd-team" / "runtime"
            self._runtime_state = RuntimeStateManager(runtime_dir=runtime_dir)
            self._runtime_state.ensure_directories()

            self._artifact_recorder = ArtifactRecorder(
                artifacts_dir=runtime_dir / "artifacts",
            )
            self._prompt_renderer = PromptRenderer()

            # M2：Memory + Skills 加载器
            self._memory_manager = MemoryManager(
                workspace_memory_dir=self.workspace / ".ai-rd-team" / "memory",
            )
            self._memory_manager.ensure_directories()
            self._skills_loader = SkillsLoader.create_default(
                workspace=self.workspace / ".ai-rd-team",
            )

            # 3. 创建 Bridge + Adapter（若未注入）
            if self._adapter is None:
                if self._bridge is None:
                    self._bridge = FileBasedBridge(
                        runtime_dir=runtime_dir,
                        timeout_seconds=float(
                            self._config.adapter.get("bridge_timeout_seconds", 60)
                        ),
                    )
                self._adapter = CodeBuddyAdapter(
                    config=self._config.adapter,
                    bridge=self._bridge,
                    runtime_dir=runtime_dir,
                )
            self._adapter.initialize()

            self._state = EngineState.IDLE
            logger.info("Engine initialized; adapter=%s", self._adapter.platform_name)
        except Exception:
            self._state = EngineState.ERROR
            logger.exception("Engine initialize failed")
            raise

    # ------------------------------------------------------------
    # start_run
    # ------------------------------------------------------------

    def start_run(
        self,
        requirement: str,
        run_mode: RunMode | None = None,
    ) -> RunContext:
        """启动一次运行。

        Args:
            requirement: 需求描述
            run_mode: 运行档位（None 则使用 config.active_mode）

        Returns:
            RunContext（run_id / team / members 等）
        """
        self._ensure_state(EngineState.IDLE)
        assert self._config is not None
        assert self._runtime_state is not None
        assert self._adapter is not None
        assert self._prompt_renderer is not None

        mode: RunMode = run_mode or self._config.active_mode
        self._state = EngineState.STARTING

        try:
            run_id = str(uuid.uuid4())[:8]
            ctx = RunContext(
                run_id=run_id,
                mode=mode,
                started_at=datetime.now(),
                requirement=requirement,
            )

            # 1. 元数据落盘
            self._runtime_state.write_run_metadata(
                run_id=run_id,
                requirement=requirement,
                mode=mode,
            )
            self._runtime_state.append_event(
                "run_starting",
                run_id=run_id,
                mode=mode,
            )

            # 2. 创建团队
            team_id = f"ai-rd-team-{run_id}"
            team = self._adapter.create_team(
                team_id=team_id,
                description=f"Run {run_id}: {requirement[:80]}",
            )
            ctx.team_handle = team
            self._runtime_state.write_team_state(
                status="running",
                team_id=team_id,
            )

            # 3. 派发成员
            roster = self._build_roster(mode)
            self._runtime_state.write_roster(roster)

            for instance_name, role_name in roster:
                role = self._resolve_role(role_name)

                # M2：加载 Skills 与 agent.d 记忆（失败不影响成员 spawn）
                skills_section = self._render_skills_section(role)
                memory_section = self._render_agent_d_section(role)

                rendered = self._prompt_renderer.render(
                    role=role,
                    instance_name=instance_name,
                    config=self._config,
                    team_roster=roster,
                    skills_injected=skills_section,
                    agent_d_memory_injected=memory_section,
                )
                member = self._adapter.spawn_member(
                    team=team,
                    member_id=instance_name,
                    role=role_name,
                    display_name=self._prompt_renderer._resolve_display_name(role, instance_name),
                    rendered_prompt=rendered.content,
                )
                ctx.members[instance_name] = member

                # 成员初始状态
                self._runtime_state.write_member_state(
                    instance_name=instance_name,
                    role=role_name,
                    status="spawning",
                )
                self._runtime_state.append_event(
                    "member_spawned",
                    run_id=run_id,
                    member_id=instance_name,
                    role=role_name,
                )

            # 4. 发送启动消息给 starter
            starter = self._find_starter(ctx.members)
            if starter is not None:
                start_msg = self._build_start_message(requirement, ctx)
                self._adapter.send_message(
                    Message(
                        from_member="main",
                        to_member=starter.member_id,
                        msg_type=MessageType.MESSAGE,
                        content=start_msg,
                        summary="启动任务",
                    )
                )
                self._runtime_state.write_message_record(
                    from_member="main",
                    to_member=starter.member_id,
                    msg_type="message",
                    content=start_msg,
                    summary="启动任务",
                )

            # 5. 切到 RUNNING
            self._runtime_state.update_run_status("running")
            self._runtime_state.append_event(
                "run_started",
                run_id=run_id,
                team_id=team_id,
                member_count=len(ctx.members),
            )

            self._ctx = ctx
            self._state = EngineState.RUNNING
            logger.info(
                "Run started: id=%s mode=%s members=%d",
                run_id,
                mode,
                len(ctx.members),
            )
            return ctx
        except Exception:
            self._state = EngineState.ERROR
            logger.exception("start_run failed")
            raise

    # ------------------------------------------------------------
    # broadcast（T2.6）
    # ------------------------------------------------------------

    def broadcast(
        self,
        content: str,
        summary: str = "",
        from_member: str = "main",
    ) -> None:
        """向当前团队广播一条消息。

        - 仅在 RUNNING 状态可用
        - Adapter 不支持 broadcast 时会抛 CapabilityNotSupportedError
        - 会记录 broadcast 事件和消息到 runtime/messages/

        Args:
            content: 广播正文
            summary: 5-10 字摘要
            from_member: 发送者（默认 main）
        """
        self._ensure_state(EngineState.RUNNING)
        assert self._adapter is not None
        assert self._runtime_state is not None
        assert self._ctx is not None

        self._adapter.broadcast(
            content=content,
            summary=summary,
            from_member=from_member,
        )
        self._runtime_state.write_message_record(
            from_member=from_member,
            to_member="*",
            msg_type="broadcast",
            content=content,
            summary=summary,
        )
        self._runtime_state.append_event(
            "broadcast_sent",
            run_id=self._ctx.run_id,
            from_member=from_member,
            target_count=len(self._ctx.members),
            summary=summary,
        )

    # ------------------------------------------------------------
    # stop_run
    # ------------------------------------------------------------

    def stop_run(self, reason: str = "normal") -> None:
        """停止当前运行：优雅关闭成员 + 删除团队。

        兜底行为（F3）：对于没有主动把 state 更新为 done/failed 的成员，
        Engine 会把它们的 state 标记为 terminated，避免遗留 spawning/working 等
        假活状态误导后续分析。
        """
        if self._ctx is None:
            logger.warning("stop_run called without active run")
            return
        assert self._adapter is not None
        assert self._runtime_state is not None

        self._state = EngineState.STOPPING
        run_id = self._ctx.run_id
        team_id = self._ctx.team_handle.team_id if self._ctx.team_handle is not None else ""

        self._runtime_state.append_event(
            "run_stopping",
            run_id=run_id,
            reason=reason,
        )

        # 1. 请求每个成员 shutdown（F3：带上'请更新 state=done'引导）
        shutdown_hint = (
            "团队即将关闭。请把 "
            ".ai-rd-team/runtime/state/members/<你的ID>.yaml 的 status 字段更新为 "
            "'done'（若工作完成）或 'failed'（若未完成），然后退出。"
            f"原因：{reason or 'normal'}"
        )
        for instance_name, member in list(self._ctx.members.items()):
            try:
                self._adapter.request_member_shutdown(member, reason=shutdown_hint)
            except Exception as e:
                logger.warning("shutdown_request failed for %s: %s", instance_name, e)

        # 2. 删除团队
        if self._ctx.team_handle is not None:
            try:
                self._adapter.delete_team(self._ctx.team_handle)
            except Exception as e:
                logger.warning("delete_team failed: %s", e)

        # 3. 兜底：把未终止状态的成员 state 置为 terminated（F3）
        self._finalize_member_states()

        # 4. 更新 state（F2：带上 team_id 避免丢字段）
        self._runtime_state.write_team_state(status="shut_down", team_id=team_id)
        self._runtime_state.update_run_status("stopped")
        self._runtime_state.append_event("run_stopped", run_id=run_id, reason=reason)

        self._state = EngineState.STOPPED
        logger.info("Run stopped: id=%s reason=%s", run_id, reason)

    def _finalize_member_states(self) -> None:
        """把还未到终态（done/failed/terminated）的成员 state 补齐为 terminated。

        这是为了避免 E2E 报告中发现的"成员 state 残留 spawning/working"问题：
        成员可能在写 state 前被 shutdown / 或者只写了文件就退出，未更新 state=done。
        Engine 兜底一把，保证 run 结束后每个 state 都有明确终态。
        """
        assert self._runtime_state is not None
        assert self._ctx is not None

        states = self._runtime_state.list_member_states()

        for instance_name, _member in self._ctx.members.items():
            existing = states.get(instance_name)
            if existing and existing.get("status") in _MEMBER_TERMINAL_STATUSES:
                continue

            role = (existing or {}).get("role", _member.role)
            current_task = (existing or {}).get("current_task", "")
            progress = (existing or {}).get("progress", "")
            produced = (existing or {}).get("produced_files") or []
            blocking = (existing or {}).get("blocking_issues") or []

            self._runtime_state.write_member_state(
                instance_name=instance_name,
                role=role,
                status="terminated",
                current_task=current_task,
                progress=progress,
                produced_files=list(produced),
                blocking_issues=list(blocking),
            )

    # ------------------------------------------------------------
    # 私有辅助
    # ------------------------------------------------------------

    def _build_roster(self, mode: RunMode) -> list[tuple[str, str]]:
        """根据档位和启用的角色构建团队名册。

        M1：直接从 _MODE_DEFAULT_ROLES 取。M2：从 config.roles 读。
        """
        assert self._config is not None

        # 优先读 config.roles 中 enabled=True 的角色；M1 默认用档位预设
        configured_roles = {name for name, r in self._config.roles.items() if r.enabled}

        if configured_roles:
            role_names = [n for n in _MODE_DEFAULT_ROLES[mode] if n in configured_roles]
        else:
            role_names = _MODE_DEFAULT_ROLES[mode]

        roster: list[tuple[str, str]] = []
        for role_name in role_names:
            role = self._resolve_role(role_name)
            count = self._instances_for_mode(role, mode)
            if count <= 1:
                roster.append((role_name, role_name))
            else:
                for i in range(1, count + 1):
                    roster.append((f"{role_name}_{i}", role_name))
        return roster

    @staticmethod
    def _instances_for_mode(role: Role, mode: RunMode) -> int:
        """决定某角色在某档位下派发多少个实例。

        M1 规则：
        - 非 scalable：固定 1
        - scalable + lite：1
        - scalable + standard：min(default_instances, 2)
        - scalable + full：default_instances（通常 ≥ 2）
        """
        if not role.scalable:
            return 1
        if mode == "lite":
            return 1
        if mode == "standard":
            return min(role.default_instances, 2)
        return role.default_instances

    def _resolve_role(self, role_name: str) -> Role:
        """优先 config.roles，回退到 builtin_roles。"""
        assert self._config is not None
        if role_name in self._config.roles:
            return self._config.roles[role_name]
        builtin = builtin_roles()
        if role_name in builtin:
            return builtin[role_name]
        # 兜底：最小 Role 对象
        return Role(name=role_name)

    # ------------------------------------------------------------
    # M2：Skills / Memory 注入
    # ------------------------------------------------------------

    def _render_skills_section(self, role: Role) -> str:
        """加载并渲染 Skills 为 prompt 片段。失败不抛，返回占位。"""
        if self._skills_loader is None or not role.skills:
            return ""

        try:
            loaded: list[LoadedSkill] = self._skills_loader.load_for_role(
                role, missing_ok=True
            )
        except Exception as e:
            logger.warning("load skills for role %s failed: %s", role.name, e)
            return ""

        if not loaded:
            return ""

        parts: list[str] = []
        for s in loaded:
            parts.append(f"## {s.name}（{s.scope}）")
            parts.append(s.content.strip())
            parts.append("")
        return "\n".join(parts).strip()

    def _render_agent_d_section(self, role: Role) -> str:
        """加载并渲染 agent.d 记忆为 prompt 片段。失败不抛。"""
        if self._memory_manager is None:
            return ""

        try:
            items: list[MemoryItem] = self._memory_manager.load_agent_d(role)
        except Exception as e:
            logger.warning("load agent.d for role %s failed: %s", role.name, e)
            return ""

        if not items:
            return ""

        parts: list[str] = []
        for item in items:
            header = item.title or item.name
            parts.append(f"## {header}")
            parts.append(item.content_body.strip())
            parts.append("")
        return "\n".join(parts).strip()

    @staticmethod
    def _find_starter(members: dict[str, MemberHandle]) -> MemberHandle | None:
        """找到应首先收到启动消息的成员。

        优先级：pm > analyst > architect > 第一个成员
        """
        for preferred in ("pm", "analyst", "architect"):
            if preferred in members:
                return members[preferred]
        # 兜底：按插入顺序第一个
        for member in members.values():
            return member
        return None

    @staticmethod
    def _build_start_message(requirement: str, ctx: RunContext) -> str:
        """构造启动消息内容。"""
        member_list = "\n".join(f"- {m.member_id}（{m.role}）" for m in ctx.members.values())
        return (
            f"项目启动。\n\n"
            f"**需求**：\n{requirement}\n\n"
            f"**团队**：\n{member_list}\n\n"
            f"**档位**：{ctx.mode}\n\n"
            f"请按你的角色职责开始工作。需要协作时直接用 send_message 联系队友。"
        )

    def _ensure_state(self, *allowed: EngineState) -> None:
        if self._state not in allowed:
            raise RuntimeError(f"Engine in state {self._state}; expected one of {allowed}")


__all__ = [
    "EngineState",
    "RunContext",
    "TeamEnvironmentManager",
]
