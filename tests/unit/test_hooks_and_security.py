"""测试 HookRunner + SecurityGuard（T2.11 + T2.12 + T2.13）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_rd_team.hooks.runner import (
    HookBlockedError,
    HookRunner,
    HookSecurityError,
    SecurityGuard,
    _expand_placeholders,
)


@pytest.fixture
def runner(tmp_workspace: Path) -> HookRunner:
    return HookRunner(
        hooks_config={"enabled": True, "builtin": {}},
        workspace=tmp_workspace,
        events_file=tmp_workspace / "events.jsonl",
        hooks_log_file=tmp_workspace / "logs" / "hooks.jsonl",
    )


class TestDefaultBuiltin:
    def test_events_emitter_enabled_by_default(self, tmp_workspace: Path) -> None:
        r = HookRunner(
            hooks_config={"enabled": True},
            workspace=tmp_workspace,
            events_file=tmp_workspace / "e.jsonl",
        )
        # events_emitter 默认开
        assert any(h.name == "events_emitter" for h in r.registered_for("*"))

    def test_trigger_emits_event_to_file(self, tmp_workspace: Path) -> None:
        events_file = tmp_workspace / "events.jsonl"
        r = HookRunner(
            hooks_config={"enabled": True},
            workspace=tmp_workspace,
            events_file=events_file,
        )
        # 需要把触发点也注册到 events_emitter 的 `*` 路径。当前实现是 trigger 精确匹配，
        # 所以 events_emitter 只在 trigger="*" 时被调用。这个设计里 `*` 是占位符，
        # 实际事件记录由 RuntimeStateManager 负责。这里只验证 builtin 存在性。
        # 直接通过 callable 测试
        hook = r.registered_for("*")[0]
        hook.callable(trigger="custom_event", context={"run_id": "r1", "foo": "bar"})
        assert events_file.is_file()
        entries = [json.loads(ln) for ln in events_file.read_text().splitlines() if ln.strip()]
        assert entries[0]["event"] == "custom_event"
        assert entries[0]["run_id"] == "r1"


class TestCustomHookShellCommand:
    def test_simple_echo_hook(self, tmp_workspace: Path) -> None:
        cfg = {
            "enabled": True,
            "builtin": {"events_emitter": False},  # 关掉内置干扰
            "custom": [
                {
                    "name": "echo-run-id",
                    "trigger": "run_started",
                    "priority": 50,
                    "command": "echo $RUN_ID",
                    "timeout_seconds": 10,
                }
            ],
        }
        r = HookRunner(hooks_config=cfg, workspace=tmp_workspace)
        results = r.trigger("run_started", run_id="abc123")
        assert len(results) == 1
        assert results[0].exit_code == 0
        assert "abc123" in results[0].stdout

    def test_hook_failure_warn_does_not_raise(self, tmp_workspace: Path) -> None:
        cfg = {
            "enabled": True,
            "builtin": {"events_emitter": False},
            "custom": [
                {
                    "name": "fail-warn",
                    "trigger": "run_started",
                    "command": "exit 1",
                    "on_failure": "warn",
                }
            ],
        }
        r = HookRunner(hooks_config=cfg, workspace=tmp_workspace)
        results = r.trigger("run_started", run_id="x")
        assert len(results) == 1
        assert results[0].failed
        # 不抛异常

    def test_hook_failure_block_raises(self, tmp_workspace: Path) -> None:
        cfg = {
            "enabled": True,
            "builtin": {"events_emitter": False},
            "custom": [
                {
                    "name": "block-hook",
                    "trigger": "artifact_written",
                    "command": "exit 2",
                    "on_failure": "block",
                }
            ],
        }
        r = HookRunner(hooks_config=cfg, workspace=tmp_workspace)
        with pytest.raises(HookBlockedError):
            r.trigger("artifact_written", path="x.py")

    def test_priority_ordering(self, tmp_workspace: Path) -> None:
        cfg = {
            "enabled": True,
            "builtin": {"events_emitter": False},
            "custom": [
                {"name": "late", "trigger": "t", "priority": 100, "command": "true"},
                {"name": "early", "trigger": "t", "priority": 10, "command": "true"},
                {"name": "mid", "trigger": "t", "priority": 50, "command": "true"},
            ],
        }
        r = HookRunner(hooks_config=cfg, workspace=tmp_workspace)
        hooks = r.registered_for("t")
        assert [h.name for h in hooks] == ["early", "mid", "late"]

    def test_when_filter_skips(self, tmp_workspace: Path) -> None:
        cfg = {
            "enabled": True,
            "builtin": {"events_emitter": False},
            "custom": [
                {
                    "name": "only-deploy",
                    "trigger": "phase_complete",
                    "command": "echo deploying",
                    "when": {"phase": "deploy"},
                }
            ],
        }
        r = HookRunner(hooks_config=cfg, workspace=tmp_workspace)

        # phase=design 应被跳过
        results = r.trigger("phase_complete", phase="design")
        assert results[0].skipped

        # phase=deploy 应执行
        results = r.trigger("phase_complete", phase="deploy")
        assert not results[0].skipped
        assert results[0].exit_code == 0


class TestEnvVarInjection:
    def test_context_as_env_var(self, tmp_workspace: Path) -> None:
        cfg = {
            "enabled": True,
            "builtin": {"events_emitter": False},
            "custom": [
                {
                    "name": "echo-team",
                    "trigger": "team_created",
                    "command": "echo team=$TEAM_ID",
                }
            ],
        }
        r = HookRunner(hooks_config=cfg, workspace=tmp_workspace)
        results = r.trigger("team_created", team_id="my-team")
        assert "team=my-team" in results[0].stdout

    def test_placeholder_expansion(self, tmp_workspace: Path) -> None:
        cfg = {
            "enabled": True,
            "builtin": {"events_emitter": False},
            "custom": [
                {
                    "name": "echo-url",
                    "trigger": "run_stopped",
                    "command": "echo url=$WEBHOOK_URL run=$RUN_ID",
                    "env": {
                        "WEBHOOK_URL": "https://example.com/${RUN_ID}",
                    },
                }
            ],
        }
        r = HookRunner(hooks_config=cfg, workspace=tmp_workspace)
        results = r.trigger("run_stopped", run_id="abc")
        assert "url=https://example.com/abc" in results[0].stdout
        assert "run=abc" in results[0].stdout


class TestBlockHookSecurity:
    def test_block_hook_requires_whitelist(self, tmp_workspace: Path) -> None:
        """block Hook 的 command 若有白名单必须命中。"""
        cfg = {
            "enabled": True,
            "builtin": {"events_emitter": False},
            "security": {"hook_commands_whitelist": ["safe-script"]},
            "custom": [
                {
                    "name": "dangerous",
                    "trigger": "t",
                    "command": "rm -rf dangerous-path",
                    "on_failure": "block",
                }
            ],
        }
        with pytest.raises(HookSecurityError):
            HookRunner(hooks_config=cfg, workspace=tmp_workspace)

    def test_block_hook_passes_whitelist(self, tmp_workspace: Path) -> None:
        cfg = {
            "enabled": True,
            "builtin": {"events_emitter": False},
            "security": {"hook_commands_whitelist": ["echo"]},
            "custom": [
                {
                    "name": "safe-block",
                    "trigger": "t",
                    "command": "echo hello",
                    "on_failure": "block",
                }
            ],
        }
        r = HookRunner(hooks_config=cfg, workspace=tmp_workspace)
        results = r.trigger("t")
        assert not results[0].failed


class TestExpandPlaceholders:
    def test_basic(self) -> None:
        out = _expand_placeholders("prefix-${VAR}-suffix", {"VAR": "x"}, {})
        assert out == "prefix-x-suffix"

    def test_falls_back_to_os_env(self) -> None:
        out = _expand_placeholders("${X}", {}, {"X": "from-os"})
        assert out == "from-os"

    def test_missing_becomes_empty(self) -> None:
        out = _expand_placeholders("${MISSING}", {}, {})
        assert out == ""

    def test_no_placeholder_returns_as_is(self) -> None:
        assert _expand_placeholders("nothing", {}, {}) == "nothing"


class TestDisabled:
    def test_disabled_runner_no_op(self, tmp_workspace: Path) -> None:
        cfg = {
            "enabled": False,
            "custom": [
                {
                    "name": "never-runs",
                    "trigger": "t",
                    "command": "echo should-not-run",
                }
            ],
        }
        r = HookRunner(hooks_config=cfg, workspace=tmp_workspace)
        assert r.trigger("t") == []


# =================================================================
# SecurityGuard（T2.13）
# =================================================================


class TestSecurityCommandCheck:
    def test_default_blocklist_catches_rm_rf_root(self) -> None:
        g = SecurityGuard(config={})
        ok, reason = g.check_command("rm -rf /")
        assert not ok
        assert "rm -rf /" in reason

    def test_default_blocklist_catches_fork_bomb(self) -> None:
        g = SecurityGuard(config={})
        ok, _ = g.check_command(":(){ :|:& };:")
        assert not ok

    def test_custom_blocklist_appended(self) -> None:
        g = SecurityGuard(config={"commands": {"blocked": ["git push --force"]}})
        ok, _ = g.check_command("git push --force origin main")
        assert not ok
        # 默认黑名单仍生效
        ok2, _ = g.check_command("sudo rm something")
        assert not ok2

    def test_allowlist_restricts_commands(self) -> None:
        g = SecurityGuard(config={"commands": {"allowed": ["pytest", "ruff"]}})
        ok, _ = g.check_command("pytest -q")
        assert ok
        ok2, reason = g.check_command("npm run test")
        assert not ok2
        assert "allowlist" in reason

    def test_empty_command_rejected(self) -> None:
        g = SecurityGuard(config={})
        ok, _ = g.check_command("")
        assert not ok


class TestSecurityFileAccess:
    def test_forbidden_path_rejected(self) -> None:
        g = SecurityGuard(config={"file_access": {"forbidden": ["/etc/", ".ssh/"]}})
        ok, _ = g.check_file_access("/etc/passwd", mode="read")
        assert not ok
        ok2, _ = g.check_file_access("/home/me/.ssh/id_rsa")
        assert not ok2

    def test_writable_whitelist_enforced(self) -> None:
        g = SecurityGuard(config={"file_access": {"writable": ["/workspace/"]}})
        ok, _ = g.check_file_access("/workspace/x.py", mode="write")
        assert ok
        ok2, _ = g.check_file_access("/other/y.py", mode="write")
        assert not ok2

    def test_readonly_blocks_write(self) -> None:
        g = SecurityGuard(
            config={
                "file_access": {
                    "writable": ["/ws/"],
                    "readonly": ["/ws/.git/"],
                }
            }
        )
        ok, reason = g.check_file_access("/ws/.git/HEAD", mode="write")
        assert not ok
        assert "readonly" in reason

    def test_read_defaults_to_allowed(self) -> None:
        g = SecurityGuard(config={})
        ok, _ = g.check_file_access("/any/path", mode="read")
        assert ok


class TestSecurityRedact:
    def test_redact_pattern(self) -> None:
        g = SecurityGuard(config={"redact": {"patterns": [r"sk-\w+"]}})
        out = g.redact("api_key=sk-1234567890abc")
        assert "sk-" not in out
        assert "***" in out

    def test_redact_dict_fields(self) -> None:
        g = SecurityGuard(config={"redact": {"fields": ["password", "token"]}})
        data = {"user": "alice", "password": "hunter2", "token": "abc"}
        out = g.redact_dict(data)
        assert out["user"] == "alice"
        assert out["password"] == "***"
        assert out["token"] == "***"

    def test_redact_nested(self) -> None:
        g = SecurityGuard(
            config={
                "redact": {
                    "patterns": [r"sk-\w+"],
                    "fields": ["secret"],
                }
            }
        )
        data = {
            "config": {
                "secret": "hidden",
                "note": "your key is sk-test-123 please",
            },
            "items": ["normal", "also sk-foo"],
        }
        out = g.redact_dict(data)
        assert out["config"]["secret"] == "***"
        assert "***" in out["config"]["note"]
        assert "sk-" not in out["config"]["note"]
        assert "***" in out["items"][1]
