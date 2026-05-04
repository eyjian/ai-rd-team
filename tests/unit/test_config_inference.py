"""测试配置智能推断（T1.3）。"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from ai_rd_team.config.inference import ConfigInference, InferredConfig


class TestProjectInfo:
    """§2B.1 项目信息推断。"""

    def test_project_name_from_directory(self, tmp_workspace: Path) -> None:
        inf = ConfigInference()
        project = inf.infer_project_info(tmp_workspace)
        assert project["name"] == "workspace"
        assert project["workspace"] == tmp_workspace
        assert project["description"] == ""

    def test_project_name_strips_dot_prefix(self, tmp_path: Path) -> None:
        hidden = tmp_path / ".mycoolproject"
        hidden.mkdir()
        inf = ConfigInference()
        project = inf.infer_project_info(hidden)
        assert project["name"] == "mycoolproject"

    def test_description_from_readme_title(self, tmp_workspace: Path) -> None:
        (tmp_workspace / "README.md").write_text(
            "# 我的 CRM 系统\n\n这是描述。\n", encoding="utf-8"
        )
        inf = ConfigInference()
        project = inf.infer_project_info(tmp_workspace)
        assert project["description"] == "我的 CRM 系统"

    def test_description_empty_when_no_readme(self, tmp_workspace: Path) -> None:
        inf = ConfigInference()
        project = inf.infer_project_info(tmp_workspace)
        assert project["description"] == ""


class TestTechStack:
    """§2B.2 技术栈推断。"""

    def test_empty_project_all_false(self, tmp_workspace: Path) -> None:
        inf = ConfigInference()
        ts = inf.infer_tech_stack(tmp_workspace)
        prof = ts["proficiency"]
        assert prof["python"] is False
        assert prof["go"] is False
        assert prof["node"] is False
        assert prof["vue"] is False
        assert prof["react"] is False
        assert ts["preferences"]["backend"] is None

    def test_go_project_detected(self, tmp_workspace: Path) -> None:
        (tmp_workspace / "go.mod").write_text("module example.com/foo\n")
        inf = ConfigInference()
        ts = inf.infer_tech_stack(tmp_workspace)
        assert ts["proficiency"]["go"] is True
        assert ts["preferences"]["backend"] == "go"

    def test_python_pyproject_detected(self, tmp_workspace: Path) -> None:
        (tmp_workspace / "pyproject.toml").write_text("[project]\nname='x'\n")
        inf = ConfigInference()
        ts = inf.infer_tech_stack(tmp_workspace)
        assert ts["proficiency"]["python"] is True
        assert ts["preferences"]["backend"] == "python"

    def test_vue_from_package_json(self, tmp_workspace: Path) -> None:
        (tmp_workspace / "package.json").write_text(
            '{"dependencies": {"vue": "^3.4.0"}}',
            encoding="utf-8",
        )
        inf = ConfigInference()
        ts = inf.infer_tech_stack(tmp_workspace)
        assert ts["proficiency"]["vue"] is True
        assert ts["proficiency"]["react"] is False
        assert ts["preferences"]["frontend"] == "vue"

    def test_react_from_package_json(self, tmp_workspace: Path) -> None:
        (tmp_workspace / "package.json").write_text(
            '{"dependencies": {"react": "^18.0.0"}}',
            encoding="utf-8",
        )
        inf = ConfigInference()
        ts = inf.infer_tech_stack(tmp_workspace)
        assert ts["proficiency"]["react"] is True
        assert ts["preferences"]["frontend"] == "react"

    def test_backend_priority_go_over_python(self, tmp_workspace: Path) -> None:
        """同时存在 Go 和 Python 时优先 Go。"""
        (tmp_workspace / "go.mod").write_text("module x\n")
        (tmp_workspace / "pyproject.toml").write_text("[project]\nname='y'\n")
        inf = ConfigInference()
        ts = inf.infer_tech_stack(tmp_workspace)
        assert ts["preferences"]["backend"] == "go"

    def test_malformed_package_json_no_crash(self, tmp_workspace: Path) -> None:
        (tmp_workspace / "package.json").write_text("not json", encoding="utf-8")
        inf = ConfigInference()
        ts = inf.infer_tech_stack(tmp_workspace)
        assert ts["proficiency"]["vue"] is False


class TestEnvironment:
    """§2B.3 环境推断。"""

    def test_environment_has_os_and_python(self) -> None:
        inf = ConfigInference()
        env = inf.infer_environment()
        assert env["os_supported"]  # 非空
        assert env["python_min"].startswith("3.")
        assert env["display_currency"] in ("CNY", "USD")

    def test_currency_from_zh_cn_lang(self) -> None:
        inf = ConfigInference()
        with patch.dict(os.environ, {"LANG": "zh_CN.UTF-8"}, clear=False):
            env = inf.infer_environment()
            assert env["display_currency"] == "CNY"

    def test_currency_from_en_lang(self) -> None:
        inf = ConfigInference()
        # 同时清理 LC_ALL 避免干扰
        with patch.dict(os.environ, {"LANG": "en_US.UTF-8", "LC_ALL": ""}, clear=False):
            env = inf.infer_environment()
            assert env["display_currency"] == "USD"


class TestWeb:
    """§2B.3 Web 推断。"""

    def test_web_host_is_loopback(self) -> None:
        inf = ConfigInference()
        web = inf.infer_web()
        assert web["host"] == "127.0.0.1"

    def test_web_port_in_valid_range(self) -> None:
        inf = ConfigInference()
        web = inf.infer_web()
        port = web["port"]
        assert 8765 <= port < 8765 + 50


class TestSecurity:
    """§2B.4 安全默认。"""

    def test_writable_covers_workspace(self, tmp_workspace: Path) -> None:
        inf = ConfigInference()
        sec = inf.infer_security(tmp_workspace)
        writable = sec["file_access"]["writable"]
        assert len(writable) == 1
        assert str(tmp_workspace.resolve()) in writable[0]

    def test_readonly_protects_git_and_decisions(self, tmp_workspace: Path) -> None:
        inf = ConfigInference()
        sec = inf.infer_security(tmp_workspace)
        readonly = sec["file_access"]["readonly"]
        assert any(".git/" in p for p in readonly)
        assert any("memory/decisions/" in p for p in readonly)

    def test_forbidden_includes_system_paths(self, tmp_workspace: Path) -> None:
        inf = ConfigInference()
        sec = inf.infer_security(tmp_workspace)
        forbidden = sec["file_access"]["forbidden"]
        assert any(".ssh" in p for p in forbidden)
        assert any("/etc/" in p for p in forbidden)

    def test_command_blacklist_includes_rm_rf_root(self, tmp_workspace: Path) -> None:
        inf = ConfigInference()
        sec = inf.infer_security(tmp_workspace)
        blocked = sec["commands"]["blocked"]
        assert "rm -rf /" in blocked
        assert any("mkfs" in c for c in blocked)


class TestLogging:
    def test_default_info(self) -> None:
        inf = ConfigInference()
        # 清除 DEBUG 环境变量干扰
        with patch.dict(os.environ, {"DEBUG": ""}, clear=False):
            log = inf.infer_logging()
            assert log["level"] == "info"

    def test_debug_env(self) -> None:
        inf = ConfigInference()
        with patch.dict(os.environ, {"DEBUG": "1"}, clear=False):
            log = inf.infer_logging()
            assert log["level"] == "debug"


class TestInferIntegration:
    """综合：infer() 返回完整 InferredConfig。"""

    def test_full_inference(self, tmp_workspace: Path) -> None:
        (tmp_workspace / "go.mod").write_text("module x\n")
        (tmp_workspace / "README.md").write_text("# My Go Project\n", encoding="utf-8")

        inf = ConfigInference()
        result = inf.infer(tmp_workspace)

        assert isinstance(result, InferredConfig)
        assert result.project["name"] == "workspace"
        assert result.project["description"] == "My Go Project"
        assert result.tech_stack["preferences"]["backend"] == "go"
        assert "os_supported" in result.environment
        assert result.web["host"] == "127.0.0.1"

    def test_to_dict_nested(self, tmp_workspace: Path) -> None:
        inf = ConfigInference()
        result = inf.infer(tmp_workspace)
        d = result.to_dict()
        assert set(d.keys()) == {
            "project",
            "tech_stack",
            "environment",
            "web",
            "security",
            "logging",
        }
