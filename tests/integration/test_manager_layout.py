"""TeamEnvironmentManager 的 ProjectLayout 加载（M7 任务 3.2）。

验证优先级：architect yaml > config.artifacts.layout > memory 推断 > fallback。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai_rd_team.artifacts.layout import DEFAULT_LAYOUTS
from ai_rd_team.engine.manager import TeamEnvironmentManager


def _write_basic_config(ws: Path, advanced_extra: dict | None = None) -> None:
    d = ws / ".ai-rd-team"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "config_version": "1.0",
                "run_mode": "lite",
                "project": {"description": "M7 layout test"},
                "budget": {"per_run": 120, "per_day": 500},
            }
        ),
        encoding="utf-8",
    )
    advanced: dict = {
        "config_version": "1.0",
        "adapter": {"bridge_timeout_seconds": 5},
    }
    if advanced_extra:
        advanced.update(advanced_extra)
    (d / "config.advanced.yaml").write_text(yaml.safe_dump(advanced), encoding="utf-8")


@pytest.fixture
def minimal_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    _write_basic_config(ws)
    return ws


class TestLayoutResolution:
    def test_fallback_when_no_hints(
        self, minimal_workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """无 yaml、无 config 覆盖、无 tech-stack memory → fallback。"""
        from tests.integration.test_manager_auto_responder import FakeAdapter

        fake = FakeAdapter(config={})
        engine = TeamEnvironmentManager(workspace=minimal_workspace, adapter=fake)
        engine.initialize(allow_onboarding=False, interactive=False)

        assert engine._artifact_recorder is not None
        assert engine._artifact_recorder.layout is DEFAULT_LAYOUTS["fallback"]

    def test_yaml_wins_over_memory(self, minimal_workspace: Path) -> None:
        """架构师声明的 data-project-layout.yaml 优先级最高。"""
        runtime = minimal_workspace / ".ai-rd-team" / "runtime"
        reports = runtime / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        (reports / "data-project-layout.yaml").write_text(
            yaml.safe_dump(
                {
                    "version": "1.0",
                    "base": "go",
                    "overrides": {
                        "code_dirs": {"mysh": "mysh"},
                        "tests_mode": "alongside",
                    },
                }
            ),
            encoding="utf-8",
        )

        # 同时写一个 memory 提示（应被覆盖）
        memory_agent = minimal_workspace / ".ai-rd-team" / "memory" / "agent.d"
        memory_agent.mkdir(parents=True, exist_ok=True)
        (memory_agent / "tech-stack-selected.md").write_text(
            "# Stack\nPython 3.11", encoding="utf-8"
        )

        from tests.integration.test_manager_auto_responder import FakeAdapter

        fake = FakeAdapter(config={})
        engine = TeamEnvironmentManager(workspace=minimal_workspace, adapter=fake)
        engine.initialize(allow_onboarding=False, interactive=False)

        layout = engine._artifact_recorder.layout
        assert layout.tests_mode == "alongside"
        assert layout.code_dirs == {"mysh": "mysh"}
        # base=go 继承
        assert layout.tests_root is None

    def test_memory_inference_when_no_yaml(self, minimal_workspace: Path) -> None:
        """无 yaml 时通过 memory 里的 tech-stack-selected 推断。"""
        memory_agent = minimal_workspace / ".ai-rd-team" / "memory" / "agent.d"
        memory_agent.mkdir(parents=True, exist_ok=True)
        (memory_agent / "tech-stack-selected.md").write_text(
            "# Tech\nUsing Go + Kratos", encoding="utf-8"
        )

        from tests.integration.test_manager_auto_responder import FakeAdapter

        fake = FakeAdapter(config={})
        engine = TeamEnvironmentManager(workspace=minimal_workspace, adapter=fake)
        engine.initialize(allow_onboarding=False, interactive=False)

        assert engine._artifact_recorder.layout == DEFAULT_LAYOUTS["go"]

    def test_event_logged(self, minimal_workspace: Path) -> None:
        """layout 解析结果应追加到 events.jsonl 便于调试。"""
        from tests.integration.test_manager_auto_responder import FakeAdapter

        fake = FakeAdapter(config={})
        engine = TeamEnvironmentManager(workspace=minimal_workspace, adapter=fake)
        engine.initialize(allow_onboarding=False, interactive=False)

        events_file = minimal_workspace / ".ai-rd-team" / "runtime" / "events.jsonl"
        assert events_file.is_file()
        lines = events_file.read_text(encoding="utf-8").splitlines()
        import json

        layout_events = [
            json.loads(line) for line in lines if line.strip() and "project_layout_resolved" in line
        ]
        assert len(layout_events) >= 1
        assert layout_events[-1]["source"] in ("yaml", "config", "memory", "fallback")
