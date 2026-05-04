"""测试 ConfigLoader（T1.5）。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai_rd_team.config.loader import ConfigLoader, ConfigValidationError
from ai_rd_team.config.models import BasicConfig
from ai_rd_team.config.onboarding import ConfigOnboarding


def _silent_print(_s: str) -> None:
    pass


def _non_interactive_onboarding() -> ConfigOnboarding:
    return ConfigOnboarding(print_fn=_silent_print)


def _make_loader(workspace: Path) -> ConfigLoader:
    return ConfigLoader(
        workspace_dir=workspace / ".ai-rd-team",
        onboarding=_non_interactive_onboarding(),
    )


class TestDeepMerge:
    """深度合并算法（§2.2）。"""

    def test_scalar_overrides(self) -> None:
        base = {"a": 1, "b": 2}
        override = {"b": 20, "c": 30}
        result = ConfigLoader._deep_merge(base, override)
        assert result == {"a": 1, "b": 20, "c": 30}

    def test_nested_dict_recursive(self) -> None:
        base = {"cc": {"enabled": True, "mode": "ask"}}
        override = {"cc": {"mode": "full", "new": 42}}
        result = ConfigLoader._deep_merge(base, override)
        assert result == {"cc": {"enabled": True, "mode": "full", "new": 42}}

    def test_list_is_replaced_not_merged(self) -> None:
        """§2.2：数组完全替换。"""
        base = {"roles": [{"name": "a"}, {"name": "b"}]}
        override = {"roles": [{"name": "c"}]}
        result = ConfigLoader._deep_merge(base, override)
        assert result == {"roles": [{"name": "c"}]}

    def test_none_overrides_value(self) -> None:
        """显式 null 覆盖原值。"""
        base = {"x": "hello"}
        override = {"x": None}
        result = ConfigLoader._deep_merge(base, override)
        assert result == {"x": None}


class TestLoadBasic:
    def test_load_basic_not_exists(self, tmp_workspace: Path) -> None:
        loader = _make_loader(tmp_workspace)
        assert loader.load_basic() is None

    def test_load_basic_valid(self, tmp_ai_rd_team_dir: Path) -> None:
        (tmp_ai_rd_team_dir / "config.yaml").write_text(
            yaml.safe_dump(
                {
                    "config_version": "1.0",
                    "run_mode": "lite",
                    "budget": {"per_run": 120, "per_day": 500},
                }
            ),
            encoding="utf-8",
        )

        loader = ConfigLoader(workspace_dir=tmp_ai_rd_team_dir)
        basic = loader.load_basic()

        assert basic is not None
        assert basic.run_mode == "lite"
        assert basic.budget.per_run == 120

    def test_load_basic_invalid_run_mode(self, tmp_ai_rd_team_dir: Path) -> None:
        (tmp_ai_rd_team_dir / "config.yaml").write_text(
            yaml.safe_dump({"run_mode": "garbage"}),
            encoding="utf-8",
        )

        loader = ConfigLoader(workspace_dir=tmp_ai_rd_team_dir)
        with pytest.raises(ConfigValidationError):
            loader.load_basic()

    def test_load_basic_per_day_less_than_per_run(
        self,
        tmp_ai_rd_team_dir: Path,
    ) -> None:
        (tmp_ai_rd_team_dir / "config.yaml").write_text(
            yaml.safe_dump(
                {"budget": {"per_run": 1000, "per_day": 500}},
            ),
            encoding="utf-8",
        )

        loader = ConfigLoader(workspace_dir=tmp_ai_rd_team_dir)
        with pytest.raises(ConfigValidationError):
            loader.load_basic()

    def test_malformed_yaml(self, tmp_ai_rd_team_dir: Path) -> None:
        (tmp_ai_rd_team_dir / "config.yaml").write_text(
            "not: yaml:\n  - broken\n   bad indent",
            encoding="utf-8",
        )

        loader = ConfigLoader(workspace_dir=tmp_ai_rd_team_dir)
        with pytest.raises(ConfigValidationError):
            loader.load_basic()


class TestBasicToAdvanced:
    """§3A.3 展开映射。"""

    def test_expand_basic_run_mode(self, tmp_workspace: Path) -> None:
        loader = _make_loader(tmp_workspace)
        basic = BasicConfig()  # 默认 Standard
        expanded = loader.expand_basic_to_advanced(basic)

        cc = expanded["cost_control"]
        assert cc["default_mode"] == "standard"
        assert cc["remembered_mode"] == "standard"
        assert cc["budget_standard"]["max_resource_points"] == 400
        assert cc["quota_windows"]["per_run"] == 400
        assert cc["quota_windows"]["per_day"] == 2000

    def test_expand_basic_lite(self, tmp_workspace: Path) -> None:
        from ai_rd_team.config.models import BasicBudget

        loader = _make_loader(tmp_workspace)
        basic = BasicConfig(
            run_mode="lite",
            budget=BasicBudget(per_run=120, per_day=500),
        )
        expanded = loader.expand_basic_to_advanced(basic)

        cc = expanded["cost_control"]
        assert cc["default_mode"] == "lite"
        # 对应档位的预算被填入
        assert cc["budget_lite"]["max_resource_points"] == 120
        assert cc["quota_windows"]["per_run"] == 120


class TestLoadEndToEnd:
    """完整 load() 流程。"""

    def test_zero_config_triggers_onboarding(
        self,
        tmp_workspace: Path,
    ) -> None:
        """无 basic 时触发非交互引导，生成 Standard 默认。"""
        loader = _make_loader(tmp_workspace)
        config = loader.load(interactive=False)

        assert config.cost_control.default_mode == "standard"
        assert config.active_budget.max_resource_points == 400
        # 引导生成了 config.yaml
        assert (tmp_workspace / ".ai-rd-team" / "config.yaml").exists()

    def test_no_onboarding_when_disabled(
        self,
        tmp_workspace: Path,
    ) -> None:
        """allow_onboarding=False 时即使缺 basic 也用默认。"""
        loader = _make_loader(tmp_workspace)
        config = loader.load(allow_onboarding=False, interactive=False)

        # 默认 default_mode=ask
        assert config.cost_control.default_mode == "ask"
        # 没生成 config.yaml
        assert not (tmp_workspace / ".ai-rd-team" / "config.yaml").exists()

    def test_with_existing_basic(self, tmp_workspace: Path) -> None:
        """Basic 已存在时不触发引导。"""
        d = tmp_workspace / ".ai-rd-team"
        d.mkdir()
        (d / "config.yaml").write_text(
            yaml.safe_dump(
                {
                    "config_version": "1.0",
                    "run_mode": "full",
                    "budget": {"per_run": 1500, "per_day": 6000},
                }
            ),
            encoding="utf-8",
        )

        loader = _make_loader(tmp_workspace)
        config = loader.load(interactive=False)

        assert config.active_mode == "full"
        assert config.active_budget.max_resource_points == 1500

    def test_preset_overrides_config(self, tmp_workspace: Path) -> None:
        """preset 参数覆盖 config 中的 run_mode。"""
        d = tmp_workspace / ".ai-rd-team"
        d.mkdir()
        (d / "config.yaml").write_text(
            yaml.safe_dump(
                {
                    "config_version": "1.0",
                    "run_mode": "lite",
                    "budget": {"per_run": 120, "per_day": 500},
                }
            ),
            encoding="utf-8",
        )

        loader = _make_loader(tmp_workspace)
        config = loader.load(preset="full", interactive=False)

        # preset 覆盖 lite
        assert config.active_mode == "full"

    def test_advanced_overrides_basic(self, tmp_workspace: Path) -> None:
        """Advanced 层覆盖 Basic。"""
        d = tmp_workspace / ".ai-rd-team"
        d.mkdir()
        (d / "config.yaml").write_text(
            yaml.safe_dump({"run_mode": "standard"}),
            encoding="utf-8",
        )
        (d / "config.advanced.yaml").write_text(
            yaml.safe_dump(
                {
                    "cost_control": {
                        "billing_mode": "subscription",
                        "display_currency": "USD",
                    },
                }
            ),
            encoding="utf-8",
        )

        loader = _make_loader(tmp_workspace)
        config = loader.load(interactive=False)

        # Advanced 的覆盖生效
        assert config.cost_control.billing_mode == "subscription"
        assert config.cost_control.display_currency == "USD"

    def test_tech_stack_inferred_from_workspace(
        self,
        tmp_workspace: Path,
    ) -> None:
        """未指定 tech_stack 时从项目文件推断。"""
        (tmp_workspace / "go.mod").write_text("module x\n")

        loader = _make_loader(tmp_workspace)
        config = loader.load(allow_onboarding=False, interactive=False)

        # inferred 层提供了 preferences.backend=go
        assert config.tech_stack.get("preferences", {}).get("backend") == "go"

    def test_source_files_tracked(self, tmp_workspace: Path) -> None:
        d = tmp_workspace / ".ai-rd-team"
        d.mkdir()
        (d / "config.yaml").write_text(
            yaml.safe_dump({"run_mode": "standard"}),
            encoding="utf-8",
        )

        loader = _make_loader(tmp_workspace)
        config = loader.load(interactive=False)

        assert len(config.source_files) >= 1
        assert any("config.yaml" in str(p) for p in config.source_files)

    def test_workspace_path_in_project(self, tmp_workspace: Path) -> None:
        loader = _make_loader(tmp_workspace)
        config = loader.load(allow_onboarding=False, interactive=False)
        assert config.project.workspace == tmp_workspace


class TestValidate:
    def test_validate_valid(self, tmp_workspace: Path) -> None:
        loader = _make_loader(tmp_workspace)
        errors = loader.validate({"run_mode": "lite"}, layer="basic")
        assert errors == []

    def test_validate_reports_invalid_mode(self, tmp_workspace: Path) -> None:
        loader = _make_loader(tmp_workspace)
        errors = loader.validate({"run_mode": "invalid"}, layer="basic")
        assert len(errors) == 1
        assert "run_mode" in errors[0]
