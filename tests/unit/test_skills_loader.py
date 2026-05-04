"""测试 SkillsLoader（T2.1）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_rd_team.config.models import Role
from ai_rd_team.roles.skills_loader import (
    LoadedSkill,
    SkillNotFoundError,
    SkillReferenceError,
    SkillsLoader,
    default_builtin_dir,
)


def _write_skill(base: Path, name: str, content: str = "# skill") -> Path:
    base.mkdir(parents=True, exist_ok=True)
    p = base / f"{name}.md"
    p.write_text(content, encoding="utf-8")
    return p


class TestRefParsing:
    def test_scoped_ref(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        scope, name = loader._parse_ref("builtin:python-best-practices")
        assert scope == "builtin"
        assert name == "python-best-practices"

    def test_bare_ref(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        scope, name = loader._parse_ref("pytest-guide")
        assert scope is None
        assert name == "pytest-guide"

    def test_invalid_scope_raises(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        with pytest.raises(SkillReferenceError):
            loader._parse_ref("typo:foo")

    def test_empty_name_raises(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        with pytest.raises(SkillReferenceError):
            loader._parse_ref("builtin:")

    def test_empty_ref_raises(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        with pytest.raises(SkillReferenceError):
            loader._parse_ref("")


class TestLoad:
    def test_load_builtin_only(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        _write_skill(tmp_path / "b", "foo", content="# Foo\n\nbar")

        skill = loader.load("foo")
        assert isinstance(skill, LoadedSkill)
        assert skill.scope == "builtin"
        assert skill.name == "foo"
        assert skill.content.startswith("# Foo")
        assert skill.estimated_tokens > 0

    def test_workspace_overrides_global_overrides_builtin(
        self, tmp_path: Path
    ) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        _write_skill(tmp_path / "b", "shared", content="builtin-content")
        _write_skill(tmp_path / "g", "shared", content="global-content")
        _write_skill(tmp_path / "w", "shared", content="workspace-content")

        skill = loader.load("shared")
        assert skill.scope == "workspace"
        assert skill.content == "workspace-content"

    def test_global_fallback_when_workspace_missing(
        self, tmp_path: Path
    ) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        _write_skill(tmp_path / "g", "personal-style", "g")

        skill = loader.load("personal-style")
        assert skill.scope == "global"

    def test_forced_scope_ignores_priority(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        _write_skill(tmp_path / "b", "x", "builtin-only")
        _write_skill(tmp_path / "w", "x", "workspace-version")

        # 强制 builtin：不走优先级
        skill = loader.load("builtin:x")
        assert skill.scope == "builtin"
        assert skill.content == "builtin-only"

    def test_not_found_raises(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        with pytest.raises(SkillNotFoundError):
            loader.load("missing")


class TestBatchLoad:
    def test_load_many_missing_ok(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        _write_skill(tmp_path / "b", "a")
        _write_skill(tmp_path / "b", "c")

        got = loader.load_many(["a", "missing", "c"], missing_ok=True)
        assert [s.name for s in got] == ["a", "c"]

    def test_load_many_strict_raises(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        _write_skill(tmp_path / "b", "a")

        with pytest.raises(SkillNotFoundError):
            loader.load_many(["a", "missing"], missing_ok=False)

    def test_load_for_role(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        _write_skill(tmp_path / "b", "python-best-practices", content="pbp")
        _write_skill(tmp_path / "b", "pytest-guide", content="pg")

        role = Role(
            name="developer",
            skills=("python-best-practices", "pytest-guide"),
        )
        got = loader.load_for_role(role)
        assert {s.name for s in got} == {"python-best-practices", "pytest-guide"}


class TestListAvailable:
    def test_list_empty_dirs(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        got = loader.list_available()
        assert got == {"builtin": [], "global": [], "workspace": []}

    def test_list_with_files(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        _write_skill(tmp_path / "b", "z")
        _write_skill(tmp_path / "b", "a")
        _write_skill(tmp_path / "w", "project-rules")

        got = loader.list_available()
        assert got["builtin"] == ["a", "z"]  # 已排序
        assert got["workspace"] == ["project-rules"]
        assert got["global"] == []


class TestBuiltinSkills:
    """验证包内 builtin skills 可以加载（M2 自带 3 个）。"""

    def test_builtin_dir_has_files(self) -> None:
        d = default_builtin_dir()
        assert d.is_dir()
        files = sorted(p.stem for p in d.glob("*.md"))
        assert "python-best-practices" in files
        assert "code-review-checklist" in files
        assert "pytest-guide" in files

    def test_load_builtin_python_best_practices(self, tmp_path: Path) -> None:
        loader = SkillsLoader.create_default(workspace=tmp_path / ".ai-rd-team")
        skill = loader.load("python-best-practices")
        assert skill.scope == "builtin"
        assert "Python Best Practices" in skill.content
