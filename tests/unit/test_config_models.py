"""测试配置数据类（T1.2）。"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from ai_rd_team.config.models import (
    BasicBudget,
    BasicConfig,
    BasicProject,
    BasicTechStack,
    CostControl,
    EffectiveConfig,
    ModelFallback,
    ProjectInfo,
    QuotaWindows,
    ResourcePointWeights,
    Role,
)


class TestBasicConfig:
    """Basic 层数据类测试。"""

    def test_default_basic_config(self) -> None:
        """Basic 层的默认值符合 §3A。"""
        cfg = BasicConfig()
        assert cfg.config_version == "1.0"
        assert cfg.run_mode == "standard"
        assert cfg.tech_stack.backend is None
        assert cfg.tech_stack.frontend is None
        assert cfg.tech_stack.mobile is None
        assert cfg.budget.per_run == 400
        assert cfg.budget.per_day == 2000

    def test_basic_config_custom(self) -> None:
        """Basic 层可以被自定义。"""
        cfg = BasicConfig(
            project=BasicProject(description="一个 CRM"),
            run_mode="lite",
            tech_stack=BasicTechStack(backend="go-kratos"),
            budget=BasicBudget(per_run=120, per_day=500),
        )
        assert cfg.project.description == "一个 CRM"
        assert cfg.run_mode == "lite"
        assert cfg.tech_stack.backend == "go-kratos"
        assert cfg.budget.per_run == 120

    def test_basic_config_frozen(self) -> None:
        """Basic 层不可变。"""
        cfg = BasicConfig()
        with pytest.raises(FrozenInstanceError):
            cfg.run_mode = "full"  # type: ignore[misc]


class TestResourcePointWeights:
    """权重 v1 值与 P5 校准一致。"""

    def test_default_weights_v1(self) -> None:
        w = ResourcePointWeights()
        # 来自 prototype/05-cost-baseline/results/weight-calibration.md
        assert w.per_member_spawn == 40
        assert w.per_message == 2
        assert w.per_broadcast_target == 2
        assert w.per_minute_runtime == 5
        assert w.per_iteration == 15
        assert w.version == "v1"


class TestBudget:
    """三档预算值与设计文档一致。"""

    def test_lite_budget(self) -> None:
        cc = CostControl()
        assert cc.budget_lite.max_resource_points == 120
        assert cc.budget_lite.max_members == 2
        assert cc.budget_lite.max_broadcasts == 0  # Lite 禁用广播

    def test_standard_budget(self) -> None:
        cc = CostControl()
        assert cc.budget_standard.max_resource_points == 400
        assert cc.budget_standard.max_members == 5
        assert cc.budget_standard.max_broadcasts == 3

    def test_full_budget(self) -> None:
        cc = CostControl()
        assert cc.budget_full.max_resource_points == 1500
        assert cc.budget_full.max_members == 15
        assert cc.budget_full.max_broadcasts == 10


class TestModelFallback:
    """模型降级配置默认值。"""

    def test_defaults(self) -> None:
        mf = ModelFallback()
        assert mf.enabled is True
        assert mf.fallback_mode == "auto"
        assert mf.trigger_threshold == 0.75
        assert mf.strategy == "hybrid"
        # 从贵到便宜
        assert mf.model_chain[0] == "claude-sonnet-4"
        assert mf.model_chain[-1] == "local-qwen"


class TestEffectiveConfig:
    """EffectiveConfig 行为。"""

    def _make_minimal(self, **overrides: object) -> EffectiveConfig:
        defaults = {
            "config_version": "1.0",
            "project": ProjectInfo(
                name="test",
                description="",
                workspace=Path("/tmp/ws"),
            ),
        }
        defaults.update(overrides)
        return EffectiveConfig(**defaults)  # type: ignore[arg-type]

    def test_minimal_construction(self) -> None:
        cfg = self._make_minimal()
        assert cfg.project.name == "test"
        assert cfg.cost_control.enabled is True

    def test_active_mode_default_is_standard(self) -> None:
        cfg = self._make_minimal()
        assert cfg.active_mode == "standard"

    def test_active_mode_respects_remembered(self) -> None:
        cfg = self._make_minimal(
            cost_control=CostControl(remembered_mode="lite"),
        )
        assert cfg.active_mode == "lite"

    def test_active_mode_respects_default_when_not_ask(self) -> None:
        cfg = self._make_minimal(
            cost_control=CostControl(default_mode="full"),
        )
        assert cfg.active_mode == "full"

    def test_active_budget_matches_mode(self) -> None:
        cfg = self._make_minimal(
            cost_control=CostControl(remembered_mode="lite"),
        )
        assert cfg.active_budget.max_resource_points == 120

        cfg_full = self._make_minimal(
            cost_control=CostControl(remembered_mode="full"),
        )
        assert cfg_full.active_budget.max_resource_points == 1500

    def test_config_is_frozen(self) -> None:
        cfg = self._make_minimal()
        with pytest.raises(FrozenInstanceError):
            cfg.config_version = "999"  # type: ignore[misc]


class TestRole:
    """角色数据类。"""

    def test_default_role(self) -> None:
        r = Role(name="architect")
        assert r.name == "architect"
        assert r.enabled is True
        assert r.scalable is False
        assert r.skills == ()
        assert r.model is None


class TestQuotaWindows:
    def test_defaults(self) -> None:
        q = QuotaWindows()
        # 日上限应 >= 单次上限
        assert q.per_day >= q.per_run
        # 周上限应 >= 日上限
        assert q.per_week >= q.per_day
        assert q.per_month >= q.per_week
