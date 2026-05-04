"""测试 builtin_roles 的 M2 默认值（T2.4）。"""

from __future__ import annotations

from ai_rd_team.roles.prompt import builtin_roles


class TestBuiltinRoleDefaults:
    def test_all_seven_roles_present(self) -> None:
        roles = builtin_roles()
        assert set(roles.keys()) == {
            "pm",
            "analyst",
            "architect",
            "developer",
            "reviewer",
            "tester",
            "devops",
        }

    def test_developer_has_default_skills(self) -> None:
        dev = builtin_roles()["developer"]
        assert "python-best-practices" in dev.skills
        assert "pytest-guide" in dev.skills

    def test_reviewer_has_review_checklist(self) -> None:
        rev = builtin_roles()["reviewer"]
        assert "code-review-checklist" in rev.skills

    def test_tester_has_pytest_guide(self) -> None:
        t = builtin_roles()["tester"]
        assert "pytest-guide" in t.skills

    def test_architect_has_memory_scope(self) -> None:
        arch = builtin_roles()["architect"]
        agent_d = arch.memory_scope.get("agent_d") or []
        assert "tech-stack-selected" in agent_d
        assert "interface-contracts" in agent_d

    def test_developer_has_memory_scope(self) -> None:
        dev = builtin_roles()["developer"]
        agent_d = dev.memory_scope.get("agent_d") or []
        assert "tech-stack-selected" in agent_d

    def test_scalable_flags(self) -> None:
        roles = builtin_roles()
        assert roles["developer"].scalable
        assert roles["reviewer"].scalable
        assert roles["tester"].scalable
        assert not roles["pm"].scalable
        assert not roles["analyst"].scalable
        assert not roles["architect"].scalable
        assert not roles["devops"].scalable

    def test_personas_non_empty(self) -> None:
        for role in builtin_roles().values():
            assert role.persona, f"{role.name} should have persona"
            assert role.display_name, f"{role.name} should have display_name"
