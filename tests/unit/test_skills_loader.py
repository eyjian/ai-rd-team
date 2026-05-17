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

    def test_workspace_overrides_global_overrides_builtin(self, tmp_path: Path) -> None:
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

    def test_global_fallback_when_workspace_missing(self, tmp_path: Path) -> None:
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


# ---------------------------------------------------------------------------
# Frontmatter 解析（T2.1 增强）
# ---------------------------------------------------------------------------


class TestFrontmatter:
    """覆盖 YAML frontmatter 的解析、剥离、容错与便利属性。"""

    def test_with_frontmatter_strips_block_and_exposes_metadata(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        content = (
            "---\n"
            "name: my-skill\n"
            "description: A test skill.\n"
            "default_for: [developer, reviewer]\n"
            "---\n"
            "\n"
            "# Body Heading\n"
            "\n"
            "Body content.\n"
        )
        _write_skill(tmp_path / "b", "my-skill", content=content)

        skill = loader.load("my-skill")

        # frontmatter 已被剥离
        assert not skill.content.lstrip().startswith("---")
        assert skill.content.startswith("# Body Heading")
        assert "Body content." in skill.content

        # metadata 正确暴露
        assert skill.metadata is not None
        assert skill.metadata.get("name") == "my-skill"
        assert skill.metadata.get("description") == "A test skill."
        assert skill.metadata.get("default_for") == ["developer", "reviewer"]

        # 便利属性
        assert skill.description == "A test skill."
        assert skill.default_for == ("developer", "reviewer")

    def test_estimated_tokens_excludes_frontmatter(self, tmp_path: Path) -> None:
        """token 估算只基于正文，不应包含 frontmatter 字符。"""
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        body = "# Title\n\n" + "x" * 400  # 大约 ~100 tokens
        with_fm = (
            "---\n"
            "name: t\n"
            "description: " + "y" * 400 + "\n"  # 故意写很长
            "---\n\n" + body
        )
        without_fm = body

        _write_skill(tmp_path / "b", "with", content=with_fm)
        _write_skill(tmp_path / "b", "without", content=without_fm)

        s1 = loader.load("with")
        s2 = loader.load("without")
        assert s1.estimated_tokens == s2.estimated_tokens, "frontmatter 不应进入 token 估算"

    def test_metadata_is_readonly_mapping(self, tmp_path: Path) -> None:
        """metadata 应该是只读的（MappingProxyType），防止下游误改。"""
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        _write_skill(
            tmp_path / "b",
            "ro",
            content="---\nname: ro\n---\n\nbody\n",
        )
        skill = loader.load("ro")
        assert skill.metadata is not None
        with pytest.raises(TypeError):
            skill.metadata["name"] = "hacked"  # type: ignore[index]

    def test_malformed_yaml_falls_back_to_none_metadata(self, tmp_path: Path) -> None:
        """frontmatter 里 YAML 坏掉时：仍剥离 ``---`` 块、metadata=None。"""
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        bad = (
            "---\n"
            "name: x\n"
            "default_for: [unclosed\n"  # 故意 YAML 坏
            "---\n"
            "\n"
            "# Body\n"
        )
        _write_skill(tmp_path / "b", "bad", content=bad)

        skill = loader.load("bad")
        # 关键：``---`` 块必须被剥离（否则会污染 prompt）
        assert not skill.content.lstrip().startswith("---")
        assert skill.content.startswith("# Body")
        # metadata 容错为 None
        assert skill.metadata is None
        assert skill.description is None
        assert skill.default_for == ()

    def test_frontmatter_top_level_not_dict_falls_back(self, tmp_path: Path) -> None:
        """frontmatter YAML 顶层不是 mapping（比如纯列表）时同样按容错处理。"""
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        bad = "---\n- item1\n- item2\n---\n\n# Body\n"
        _write_skill(tmp_path / "b", "list-fm", content=bad)

        skill = loader.load("list-fm")
        assert skill.metadata is None
        assert skill.content.startswith("# Body")

    def test_default_for_non_list_value_returns_empty_tuple(self, tmp_path: Path) -> None:
        """``default_for`` 字段写成字符串时不应炸，而是退化为空元组。"""
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        content = (
            "---\n"
            "name: weird\n"
            'default_for: "developer"\n'  # 不是列表
            "---\n\n# Body\n"
        )
        _write_skill(tmp_path / "b", "weird", content=content)
        skill = loader.load("weird")
        assert skill.metadata is not None
        assert skill.default_for == ()

    def test_only_dashes_no_yaml_body(self, tmp_path: Path) -> None:
        """空 frontmatter ``---\\n---``：剥离块、metadata=None。"""
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        _write_skill(tmp_path / "b", "empty-fm", content="---\n---\n# Body\n")
        skill = loader.load("empty-fm")
        assert skill.metadata is None
        assert skill.content.startswith("# Body")


# ---------------------------------------------------------------------------
# 向后兼容（无 frontmatter 的旧文件）
# ---------------------------------------------------------------------------


class TestBackwardCompat:
    def test_no_frontmatter_keeps_full_content(self, tmp_path: Path) -> None:
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        content = "# Plain Skill\n\nNo frontmatter here.\n"
        _write_skill(tmp_path / "b", "plain", content=content)

        skill = loader.load("plain")
        assert skill.content == content
        assert skill.metadata is None
        assert skill.description is None
        assert skill.default_for == ()

    def test_dashes_in_middle_of_file_not_treated_as_frontmatter(self, tmp_path: Path) -> None:
        """正文里的 ``---``（horizontal rule）不应被误当作 frontmatter。"""
        loader = SkillsLoader(
            builtin_dir=tmp_path / "b",
            global_dir=tmp_path / "g",
            workspace_dir=tmp_path / "w",
        )
        content = "# Title\n\nIntro.\n\n---\n\nMore content.\n"
        _write_skill(tmp_path / "b", "hr", content=content)

        skill = loader.load("hr")
        assert skill.metadata is None
        assert skill.content == content


# ---------------------------------------------------------------------------
# 守门测试：builtin skill 的 default_for 与 _DEFAULT_ROLE_SKILLS 双向一致
# ---------------------------------------------------------------------------


class TestDefaultForConsistency:
    """frontmatter 的 ``default_for`` 必须与 ``_DEFAULT_ROLE_SKILLS`` 双向镜像。

    这是一个守门测试：以后任何一方漂移都会被立即抓到。
    """

    def test_default_for_mirrors_default_role_skills(self, tmp_path: Path) -> None:
        # 延迟导入以避免在 prompt 模块未就绪时影响 collect
        from ai_rd_team.roles.prompt import _DEFAULT_ROLE_SKILLS

        loader = SkillsLoader.create_default(workspace=tmp_path / ".ai-rd-team")
        builtin_names = loader.list_available()["builtin"]
        assert builtin_names, "expected at least one builtin skill"

        # 1) 正向：frontmatter.default_for 里每个角色，确实把该 skill 装在了清单里
        for name in builtin_names:
            skill = loader.load(f"builtin:{name}")
            for role in skill.default_for:
                assert role in _DEFAULT_ROLE_SKILLS, (
                    f"builtin skill {name!r} 在 frontmatter 里声明 default_for "
                    f"包含未知角色 {role!r}"
                )
                assert name in _DEFAULT_ROLE_SKILLS[role], (
                    f"builtin skill {name!r} 的 frontmatter 声明 default_for "
                    f"包含 {role!r}，但 _DEFAULT_ROLE_SKILLS[{role!r}]="
                    f"{_DEFAULT_ROLE_SKILLS[role]!r} 里并没有它"
                )

        # 2) 反向：_DEFAULT_ROLE_SKILLS 里每个 builtin skill，frontmatter 都得列出该角色
        for role, refs in _DEFAULT_ROLE_SKILLS.items():
            for ref in refs:
                # 只校验确实存在于 builtin 层的（用户可能引用 workspace skill）
                if ref not in builtin_names:
                    continue
                skill = loader.load(f"builtin:{ref}")
                assert role in skill.default_for, (
                    f"_DEFAULT_ROLE_SKILLS[{role!r}] 包含 builtin skill {ref!r}，"
                    f"但该 skill 的 frontmatter default_for={skill.default_for!r} "
                    f"里没有 {role!r}"
                )

    def test_every_builtin_has_frontmatter(self, tmp_path: Path) -> None:
        """builtin 层的所有 skill 都必须带规范的 frontmatter。"""
        loader = SkillsLoader.create_default(workspace=tmp_path / ".ai-rd-team")
        for name in loader.list_available()["builtin"]:
            skill = loader.load(f"builtin:{name}")
            assert skill.metadata is not None, f"builtin skill {name!r} 缺少 YAML frontmatter"
            assert skill.metadata.get("name") == name, (
                f"builtin skill {name!r} 的 frontmatter.name="
                f"{skill.metadata.get('name')!r}，与文件名不一致"
            )
            assert isinstance(skill.description, str) and skill.description, (
                f"builtin skill {name!r} 缺少 description"
            )
