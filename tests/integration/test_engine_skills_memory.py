"""Engine 集成 Skills + Memory 的测试（T2.1 + T2.2）。"""

from __future__ import annotations

from pathlib import Path

import yaml

from ai_rd_team.adapter.bridge import InMemoryBridge
from ai_rd_team.config.models import Role
from ai_rd_team.engine.manager import TeamEnvironmentManager


def _write_basic_config(ws: Path, mode: str = "lite") -> None:
    d = ws / ".ai-rd-team"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "config_version": "1.0",
                "run_mode": mode,
                "project": {"description": "测试项目"},
                "budget": {"per_run": 120, "per_day": 500},
            }
        ),
        encoding="utf-8",
    )


class TestSkillsInjection:
    def test_engine_uses_builtin_skills(self, tmp_workspace: Path) -> None:
        """当角色 skills 引用了 builtin skills 时，prompt 应包含其内容。"""
        _write_basic_config(tmp_workspace, mode="lite")
        bridge = InMemoryBridge()
        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
        engine.initialize(allow_onboarding=False, interactive=False)

        # 临时覆盖 resolve_role：让 developer 带 skills
        original_resolve = engine._resolve_role

        def _resolve(role_name: str) -> Role:
            r = original_resolve(role_name)
            if role_name == "developer":
                return Role(
                    name=r.name,
                    display_name=r.display_name,
                    persona=r.persona,
                    scalable=r.scalable,
                    default_instances=r.default_instances,
                    skills=("python-best-practices", "pytest-guide"),
                )
            return r

        engine._resolve_role = _resolve  # type: ignore[method-assign]
        engine.start_run("test")

        # 从 bridge 的 task 调用中取 prompt
        task_calls = [c for c in bridge.calls if c["op"] == "task"]
        assert task_calls
        prompt = task_calls[0]["prompt"]
        assert "Python Best Practices" in prompt
        assert "Pytest Guide" in prompt

    def test_missing_skill_does_not_crash(self, tmp_workspace: Path) -> None:
        """引用不存在的 skill 不应让 spawn 失败（missing_ok=True）。"""
        _write_basic_config(tmp_workspace, mode="lite")
        bridge = InMemoryBridge()
        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
        engine.initialize(allow_onboarding=False, interactive=False)

        original_resolve = engine._resolve_role

        def _resolve(role_name: str) -> Role:
            r = original_resolve(role_name)
            if role_name == "developer":
                return Role(
                    name=r.name,
                    display_name=r.display_name,
                    skills=("does-not-exist", "python-best-practices"),
                )
            return r

        engine._resolve_role = _resolve  # type: ignore[method-assign]
        engine.start_run("test")

        # 应成功 spawn
        assert any(c["op"] == "task" for c in bridge.calls)


class TestMemoryInjection:
    def test_agent_d_loaded_into_prompt(self, tmp_workspace: Path) -> None:
        """成员 memory_scope.agent_d 里引用的文件应被注入 prompt。"""
        _write_basic_config(tmp_workspace, mode="lite")

        # 提前准备一个 agent.d 文件
        agent_d = tmp_workspace / ".ai-rd-team" / "memory" / "agent.d"
        agent_d.mkdir(parents=True, exist_ok=True)
        (agent_d / "team-roster.md").write_text(
            "---\ntype: memory\nlayer: agent.d\nauthor: auto\n"
            "created: 2026-05-04\nupdated: 2026-05-04\n"
            "estimated_tokens: 50\n---\n\n"
            "# 团队成员清单\n\n- 陈架构\n- 林1号\n",
            encoding="utf-8",
        )

        bridge = InMemoryBridge()
        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=bridge)
        engine.initialize(allow_onboarding=False, interactive=False)

        original_resolve = engine._resolve_role

        def _resolve(role_name: str) -> Role:
            r = original_resolve(role_name)
            if role_name == "developer":
                return Role(
                    name=r.name,
                    display_name=r.display_name,
                    memory_scope={"agent_d": ["team-roster"]},
                )
            return r

        engine._resolve_role = _resolve  # type: ignore[method-assign]
        engine.start_run("test")

        task_calls = [c for c in bridge.calls if c["op"] == "task"]
        assert task_calls
        prompt = task_calls[0]["prompt"]
        assert "团队成员清单" in prompt
        assert "陈架构" in prompt

    def test_memory_dir_created_on_initialize(self, tmp_workspace: Path) -> None:
        """initialize 后 memory/ 三层目录应自动创建。"""
        _write_basic_config(tmp_workspace, mode="lite")
        engine = TeamEnvironmentManager(workspace=tmp_workspace, bridge=InMemoryBridge())
        engine.initialize(allow_onboarding=False, interactive=False)

        memory = tmp_workspace / ".ai-rd-team" / "memory"
        assert (memory / "agent.d").is_dir()
        assert (memory / "memory.d").is_dir()
        assert (memory / "decisions").is_dir()
