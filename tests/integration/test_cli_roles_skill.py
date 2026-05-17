"""``ai-rd-team roles-skill list / show`` 子命令集成测试。

对应 CLI：``src/ai_rd_team/cli/main.py`` 中的 ``roles_skill_app``。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_rd_team.cli.main import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# =====================================================================
# roles-skill list
# =====================================================================


class TestRolesSkillList:
    """``ai-rd-team roles-skill list`` 行为测试。"""

    def test_list_all_layers_default(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        """无参数时输出三层标题与 builtin 内容。"""
        result = runner.invoke(app, ["roles-skill", "list", "-w", str(tmp_workspace)])
        assert result.exit_code == 0
        # 三层标题都应出现（emoji 可能被 rich 折行，只检查关键字）
        assert "Builtin" in result.stdout
        assert "Global" in result.stdout
        assert "Workspace" in result.stdout
        # builtin 中至少有这两个 skill
        assert "code-review-checklist" in result.stdout
        assert "python-best-practices" in result.stdout

    def test_list_shows_default_for_tag(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        """default_for 不为空的 skill 应展示 ``默认装配:`` 标签。"""
        result = runner.invoke(app, ["roles-skill", "list", "-w", str(tmp_workspace)])
        assert result.exit_code == 0
        assert "默认装配" in result.stdout
        # python-best-practices 默认装配 developer + reviewer
        assert "developer" in result.stdout
        assert "reviewer" in result.stdout

    def test_list_scope_builtin_filters(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        """``--scope builtin`` 只输出 builtin 层。"""
        result = runner.invoke(
            app,
            ["roles-skill", "list", "--scope", "builtin", "-w", str(tmp_workspace)],
        )
        assert result.exit_code == 0
        assert "Builtin" in result.stdout
        assert "Global" not in result.stdout
        assert "Workspace" not in result.stdout

    def test_list_invalid_scope_exits_2(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        """非法 ``--scope`` 必须以 exit code 2（用法错误）失败。"""
        result = runner.invoke(
            app,
            ["roles-skill", "list", "--scope", "foo", "-w", str(tmp_workspace)],
        )
        assert result.exit_code == 2
        assert "无效的 scope" in result.stdout or "无效" in result.stdout

    def test_list_json_output_parses(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        """``--json`` 输出必须是合法 JSON，且结构稳定。"""
        result = runner.invoke(app, ["roles-skill", "list", "--json", "-w", str(tmp_workspace)])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert set(data.keys()) == {"builtin", "global", "workspace"}

        builtin_names = {row["name"] for row in data["builtin"]}
        assert "code-review-checklist" in builtin_names
        assert "python-best-practices" in builtin_names

        # 抽一行做字段断言
        py = next(r for r in data["builtin"] if r["name"] == "python-best-practices")
        assert py["scope"] == "builtin"
        assert isinstance(py["default_for"], list)
        assert "developer" in py["default_for"]
        assert isinstance(py["estimated_tokens"], int) and py["estimated_tokens"] > 0
        assert py["path"].endswith("python-best-practices.md")

    def test_list_json_with_scope_only_returns_that_layer(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        """``--json --scope builtin`` 时其它层不在 JSON 顶层 key 中。"""
        result = runner.invoke(
            app,
            [
                "roles-skill",
                "list",
                "--json",
                "--scope",
                "builtin",
                "-w",
                str(tmp_workspace),
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "builtin" in data
        assert "global" not in data
        assert "workspace" not in data


# =====================================================================
# roles-skill show
# =====================================================================


class TestRolesSkillShow:
    """``ai-rd-team roles-skill show`` 行为测试。"""

    def test_show_existing_skill_zero_exit(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["roles-skill", "show", "pytest-guide", "-w", str(tmp_workspace)],
        )
        assert result.exit_code == 0
        assert "pytest-guide" in result.stdout
        assert "builtin" in result.stdout

    def test_show_with_scope_prefix(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        """``builtin:xxx`` 形式的强制 scope 引用应正确解析。"""
        result = runner.invoke(
            app,
            [
                "roles-skill",
                "show",
                "builtin:pytest-guide",
                "-w",
                str(tmp_workspace),
            ],
        )
        assert result.exit_code == 0
        assert "pytest-guide" in result.stdout

    def test_show_not_found_exits_1(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        """找不到的 skill 应以 exit code 1 失败（区别于用法错误的 2）。"""
        result = runner.invoke(
            app,
            ["roles-skill", "show", "no-such-skill", "-w", str(tmp_workspace)],
        )
        assert result.exit_code == 1
        assert "未找到" in result.stdout

    def test_show_invalid_scope_exits_2(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        """非法 scope 前缀（如 ``foo:xxx``）属于用法错误，exit=2。"""
        result = runner.invoke(
            app,
            [
                "roles-skill",
                "show",
                "foo:python-best-practices",
                "-w",
                str(tmp_workspace),
            ],
        )
        assert result.exit_code == 2
        assert "引用语法错误" in result.stdout or "invalid scope" in result.stdout

    def test_show_with_content_includes_body(
        self,
        runner: CliRunner,
        tmp_workspace: Path,
    ) -> None:
        """``--content`` 应附带正文。"""
        result = runner.invoke(
            app,
            [
                "roles-skill",
                "show",
                "code-review-checklist",
                "--content",
                "-w",
                str(tmp_workspace),
            ],
        )
        assert result.exit_code == 0
        # 正文应包含 markdown 标题 / 评审相关关键字
        assert "正文" in result.stdout
        # code-review-checklist 正文里必然出现的稳定词（不依赖具体格式）
        assert "评审" in result.stdout or "review" in result.stdout.lower()
