"""首次启动对话引导。

对应设计文档：openspec/specs/design/10-config-schema.md §2A

核心设计：
- ≤3 个问题，每题有推荐默认（回车即接受）
- interactive=False 时全部取默认（适合 CI）
- 产出：BasicConfig + 落盘到 <workspace>/.ai-rd-team/config.yaml
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ai_rd_team.config.models import (
    BasicBudget,
    BasicConfig,
    BasicProject,
    BasicTechStack,
    RunMode,
)

if TYPE_CHECKING:
    from ai_rd_team.config.inference import InferredConfig


# 档位对应的默认预算（同 10-config-schema §3A）
_BUDGET_BY_MODE: dict[RunMode, tuple[int, int]] = {
    "lite": (120, 500),
    "standard": (400, 2000),
    "full": (1500, 6000),
}


# 可注入的提示函数签名：(prompt) -> 用户输入
# 默认使用 input()，测试可注入 mock
PromptFn = Callable[[str], str]


class ConfigOnboarding:
    """首次启动对话引导。

    典型用法：
        onboarding = ConfigOnboarding()
        basic = onboarding.run(workspace, interactive=True, inferred=inf)
        # basic 已写入 workspace/.ai-rd-team/config.yaml
    """

    def __init__(
        self,
        prompt_fn: PromptFn | None = None,
        print_fn: Callable[[str], None] | None = None,
    ) -> None:
        # 默认使用 input + print（可被测试注入）
        self._prompt: PromptFn = prompt_fn or input
        self._print: Callable[[str], None] = print_fn or print

    def run(
        self,
        workspace: Path,
        interactive: bool = True,
        inferred: InferredConfig | None = None,
    ) -> BasicConfig:
        """执行引导，返回 BasicConfig 并写入 config.yaml。

        Args:
            workspace: 工作区根目录
            interactive: True 则问 3 个问题；False 则全取默认
            inferred: 智能推断结果（用于展示"已识别"提示和默认值）

        Returns:
            BasicConfig 对象

        Side effects:
            写入 <workspace>/.ai-rd-team/config.yaml（若目录不存在则创建）
        """
        basic = self._interactive(inferred) if interactive else self._from_defaults(inferred)

        self._write(workspace, basic)
        return basic

    # ------------------------------------------------------------
    # 交互式引导
    # ------------------------------------------------------------

    def _interactive(self, inferred: InferredConfig | None) -> BasicConfig:
        """执行 3 问引导。"""
        self._print("")
        self._print("👋 你好，我是 ai-rd-team。我检测到这是你第一次在这个项目使用我。")

        # 介绍识别到的项目类型
        if inferred is not None:
            detected = self._describe_detection(inferred)
            if detected:
                self._print(f"   项目识别：{detected}")

        self._print("   3 个问题，20 秒完成：")
        self._print("")

        # Q1: 项目规模
        run_mode = self._ask_run_mode()

        # Q2: 技术栈
        tech_stack = self._ask_tech_stack(inferred)

        # Q3: 预算
        budget = self._ask_budget(run_mode)

        # Q0（最轻量）：项目描述 - 不问用户，默认用 README 标题或留空
        description = ""
        if inferred is not None:
            description = inferred.project.get("description", "") or ""

        return BasicConfig(
            config_version="1.0",
            project=BasicProject(description=description),
            run_mode=run_mode,
            tech_stack=tech_stack,
            budget=budget,
        )

    def _ask_run_mode(self) -> RunMode:
        """Q1 项目规模。"""
        self._print("1. 项目规模大概是？")
        self._print("   [1] 小玩意，几天能搞定（Lite）")
        self._print("   [2] 正经项目，几周 ← 默认（Standard）")
        self._print("   [3] 大系统，慢慢来（Full）")
        choice = self._prompt("   > ").strip()
        return self._parse_run_mode(choice, default="standard")

    def _ask_tech_stack(self, inferred: InferredConfig | None) -> BasicTechStack:
        """Q2 技术栈。"""
        self._print("")
        self._print("2. 技术栈？")
        self._print("   [1] 我不管，架构师自己定 ← 默认")

        # 展示识别到的已有栈
        existing_hint = ""
        if inferred is not None:
            prefs = inferred.tech_stack.get("preferences", {})
            backend = prefs.get("backend")
            frontend = prefs.get("frontend")
            if backend or frontend:
                parts = []
                if backend:
                    parts.append(f"后端 {backend}")
                if frontend:
                    parts.append(f"前端 {frontend}")
                existing_hint = "，".join(parts)

        if existing_hint:
            self._print(f"   [2] 复用现有项目的栈（已识别：{existing_hint}）")
        else:
            self._print("   [2] 复用现有项目的栈（未识别到现有栈）")

        self._print("   [3] 指定：Go+Kratos 后端 / Vue3 PC / 微信小程序")
        self._print("   [4] 稍后自己改 config.yaml")
        choice = self._prompt("   > ").strip()
        return self._parse_tech_stack(choice, inferred)

    def _ask_budget(self, mode: RunMode) -> BasicBudget:
        """Q3 预算大约。"""
        per_run_default, per_day_default = _BUDGET_BY_MODE[mode]
        self._print("")
        self._print("3. 预算大约？")
        self._print("   [1] 能省则省（Lite 预算 120 RP/次）")
        self._print("   [2] 平衡 ← 默认（Standard 400 RP/次, 2000 RP/天）")
        self._print("   [3] 要最好的（Full 1500 RP/次）")
        choice = self._prompt("   > ").strip()
        per_run, per_day = self._parse_budget(choice, default_mode=mode)
        return BasicBudget(per_run=per_run, per_day=per_day)

    # ------------------------------------------------------------
    # 解析函数（可单独测试）
    # ------------------------------------------------------------

    @staticmethod
    def _parse_run_mode(choice: str, default: RunMode = "standard") -> RunMode:
        mapping: dict[str, RunMode] = {
            "1": "lite",
            "2": "standard",
            "3": "full",
            "lite": "lite",
            "standard": "standard",
            "full": "full",
        }
        if not choice:
            return default
        return mapping.get(choice.lower(), default)

    @staticmethod
    def _parse_tech_stack(
        choice: str,
        inferred: InferredConfig | None,
    ) -> BasicTechStack:
        # 默认：全部 null（架构师自主选择）
        if not choice or choice == "1":
            return BasicTechStack()

        # [2] 复用现有栈
        if choice == "2" and inferred is not None:
            prefs = inferred.tech_stack.get("preferences", {})
            return BasicTechStack(
                backend=prefs.get("backend"),
                frontend=prefs.get("frontend"),
                mobile=prefs.get("mobile"),
            )

        # [3] 默认内置栈
        if choice == "3":
            return BasicTechStack(
                backend="go-kratos",
                frontend="vue3",
                mobile="wechat-miniprogram",
            )

        # [4] 稍后自己改
        return BasicTechStack()

    @staticmethod
    def _parse_budget(
        choice: str,
        default_mode: RunMode = "standard",
    ) -> tuple[int, int]:
        mapping: dict[str, RunMode] = {
            "1": "lite",
            "2": "standard",
            "3": "full",
        }
        if not choice:
            return _BUDGET_BY_MODE[default_mode]
        mode = mapping.get(choice, default_mode)
        return _BUDGET_BY_MODE[mode]

    # ------------------------------------------------------------
    # 非交互（--yes 或 CI）
    # ------------------------------------------------------------

    def _from_defaults(self, inferred: InferredConfig | None) -> BasicConfig:
        """非交互模式：用推荐默认 + 推断。"""
        description = ""
        if inferred is not None:
            description = inferred.project.get("description", "") or ""
        return BasicConfig(
            config_version="1.0",
            project=BasicProject(description=description),
            run_mode="standard",
            tech_stack=BasicTechStack(),
            budget=BasicBudget(per_run=400, per_day=2000),
        )

    # ------------------------------------------------------------
    # 落盘
    # ------------------------------------------------------------

    def _write(self, workspace: Path, basic: BasicConfig) -> None:
        """将 BasicConfig 写入 <workspace>/.ai-rd-team/config.yaml。"""
        target_dir = workspace / ".ai-rd-team"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "config.yaml"

        content = self._render_yaml(basic)
        target.write_text(content, encoding="utf-8")

    @staticmethod
    def _render_yaml(basic: BasicConfig) -> str:
        """手工渲染 Basic 配置为 YAML（保留注释，便于用户编辑）。

        不用 yaml.dump 因为那样无法带注释。
        """
        description = basic.project.description or "（请填写一句话描述）"

        def _ystr(v: Any) -> str:
            if v is None:
                return "null"
            # 字符串包括中文都可以直接输出为双引号形式
            return '"' + str(v).replace('"', '\\"') + '"'

        lines = [
            "# ai-rd-team 基础配置（首次引导自动生成，可手动编辑）",
            "# 高级配置用 `ai-rd-team config advanced` 生成 config.advanced.yaml",
            "",
            f'config_version: "{basic.config_version}"',
            "",
            "project:",
            f"  description: {_ystr(description)}",
            "",
            f'run_mode: "{basic.run_mode}"     # lite / standard / full',
            "",
            "# 技术栈（留空表示让架构师自主选择；架构师会参考现有代码）",
            "tech_stack:",
            f"  backend: {_ystr(basic.tech_stack.backend)}",
            f"  frontend: {_ystr(basic.tech_stack.frontend)}",
            f"  mobile: {_ystr(basic.tech_stack.mobile)}",
            "",
            "# 预算（Resource Points）",
            "budget:",
            f"  per_run: {basic.budget.per_run}",
            f"  per_day: {basic.budget.per_day}",
            "",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------

    @staticmethod
    def _describe_detection(inferred: InferredConfig) -> str:
        """组装一条"已识别"字符串供展示。"""
        prefs = inferred.tech_stack.get("preferences", {})
        backend = prefs.get("backend")
        frontend = prefs.get("frontend")
        parts: list[str] = []
        if backend:
            parts.append(f"{backend} 后端")
        if frontend:
            parts.append(f"{frontend} 前端")
        if not parts:
            return "空项目"
        return " + ".join(parts)
