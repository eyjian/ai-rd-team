"""配置加载与合并。

对应设计文档：openspec/specs/design/10-config-schema.md §2 + §9

M1 范围：
- 五层合并（defaults ← inferred ← global ← basic ← advanced）
- 首次启动引导触发
- Basic → Advanced 展开（run_mode 联动预算）
- 最小 JSON Schema 校验

M2+ 扩展：
- 完整 JSON Schema
- 版本迁移（§7）
- 源追踪 get_effective_source
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml

from ai_rd_team.config.inference import ConfigInference, InferredConfig
from ai_rd_team.config.models import (
    BasicConfig,
    Budget,
    CostControl,
    EffectiveConfig,
    ProjectInfo,
    QuotaWindows,
    ResourcePointWeights,
    Role,
    RunMode,
)
from ai_rd_team.config.onboarding import ConfigOnboarding


class ConfigValidationError(Exception):
    """配置校验失败。"""


class ConfigMigrationError(Exception):
    """配置版本迁移失败。"""


# Basic 层默认文件名
_BASIC_FILENAME = "config.yaml"
_ADVANCED_FILENAME = "config.advanced.yaml"


@dataclass
class ConfigLoader:
    """配置加载器。

    典型用法：
        loader = ConfigLoader(workspace_dir=Path.cwd() / ".ai-rd-team")
        config = loader.load()  # 缺 basic 时触发引导

    测试中可注入替身：
        loader = ConfigLoader(
            workspace_dir=...,
            onboarding=fake_onboarding,
            inference=fake_inference,
        )
    """

    workspace_dir: Path
    global_dir: Path = Path.home() / ".ai-rd-team"
    inference: ConfigInference | None = None
    onboarding: ConfigOnboarding | None = None

    def __post_init__(self) -> None:
        if self.inference is None:
            self.inference = ConfigInference()
        if self.onboarding is None:
            self.onboarding = ConfigOnboarding()

    # ------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------

    def load(
        self,
        preset: RunMode | None = None,
        allow_onboarding: bool = True,
        interactive: bool = True,
    ) -> EffectiveConfig:
        """加载配置，产出 EffectiveConfig。

        合并顺序：defaults ← inferred ← global ← basic ← advanced

        Args:
            preset: 强制档位（覆盖 config.yaml 中的 run_mode）
            allow_onboarding: 若项目 config.yaml 不存在，是否触发引导
            interactive: 引导时是否允许交互
        """
        workspace = self._workspace_root()

        # 1. 智能推断
        assert self.inference is not None
        inferred = self.inference.infer(workspace)

        # 2. 项目 Basic（若缺失可触发引导）
        basic = self.load_basic()
        if basic is None and allow_onboarding:
            assert self.onboarding is not None
            basic = self.onboarding.run(
                workspace=workspace,
                interactive=interactive,
                inferred=inferred,
            )

        # 3. Advanced 层
        advanced_raw = self.load_advanced()

        # 4. 全局层（可选，仅限本 M1 版本：不实现）
        #    留空作为扩展点

        # 5. 展开 basic → advanced 风格的 dict
        basic_expanded = self.expand_basic_to_advanced(basic) if basic else {}

        # 6. 合并：defaults ← inferred ← basic_expanded ← advanced_raw
        merged = self._deep_merge(
            self._defaults_dict(),
            inferred.to_dict(),
        )
        merged = self._deep_merge(merged, basic_expanded)
        if advanced_raw:
            merged = self._deep_merge(merged, advanced_raw)

        # 7. 应用 preset（覆盖 run_mode）
        if preset is not None:
            merged.setdefault("cost_control", {})["remembered_mode"] = preset
            merged["cost_control"]["default_mode"] = preset

        # 8. 基础校验
        self._validate_basic_fields(merged)

        # 9. 构建 EffectiveConfig
        source_files: list[Path] = []
        if basic is not None:
            source_files.append(self._basic_path())
        if advanced_raw:
            source_files.append(self._advanced_path())

        return self._build_effective_config(
            merged=merged,
            inferred=inferred,
            source_files=source_files,
        )

    # ------------------------------------------------------------
    # 分层加载
    # ------------------------------------------------------------

    def load_basic(self) -> BasicConfig | None:
        """只加载 Basic 层，不合并。"""
        path = self._basic_path()
        if not path.is_file():
            return None

        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as e:
            raise ConfigValidationError(f"Failed to parse {path}: {e}") from e

        return self._parse_basic(raw)

    def load_advanced(self) -> dict[str, Any] | None:
        """只加载 Advanced 层，返回原始 dict。"""
        path = self._advanced_path()
        if not path.is_file():
            return None
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as e:
            raise ConfigValidationError(f"Failed to parse {path}: {e}") from e
        if not isinstance(raw, dict):
            raise ConfigValidationError(f"{path} must be a mapping at top level")
        return raw

    # ------------------------------------------------------------
    # Basic → Advanced 展开（§3A.3）
    # ------------------------------------------------------------

    def expand_basic_to_advanced(self, basic: BasicConfig) -> dict[str, Any]:
        """将 Basic 配置展开为 Advanced 风格的 dict。

        字段映射遵循 10-config-schema.md §3A.3。
        """
        # run_mode 联动预算
        mode = basic.run_mode
        budget_per_run = basic.budget.per_run
        budget_per_day = basic.budget.per_day

        return {
            "config_version": basic.config_version,
            "project": {
                "description": basic.project.description,
            },
            "tech_stack": {
                "preferences": {
                    "backend": basic.tech_stack.backend,
                    "frontend": basic.tech_stack.frontend,
                    "mobile": basic.tech_stack.mobile,
                },
            },
            "cost_control": {
                "default_mode": mode,
                "remembered_mode": mode,
                f"budget_{mode}": {
                    "max_resource_points": budget_per_run,
                },
                "quota_windows": {
                    "per_run": budget_per_run,
                    "per_day": budget_per_day,
                },
            },
        }

    # ------------------------------------------------------------
    # 合并与校验
    # ------------------------------------------------------------

    @staticmethod
    def _deep_merge(
        base: dict[str, Any],
        override: dict[str, Any],
    ) -> dict[str, Any]:
        """深度合并：标量/数组低层覆盖，对象递归合并（§2.2）。"""
        result = copy.deepcopy(base)
        for key, override_val in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(override_val, dict)
            ):
                result[key] = ConfigLoader._deep_merge(result[key], override_val)
            else:
                # 标量、数组直接覆盖（包括 None 也覆盖）
                result[key] = copy.deepcopy(override_val)
        return result

    @staticmethod
    def _validate_basic_fields(merged: dict[str, Any]) -> None:
        """M1 最小校验：关键字段存在和类型正确。"""
        # config_version
        cv = merged.get("config_version")
        if not isinstance(cv, str):
            raise ConfigValidationError("config_version must be a string")

        # cost_control.default_mode
        cc = merged.get("cost_control", {})
        mode = cc.get("default_mode")
        if mode not in ("ask", "lite", "standard", "full"):
            raise ConfigValidationError(
                f"cost_control.default_mode must be one of "
                f"ask/lite/standard/full, got {mode!r}"
            )

    def validate(
        self,
        raw: dict[str, Any],
        layer: Literal["basic", "advanced"] = "advanced",
    ) -> list[str]:
        """仅校验，返回错误列表（M1 最小版）。"""
        errors: list[str] = []
        try:
            if layer == "basic":
                self._parse_basic(raw)
            else:
                self._validate_basic_fields(raw)
        except ConfigValidationError as e:
            errors.append(str(e))
        return errors

    # ------------------------------------------------------------
    # 构建最终 EffectiveConfig
    # ------------------------------------------------------------

    def _build_effective_config(
        self,
        merged: dict[str, Any],
        inferred: InferredConfig,
        source_files: list[Path],
    ) -> EffectiveConfig:
        # project
        proj_raw = merged.get("project", {})
        inf_proj = inferred.project
        project = ProjectInfo(
            name=proj_raw.get("name") or inf_proj.get("name", "unnamed-project"),
            description=proj_raw.get("description", ""),
            workspace=Path(proj_raw.get("workspace") or inf_proj["workspace"]),
        )

        # cost_control
        cost_control = self._build_cost_control(merged.get("cost_control", {}))

        # roles
        roles: dict[str, Role] = {}
        for name, role_raw in (merged.get("roles") or {}).items():
            if not isinstance(role_raw, dict):
                continue
            roles[name] = self._build_role(name, role_raw)

        return EffectiveConfig(
            config_version=merged.get("config_version", "1.0"),
            project=project,
            roles=roles,
            tech_stack=merged.get("tech_stack") or {},
            adapter=merged.get("adapter") or {},
            environment=merged.get("environment") or {},
            team=merged.get("team") or {},
            security=merged.get("security") or {},
            web=merged.get("web") or {},
            hooks=merged.get("hooks") or {},
            notifications=merged.get("notifications") or {},
            quality_gates=merged.get("quality_gates") or {},
            logging=merged.get("logging") or {},
            resource_limits=merged.get("resource_limits") or {},
            cost_control=cost_control,
            role_models=merged.get("role_models") or {},
            tools=merged.get("tools") or {},
            rules=merged.get("rules") or {},
            source_files=tuple(source_files),
            loaded_at=datetime.now(),
        )

    @staticmethod
    def _build_cost_control(raw: dict[str, Any]) -> CostControl:
        """从 dict 构建 CostControl（用默认值填充缺失字段）。"""
        defaults = CostControl()

        # budget_{mode} 可能只有部分字段（来自 Basic 展开）
        def _build_budget(raw_budget: dict[str, Any], default: Budget) -> Budget:
            if not raw_budget:
                return default
            return Budget(
                max_members=raw_budget.get("max_members", default.max_members),
                max_messages=raw_budget.get("max_messages", default.max_messages),
                max_broadcasts=raw_budget.get("max_broadcasts", default.max_broadcasts),
                max_runtime_minutes=raw_budget.get(
                    "max_runtime_minutes", default.max_runtime_minutes
                ),
                max_total_iterations=raw_budget.get(
                    "max_total_iterations", default.max_total_iterations
                ),
                max_resource_points=raw_budget.get(
                    "max_resource_points", default.max_resource_points
                ),
            )

        budget_lite = _build_budget(raw.get("budget_lite", {}), defaults.budget_lite)
        budget_standard = _build_budget(
            raw.get("budget_standard", {}),
            defaults.budget_standard,
        )
        budget_full = _build_budget(raw.get("budget_full", {}), defaults.budget_full)

        # quota_windows
        qw_raw = raw.get("quota_windows", {})
        qw_default = defaults.quota_windows
        quota_windows = QuotaWindows(
            per_run=qw_raw.get("per_run", qw_default.per_run),
            per_day=qw_raw.get("per_day", qw_default.per_day),
            per_week=qw_raw.get("per_week", qw_default.per_week),
            per_month=qw_raw.get("per_month", qw_default.per_month),
        )

        # 权重
        w_raw = raw.get("resource_point_weights", {})
        w_default = defaults.resource_point_weights
        weights = ResourcePointWeights(
            per_member_spawn=w_raw.get(
                "per_member_spawn", w_default.per_member_spawn
            ),
            per_message=w_raw.get("per_message", w_default.per_message),
            per_broadcast_target=w_raw.get(
                "per_broadcast_target", w_default.per_broadcast_target
            ),
            per_minute_runtime=w_raw.get(
                "per_minute_runtime", w_default.per_minute_runtime
            ),
            per_iteration=w_raw.get("per_iteration", w_default.per_iteration),
            version=w_raw.get("version", w_default.version),
        )

        default_mode = raw.get("default_mode", defaults.default_mode)
        remembered_mode = raw.get("remembered_mode")

        return CostControl(
            enabled=raw.get("enabled", defaults.enabled),
            billing_mode=raw.get("billing_mode", defaults.billing_mode),
            display_currency=raw.get("display_currency", defaults.display_currency),
            confirm_currency_on_startup=raw.get(
                "confirm_currency_on_startup",
                defaults.confirm_currency_on_startup,
            ),
            resource_point_weights=weights,
            budget_lite=budget_lite,
            budget_standard=budget_standard,
            budget_full=budget_full,
            on_budget_exceeded=raw.get(
                "on_budget_exceeded", defaults.on_budget_exceeded
            ),
            quota_enabled=raw.get("quota_enabled", defaults.quota_enabled),
            quota_windows=quota_windows,
            quota_on_exceed=raw.get("quota_on_exceed", {}) or {},
            model_fallback=defaults.model_fallback,  # M1 先用默认
            post_run_recording_enabled=raw.get(
                "post_run_recording_enabled",
                defaults.post_run_recording_enabled,
            ),
            default_mode=default_mode,
            remembered_mode=remembered_mode,
        )

    @staticmethod
    def _build_role(name: str, raw: dict[str, Any]) -> Role:
        return Role(
            name=name,
            enabled=raw.get("enabled", True),
            display_name=raw.get("display_name", ""),
            persona=raw.get("persona", ""),
            scalable=raw.get("scalable", False),
            max_instances=raw.get("max_instances", 1),
            default_instances=raw.get("default_instances", 1),
            skills=tuple(raw.get("skills", [])),
            rules=tuple(raw.get("rules", [])),
            memory_scope=raw.get("memory_scope", {}) or {},
            model=raw.get("model"),
        )

    # ------------------------------------------------------------
    # Basic 解析
    # ------------------------------------------------------------

    @staticmethod
    def _parse_basic(raw: dict[str, Any]) -> BasicConfig:
        """从 dict 解析 BasicConfig，含字段校验。"""
        from ai_rd_team.config.models import (
            BasicBudget,
            BasicProject,
            BasicTechStack,
        )

        run_mode = raw.get("run_mode", "standard")
        if run_mode not in ("lite", "standard", "full"):
            raise ConfigValidationError(
                f"run_mode must be lite/standard/full, got {run_mode!r}"
            )

        budget_raw = raw.get("budget", {}) or {}
        per_run = budget_raw.get("per_run", 400)
        per_day = budget_raw.get("per_day", 2000)
        if not isinstance(per_run, int) or per_run <= 0:
            raise ConfigValidationError("budget.per_run must be positive integer")
        if not isinstance(per_day, int) or per_day < per_run:
            raise ConfigValidationError(
                f"budget.per_day ({per_day}) must be >= budget.per_run ({per_run})"
            )

        ts_raw = raw.get("tech_stack", {}) or {}
        tech_stack = BasicTechStack(
            backend=ts_raw.get("backend"),
            frontend=ts_raw.get("frontend"),
            mobile=ts_raw.get("mobile"),
        )

        proj_raw = raw.get("project", {}) or {}
        project = BasicProject(description=proj_raw.get("description", ""))

        return BasicConfig(
            config_version=raw.get("config_version", "1.0"),
            project=project,
            run_mode=run_mode,
            tech_stack=tech_stack,
            budget=BasicBudget(per_run=per_run, per_day=per_day),
        )

    # ------------------------------------------------------------
    # 默认值
    # ------------------------------------------------------------

    @staticmethod
    def _defaults_dict() -> dict[str, Any]:
        """代码内置 defaults.yaml 的等价物。

        M1 阶段手工维护；M4 阶段可迁移到独立 defaults.yaml。
        """
        return {
            "config_version": "1.0",
            "cost_control": {
                "default_mode": "ask",
                "billing_mode": "auto",
            },
            "roles": {},
            "tech_stack": {},
            "adapter": {},
            "team": {},
            "security": {},
            "hooks": {},
            "notifications": {},
            "quality_gates": {},
            "resource_limits": {},
            "role_models": {},
            "tools": {},
            "rules": {},
        }

    # ------------------------------------------------------------
    # 路径
    # ------------------------------------------------------------

    def _workspace_root(self) -> Path:
        """workspace_dir 一般是 {ws}/.ai-rd-team，返回 {ws}。"""
        if self.workspace_dir.name == ".ai-rd-team":
            return self.workspace_dir.parent
        return self.workspace_dir

    def _basic_path(self) -> Path:
        return self.workspace_dir / _BASIC_FILENAME

    def _advanced_path(self) -> Path:
        return self.workspace_dir / _ADVANCED_FILENAME
