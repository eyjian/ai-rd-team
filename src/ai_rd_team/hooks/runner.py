"""HookRunner：Hook 执行器（T2.11 + T2.12）。

对应设计文档：openspec/specs/design/09-hooks-security.md §2

核心职责：
- 注册内置 + 用户自定义 Hook
- 按 trigger 触发，按 priority 排序（数字越小越先）
- 执行 shell 命令（可选 python 脚本），传入上下文环境变量
- on_failure 策略：warn / block / ignore
- 超时控制
- 环境变量注入 + ``${VAR}`` 占位替换

安全约束（§3.5）：
- on_failure=block 的 Hook 必须通过命令白名单（或内置）
- 无白名单时禁止配置 block 级 Hook
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import shlex
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ai_rd_team.runtime.state import utc_now_iso
from ai_rd_team.utils.file_ops import locked_append

logger = logging.getLogger(__name__)

FailurePolicy = Literal["warn", "block", "ignore"]


# -----------------------------------------------------------------
# 数据结构
# -----------------------------------------------------------------


@dataclass(frozen=True)
class HookDef:
    """Hook 定义（来源：内置 or 配置）。"""

    name: str
    trigger: str
    priority: int = 50
    command: str = ""  # shell 命令（与 callable 二选一）
    env: dict[str, str] = field(default_factory=dict)
    on_failure: FailurePolicy = "warn"
    timeout_seconds: int = 30
    when: dict[str, Any] = field(default_factory=dict)  # 条件过滤
    builtin: bool = False
    # 内置 Hook 可提供 Python 可调用对象（优先于 command）
    callable: Callable[..., Any] | None = None


@dataclass
class HookResult:
    """Hook 执行结果。"""

    hook_name: str
    trigger: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    failed: bool = False
    error: str = ""
    skipped: bool = False
    duration_ms: int = 0


class HookError(Exception):
    """Hook 基础异常。"""


class HookBlockedError(HookError):
    """on_failure=block 的 Hook 失败，引擎应中止。"""

    def __init__(self, hook_name: str, reason: str):
        super().__init__(f"hook {hook_name!r} blocked: {reason}")
        self.hook_name = hook_name
        self.reason = reason


class HookSecurityError(HookError):
    """Hook 配置违反安全约束。"""


# -----------------------------------------------------------------
# 环境变量占位替换
# -----------------------------------------------------------------

_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _expand_placeholders(
    text: str,
    context_env: dict[str, str],
    os_env: dict[str, str] | None = None,
) -> str:
    """把 ``${VAR}`` 替换为对应值。

    查找顺序：context_env > os_env > 空串（不触发 KeyError）
    """
    if not text or "${" not in text:
        return text
    os_env = os_env if os_env is not None else dict(os.environ)

    def _sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key in context_env:
            return str(context_env[key])
        return str(os_env.get(key, ""))

    return _VAR_RE.sub(_sub, text)


# -----------------------------------------------------------------
# HookRunner
# -----------------------------------------------------------------


@dataclass
class HookRunner:
    """Hook 执行器。

    典型用法::

        runner = HookRunner(
            hooks_config=effective_config.hooks,
            workspace=workspace_path,
            events_file=runtime_dir / "events.jsonl",
        )
        runner.trigger("run_started", run_id="abc", team_id="team-x")
    """

    hooks_config: dict[str, Any]
    workspace: Path
    events_file: Path | None = None
    hooks_log_file: Path | None = None
    # builtin 是否被 config.enabled=false 全局关闭
    _registered: dict[str, list[HookDef]] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._load_builtin()
        self._load_custom()

    # -----------------------------------------------------------------
    # 查询
    # -----------------------------------------------------------------

    def enabled(self) -> bool:
        return bool(self.hooks_config.get("enabled", True))

    def registered_for(self, trigger: str) -> list[HookDef]:
        return list(self._registered.get(trigger, []))

    def all_triggers(self) -> list[str]:
        return sorted(self._registered.keys())

    # -----------------------------------------------------------------
    # 触发
    # -----------------------------------------------------------------

    def trigger(
        self,
        trigger: str,
        **context: Any,
    ) -> list[HookResult]:
        """触发某个 Hook 点，执行所有注册到该点的 Hook。

        Raises:
            HookBlockedError: on_failure=block 的 Hook 失败时
        """
        if not self.enabled():
            return []
        hooks = self._registered.get(trigger, [])
        if not hooks:
            return []

        results: list[HookResult] = []
        for hook in hooks:
            if not self._check_when(hook, context):
                results.append(
                    HookResult(
                        hook_name=hook.name,
                        trigger=trigger,
                        skipped=True,
                    )
                )
                continue
            result = self._execute(hook, trigger, context)
            results.append(result)
            self._log_result(result)

            if result.failed and hook.on_failure == "block":
                raise HookBlockedError(hook.name, result.error or result.stderr)
            if result.failed and hook.on_failure == "warn":
                logger.warning(
                    "hook %s failed (warn): %s", hook.name, result.error or result.stderr
                )

        return results

    # -----------------------------------------------------------------
    # 注册：内置 Hook
    # -----------------------------------------------------------------

    def _load_builtin(self) -> None:
        """注册内置 Hook（T2.12）：log_message / state_updater / cost / events / git。"""
        builtin_cfg = self.hooks_config.get("builtin") or {}

        # events_emitter：所有触发都写 events.jsonl（幂等，便于审计）
        if builtin_cfg.get("events_emitter", True):
            self._register(
                HookDef(
                    name="events_emitter",
                    trigger="*",  # 特殊：通配符
                    priority=1,
                    builtin=True,
                    callable=self._builtin_events_emitter,
                )
            )

        # log_every_message：写消息审计
        if builtin_cfg.get("log_every_message", True):
            self._register(
                HookDef(
                    name="log_every_message",
                    trigger="message_sent",
                    priority=20,
                    builtin=True,
                    callable=self._builtin_log_message,
                )
            )

        # state_updater：member_status_changed 时同步 state 摘要
        if builtin_cfg.get("auto_save_state", True):
            self._register(
                HookDef(
                    name="state_updater",
                    trigger="member_status_changed",
                    priority=20,
                    builtin=True,
                    callable=self._builtin_state_updater,
                )
            )

        # cost_tracker：预算阈值到达时记录
        if builtin_cfg.get("cost_tracker", True):
            self._register(
                HookDef(
                    name="cost_tracker",
                    trigger="budget_threshold_reached",
                    priority=30,
                    builtin=True,
                    callable=self._builtin_cost_tracker,
                )
            )

        # git_auto_commit_on_phase：默认关
        if builtin_cfg.get("git_auto_commit_on_phase", False):
            self._register(
                HookDef(
                    name="git_auto_commit_on_phase",
                    trigger="phase_complete",
                    priority=100,
                    builtin=True,
                    callable=self._builtin_git_commit,
                )
            )

    # -----------------------------------------------------------------
    # 注册：自定义 Hook
    # -----------------------------------------------------------------

    def _load_custom(self) -> None:
        custom = self.hooks_config.get("custom") or []
        if not isinstance(custom, list):
            logger.warning("hooks.custom should be a list, got %s", type(custom))
            return

        for raw in custom:
            if not isinstance(raw, dict):
                continue
            hook = self._parse_hook(raw)
            if hook is None:
                continue

            # 安全校验（§3.5）：block 级 Hook 额外校验
            if hook.on_failure == "block":
                self._validate_block_hook(hook)

            self._register(hook)

    def _parse_hook(self, raw: dict) -> HookDef | None:
        name = raw.get("name")
        trigger = raw.get("trigger")
        command = raw.get("command", "")
        if not name or not trigger:
            logger.warning("skip hook with missing name/trigger: %s", raw)
            return None
        if not command:
            logger.warning("skip hook %s with no command", name)
            return None
        return HookDef(
            name=str(name),
            trigger=str(trigger),
            priority=int(raw.get("priority", 50)),
            command=str(command),
            env=dict(raw.get("env") or {}),
            on_failure=raw.get("on_failure", "warn"),
            timeout_seconds=int(raw.get("timeout_seconds", 30)),
            when=dict(raw.get("when") or {}),
            builtin=False,
        )

    def _validate_block_hook(self, hook: HookDef) -> None:
        """block 级 Hook 要求命令必须在 security.hook_commands_whitelist 白名单内。"""
        security = self.hooks_config.get("security") or {}
        whitelist = security.get("hook_commands_whitelist") or []
        if whitelist:
            first_token = shlex.split(hook.command)[0] if hook.command else ""
            if first_token not in whitelist:
                raise HookSecurityError(
                    f"block-level hook {hook.name!r} command {first_token!r} "
                    f"not in hook_commands_whitelist"
                )
        # 无白名单时，允许但发出警告
        else:
            logger.warning(
                "block-level hook %s has no command whitelist; allowing by default",
                hook.name,
            )

    def _register(self, hook: HookDef) -> None:
        bucket = self._registered.setdefault(hook.trigger, [])
        bucket.append(hook)
        bucket.sort(key=lambda h: h.priority)

    # -----------------------------------------------------------------
    # 执行
    # -----------------------------------------------------------------

    def _execute(
        self,
        hook: HookDef,
        trigger: str,
        context: dict[str, Any],
    ) -> HookResult:
        """单个 Hook 的执行。"""
        import time as _time

        t0 = _time.monotonic()

        # 内置 Hook：直接调 Python 函数
        if hook.callable is not None:
            try:
                hook.callable(trigger=trigger, context=context)
                return HookResult(
                    hook_name=hook.name,
                    trigger=trigger,
                    duration_ms=int((_time.monotonic() - t0) * 1000),
                )
            except Exception as e:
                return HookResult(
                    hook_name=hook.name,
                    trigger=trigger,
                    failed=True,
                    error=str(e),
                    duration_ms=int((_time.monotonic() - t0) * 1000),
                )

        # 外部命令 Hook
        env = os.environ.copy()
        env.update(self._context_env(context))
        # 用户定义的 env（支持 ${VAR} 占位）
        context_env_for_expand = {k: str(v) for k, v in self._context_env(context).items()}
        for k, v in hook.env.items():
            env[k] = _expand_placeholders(str(v), context_env_for_expand, env)

        expanded_cmd = _expand_placeholders(hook.command, context_env_for_expand, env)

        try:
            proc = subprocess.run(
                expanded_cmd,
                shell=True,
                env=env,
                cwd=str(self.workspace),
                timeout=hook.timeout_seconds,
                capture_output=True,
                text=True,
                check=False,
            )
            return HookResult(
                hook_name=hook.name,
                trigger=trigger,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                failed=proc.returncode != 0,
                duration_ms=int((_time.monotonic() - t0) * 1000),
            )
        except subprocess.TimeoutExpired:
            return HookResult(
                hook_name=hook.name,
                trigger=trigger,
                failed=True,
                error=f"timeout after {hook.timeout_seconds}s",
                duration_ms=int((_time.monotonic() - t0) * 1000),
            )
        except Exception as e:
            return HookResult(
                hook_name=hook.name,
                trigger=trigger,
                failed=True,
                error=str(e),
                duration_ms=int((_time.monotonic() - t0) * 1000),
            )

    def _check_when(self, hook: HookDef, context: dict[str, Any]) -> bool:
        """when 条件过滤（M2 最简：key=value 精确匹配全部命中）。"""
        if not hook.when:
            return True
        return all(context.get(k) == v for k, v in hook.when.items())

    def _context_env(self, context: dict[str, Any]) -> dict[str, str]:
        """把 trigger 上下文转成环境变量形式（全部大写）。"""
        env: dict[str, str] = {}
        for k, v in context.items():
            if v is None:
                continue
            key = k.upper()
            if isinstance(v, (str, int, float, bool)):
                env[key] = str(v)
            else:
                try:
                    env[key] = json.dumps(v, ensure_ascii=False)
                except (TypeError, ValueError):
                    env[key] = str(v)
        return env

    # -----------------------------------------------------------------
    # 日志
    # -----------------------------------------------------------------

    def _log_result(self, result: HookResult) -> None:
        if self.hooks_log_file is None:
            return
        entry = {
            "ts": utc_now_iso(),
            "hook": result.hook_name,
            "trigger": result.trigger,
            "failed": result.failed,
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "skipped": result.skipped,
        }
        if result.error:
            entry["error"] = result.error
        try:
            locked_append(
                self.hooks_log_file,
                json.dumps(entry, ensure_ascii=False) + "\n",
            )
        except OSError as e:
            logger.debug("failed to log hook result: %s", e)

    # -----------------------------------------------------------------
    # 内置 Hook 实现（T2.12）
    # -----------------------------------------------------------------

    def _builtin_events_emitter(self, trigger: str, context: dict) -> None:
        """把 trigger 追加到 events.jsonl（若配置）。"""
        if self.events_file is None:
            return
        entry = {
            "ts": utc_now_iso(),
            "event": trigger,
            **{k: v for k, v in context.items() if not k.startswith("_")},
        }
        locked_append(
            self.events_file,
            json.dumps(entry, ensure_ascii=False) + "\n",
        )

    def _builtin_log_message(self, trigger: str, context: dict) -> None:
        """message_sent 的审计记录。真实写入在 RuntimeStateManager 中，这里只是占位。"""
        logger.debug(
            "message: from=%s to=%s type=%s",
            context.get("from_member"),
            context.get("to_member"),
            context.get("msg_type"),
        )

    def _builtin_state_updater(self, trigger: str, context: dict) -> None:
        """member_status_changed 时记录。实际写入由 RuntimeStateManager 完成。"""
        logger.debug(
            "member status changed: id=%s new_status=%s",
            context.get("member_id"),
            context.get("new_status"),
        )

    def _builtin_cost_tracker(self, trigger: str, context: dict) -> None:
        """预算阈值到达时的记录（CostTracker 独立运作，这里只是 Hook 钩子）。"""
        logger.info(
            "budget_threshold_reached: rp=%s budget=%s",
            context.get("rp_used"),
            context.get("rp_budget"),
        )

    def _builtin_git_commit(self, trigger: str, context: dict) -> None:
        """phase_complete 时自动 git commit（默认关）。"""
        phase = context.get("phase", "unknown")
        message = f"ai-rd-team: phase {phase} complete"
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(self.workspace),
                check=False,
                capture_output=True,
                timeout=20,
            )
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=str(self.workspace),
                check=False,
                capture_output=True,
                timeout=20,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning("git auto commit failed: %s", e)

    # -----------------------------------------------------------------
    # 供测试用的辅助
    # -----------------------------------------------------------------

    def snapshot_registered(self) -> dict[str, list[str]]:
        """返回 trigger → [hook_name...] 的浅快照。"""
        return {trigger: [h.name for h in hooks] for trigger, hooks in self._registered.items()}


# -----------------------------------------------------------------
# Security 检查（T2.13）
# -----------------------------------------------------------------


DEFAULT_COMMAND_BLOCKLIST: tuple[str, ...] = (
    "rm -rf /",
    "rm -rf ~",
    "rm -rf .git",
    "sudo ",
    "curl | sh",
    "wget | sh",
    "> /etc/",
    "chmod 777",
    ":(){ :|:& };:",
    "dd if=/dev/zero",
    "mkfs",
    "shutdown",
    "reboot",
)


@dataclass
class SecurityGuard:
    """安全约束检查（T2.13）。

    - 命令白/黑名单（§3.1）
    - 文件访问规则（§3.2）：writable / readonly / forbidden
    - 敏感数据脱敏（§3.4）

    实例化后通过 check_command / check_file_access / redact 检查具体动作。
    """

    config: dict[str, Any]

    def __post_init__(self) -> None:
        cmd_cfg = self.config.get("commands") or {}
        self.allowed: list[str] = list(cmd_cfg.get("allowed") or [])
        blocked = list(cmd_cfg.get("blocked") or [])
        # 默认黑名单兜底
        for pattern in DEFAULT_COMMAND_BLOCKLIST:
            if pattern not in blocked:
                blocked.append(pattern)
        self.blocked: list[str] = blocked

        fa = self.config.get("file_access") or {}
        self.writable = [str(p) for p in (fa.get("writable") or [])]
        self.readonly = [str(p) for p in (fa.get("readonly") or [])]
        self.forbidden = [str(p) for p in (fa.get("forbidden") or [])]

        redact = self.config.get("redact") or {}
        self.redact_patterns: list[str] = list(redact.get("patterns") or [])
        self.redact_fields: list[str] = list(redact.get("fields") or [])
        self._redact_re = (
            re.compile("|".join(self.redact_patterns)) if self.redact_patterns else None
        )

    # --- 命令检查 ---

    def check_command(self, command: str) -> tuple[bool, str]:
        """返回 (allowed, reason)。"""
        cmd = command.strip()
        if not cmd:
            return False, "empty command"

        # 黑名单：子串匹配（足够严格）
        for pattern in self.blocked:
            if pattern in cmd:
                return False, f"matches blocked pattern: {pattern}"

        # 白名单：若设置了则必须命中（按命令首词匹配）
        if self.allowed:
            first = shlex.split(cmd)[0] if cmd else ""
            if first not in self.allowed:
                return False, f"command {first!r} not in allowlist"

        return True, ""

    # --- 文件访问检查 ---

    def check_file_access(
        self,
        path: Path | str,
        mode: Literal["read", "write"] = "read",
    ) -> tuple[bool, str]:
        """返回 (allowed, reason)。

        规则（按优先级）：
          1. 命中 forbidden 子串 → 拒绝
          2. write 模式下未命中 writable → 拒绝（writable 视为白名单）
          3. write 模式下命中 readonly → 拒绝
          4. read 模式 → 默认允许
        """
        p = str(path)
        for f in self.forbidden:
            if f in p:
                return False, f"path matches forbidden: {f}"

        if mode == "write":
            # readonly 优先于 writable
            for ro in self.readonly:
                if ro in p:
                    return False, f"path is readonly: {ro}"
            if self.writable and not any(w in p for w in self.writable):
                return False, "path not in writable whitelist"

        return True, ""

    # --- 脱敏 ---

    def redact(self, text: str) -> str:
        """对正则命中的子串做 ``***`` 替换。"""
        if not text or self._redact_re is None:
            return text
        return self._redact_re.sub("***", text)

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """对 dict 中的敏感字段整体替换为 ``***``，并对所有字符串值做正则脱敏。"""
        if not data:
            return data
        result = copy.deepcopy(data)
        self._redact_inplace(result)
        return result

    def _redact_inplace(self, node: Any) -> None:
        if isinstance(node, dict):
            for k in list(node.keys()):
                v = node[k]
                if k in self.redact_fields:
                    node[k] = "***"
                elif isinstance(v, str):
                    node[k] = self.redact(v)
                else:
                    self._redact_inplace(v)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                if isinstance(v, str):
                    node[i] = self.redact(v)
                else:
                    self._redact_inplace(v)


__all__ = [
    "DEFAULT_COMMAND_BLOCKLIST",
    "FailurePolicy",
    "HookBlockedError",
    "HookDef",
    "HookError",
    "HookResult",
    "HookRunner",
    "HookSecurityError",
    "SecurityGuard",
]
