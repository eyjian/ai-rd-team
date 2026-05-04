"""Engine + HookRunner 集成测试（T2.11）。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from ai_rd_team.adapter.bridge import InMemoryBridge
from ai_rd_team.engine.manager import TeamEnvironmentManager


def _write_config_with_hooks(ws: Path, hooks: dict | None = None) -> None:
    d = ws / ".ai-rd-team"
    d.mkdir(parents=True, exist_ok=True)
    data = {
        "config_version": "1.0",
        "run_mode": "lite",
        "project": {"description": "Hook 集成测试"},
        "budget": {"per_run": 120, "per_day": 500},
    }
    if hooks is not None:
        data["hooks"] = hooks
    (d / "config.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")

    # 同时写一份 advanced 层，因为 hooks 是 Advanced 字段
    if hooks is not None:
        (d / "config.advanced.yaml").write_text(
            yaml.safe_dump({"hooks": hooks}, allow_unicode=True),
            encoding="utf-8",
        )


class TestEngineHookIntegration:
    def test_run_started_hook_triggered(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        marker = tmp_workspace / "hook-fired.txt"
        hooks = {
            "enabled": True,
            "builtin": {"events_emitter": False},
            "custom": [
                {
                    "name": "write-marker",
                    "trigger": "run_started",
                    "command": f"echo fired > {marker}",
                }
            ],
        }
        _write_config_with_hooks(tmp_workspace, hooks)

        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")

        assert marker.is_file()
        assert "fired" in marker.read_text()

    def test_run_stopped_hook_triggered(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        marker = tmp_workspace / "stop-hook.txt"
        hooks = {
            "enabled": True,
            "builtin": {"events_emitter": False},
            "custom": [
                {
                    "name": "stop-marker",
                    "trigger": "run_stopped",
                    "command": f"echo $REASON > {marker}",
                }
            ],
        }
        _write_config_with_hooks(tmp_workspace, hooks)

        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")
        engine.stop_run(reason="finished")

        assert marker.is_file()
        content = marker.read_text().strip()
        assert content == "finished"

    def test_hooks_log_jsonl_written(self, tmp_workspace: Path, tmp_quota_home: Path) -> None:
        hooks = {
            "enabled": True,
            "builtin": {"events_emitter": False},
            "custom": [
                {
                    "name": "log-test",
                    "trigger": "run_started",
                    "command": "true",
                }
            ],
        }
        _write_config_with_hooks(tmp_workspace, hooks)

        engine = TeamEnvironmentManager(
            workspace=tmp_workspace,
            bridge=InMemoryBridge(),
            quota_home_dir=tmp_quota_home,
        )
        engine.initialize(allow_onboarding=False, interactive=False)
        engine.start_run("test")
        engine.stop_run(reason="done")

        log = tmp_workspace / ".ai-rd-team" / "runtime" / "logs" / "hooks.jsonl"
        assert log.is_file()
        entries = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
        assert any(e["hook"] == "log-test" for e in entries)
