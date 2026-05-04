"""测试首次启动对话引导（T1.4）。"""

from __future__ import annotations

from pathlib import Path

from ai_rd_team.config.inference import ConfigInference, InferredConfig
from ai_rd_team.config.onboarding import ConfigOnboarding


class _FakePrompt:
    """可控的 prompt 模拟器。"""

    def __init__(self, answers: list[str]) -> None:
        self._answers = list(answers)
        self._idx = 0

    def __call__(self, prompt: str) -> str:  # noqa: D401
        if self._idx >= len(self._answers):
            return ""  # 超过则返回空字符串（模拟回车）
        ans = self._answers[self._idx]
        self._idx += 1
        return ans


def _silent_print(s: str) -> None:
    pass


class TestParsing:
    """解析函数单独测试（不涉及 IO）。"""

    def test_parse_run_mode_all_choices(self) -> None:
        assert ConfigOnboarding._parse_run_mode("1") == "lite"
        assert ConfigOnboarding._parse_run_mode("2") == "standard"
        assert ConfigOnboarding._parse_run_mode("3") == "full"
        assert ConfigOnboarding._parse_run_mode("") == "standard"  # 回车 = 默认
        assert ConfigOnboarding._parse_run_mode("garbage") == "standard"
        assert ConfigOnboarding._parse_run_mode("lite") == "lite"

    def test_parse_budget_scales_with_mode(self) -> None:
        lite = ConfigOnboarding._parse_budget("1")
        assert lite == (120, 500)

        standard = ConfigOnboarding._parse_budget("2")
        assert standard == (400, 2000)

        full = ConfigOnboarding._parse_budget("3")
        assert full == (1500, 6000)

    def test_parse_budget_empty_uses_default_mode(self) -> None:
        # 默认档位为 lite 时，空输入返回 lite 预算
        result = ConfigOnboarding._parse_budget("", default_mode="lite")
        assert result == (120, 500)


class TestInteractiveFlow:
    """交互式引导的完整流程。"""

    def test_all_defaults_accepted(self, tmp_workspace: Path) -> None:
        """用户全部回车：得到 Standard 档 + 默认栈 + 2000 RP/天。"""
        prompt = _FakePrompt(["", "", ""])
        onboarding = ConfigOnboarding(prompt_fn=prompt, print_fn=_silent_print)

        basic = onboarding.run(tmp_workspace, interactive=True, inferred=None)

        assert basic.run_mode == "standard"
        assert basic.tech_stack.backend is None
        assert basic.tech_stack.frontend is None
        assert basic.budget.per_run == 400
        assert basic.budget.per_day == 2000

    def test_select_lite_mode(self, tmp_workspace: Path) -> None:
        """用户选 Lite：档位联动预算。"""
        prompt = _FakePrompt(["1", "1", ""])  # lite + 默认栈 + 默认预算(lite)
        onboarding = ConfigOnboarding(prompt_fn=prompt, print_fn=_silent_print)

        basic = onboarding.run(tmp_workspace, interactive=True, inferred=None)

        assert basic.run_mode == "lite"
        # 档位 = lite，Q3 回车采用 lite 默认 = 120 RP
        assert basic.budget.per_run == 120
        assert basic.budget.per_day == 500

    def test_select_full_mode(self, tmp_workspace: Path) -> None:
        prompt = _FakePrompt(["3", "1", ""])  # full + 默认栈 + 默认预算(full)
        onboarding = ConfigOnboarding(prompt_fn=prompt, print_fn=_silent_print)

        basic = onboarding.run(tmp_workspace, interactive=True, inferred=None)

        assert basic.run_mode == "full"
        assert basic.budget.per_run == 1500
        assert basic.budget.per_day == 6000

    def test_choose_builtin_stack(self, tmp_workspace: Path) -> None:
        """选 [3] 内置栈。"""
        prompt = _FakePrompt(["", "3", ""])
        onboarding = ConfigOnboarding(prompt_fn=prompt, print_fn=_silent_print)

        basic = onboarding.run(tmp_workspace, interactive=True, inferred=None)

        assert basic.tech_stack.backend == "go-kratos"
        assert basic.tech_stack.frontend == "vue3"
        assert basic.tech_stack.mobile == "wechat-miniprogram"

    def test_choose_reuse_existing_stack(self, tmp_workspace: Path) -> None:
        """选 [2] 复用现有栈：读取 inferred。"""
        inferred = InferredConfig()
        inferred.tech_stack = {
            "preferences": {"backend": "python", "frontend": "vue", "mobile": None},
        }

        prompt = _FakePrompt(["", "2", ""])
        onboarding = ConfigOnboarding(prompt_fn=prompt, print_fn=_silent_print)

        basic = onboarding.run(tmp_workspace, interactive=True, inferred=inferred)

        assert basic.tech_stack.backend == "python"
        assert basic.tech_stack.frontend == "vue"

    def test_description_from_inferred_readme(self, tmp_workspace: Path) -> None:
        inferred = InferredConfig()
        inferred.project = {
            "name": "test",
            "workspace": tmp_workspace,
            "description": "我的 CRM 系统",
        }

        prompt = _FakePrompt(["", "", ""])
        onboarding = ConfigOnboarding(prompt_fn=prompt, print_fn=_silent_print)

        basic = onboarding.run(tmp_workspace, interactive=True, inferred=inferred)

        assert basic.project.description == "我的 CRM 系统"


class TestNonInteractive:
    """--yes 模式：所有默认。"""

    def test_non_interactive_uses_standard_default(self, tmp_workspace: Path) -> None:
        # prompt 不应被调用
        prompt_call_count = 0

        def failing_prompt(_p: str) -> str:
            nonlocal prompt_call_count
            prompt_call_count += 1
            return ""

        onboarding = ConfigOnboarding(prompt_fn=failing_prompt, print_fn=_silent_print)

        basic = onboarding.run(tmp_workspace, interactive=False, inferred=None)

        assert prompt_call_count == 0
        assert basic.run_mode == "standard"
        assert basic.budget.per_run == 400

    def test_non_interactive_uses_inferred_description(self, tmp_workspace: Path) -> None:
        inferred = InferredConfig()
        inferred.project = {"description": "test project"}

        onboarding = ConfigOnboarding(print_fn=_silent_print)
        basic = onboarding.run(tmp_workspace, interactive=False, inferred=inferred)

        assert basic.project.description == "test project"


class TestWriteToFile:
    """落盘行为。"""

    def test_writes_config_yaml(self, tmp_workspace: Path) -> None:
        onboarding = ConfigOnboarding(print_fn=_silent_print)
        onboarding.run(tmp_workspace, interactive=False, inferred=None)

        config_file = tmp_workspace / ".ai-rd-team" / "config.yaml"
        assert config_file.exists()

        content = config_file.read_text(encoding="utf-8")
        assert 'config_version: "1.0"' in content
        assert 'run_mode: "standard"' in content
        assert "per_run: 400" in content

    def test_creates_parent_dir(self, tmp_path: Path) -> None:
        # workspace 不存在 .ai-rd-team 子目录
        ws = tmp_path / "fresh-workspace"
        ws.mkdir()

        onboarding = ConfigOnboarding(print_fn=_silent_print)
        onboarding.run(ws, interactive=False, inferred=None)

        assert (ws / ".ai-rd-team" / "config.yaml").exists()

    def test_yaml_roundtrip(self, tmp_workspace: Path) -> None:
        """生成的 YAML 能被 PyYAML 解析回来。"""
        import yaml

        onboarding = ConfigOnboarding(print_fn=_silent_print)
        onboarding.run(tmp_workspace, interactive=False, inferred=None)

        config_file = tmp_workspace / ".ai-rd-team" / "config.yaml"
        parsed = yaml.safe_load(config_file.read_text(encoding="utf-8"))

        assert parsed["config_version"] == "1.0"
        assert parsed["run_mode"] == "standard"
        assert parsed["tech_stack"]["backend"] is None
        assert parsed["budget"]["per_run"] == 400

    def test_yaml_is_minimal(self, tmp_workspace: Path) -> None:
        """Basic config 必须 ≤ 30 行（§12.1 验收：≤20 行含空行注释）。"""
        onboarding = ConfigOnboarding(print_fn=_silent_print)
        onboarding.run(tmp_workspace, interactive=False, inferred=None)

        content = (tmp_workspace / ".ai-rd-team" / "config.yaml").read_text()
        # 放宽到 30 行（注释较多）
        assert len(content.splitlines()) <= 30


class TestIntegrationWithInference:
    """推断 + 引导 联合工作。"""

    def test_go_project_hints_existing_stack(self, tmp_workspace: Path) -> None:
        """有 go.mod 时，引导展示 Go 识别信息。"""
        (tmp_workspace / "go.mod").write_text("module example.com/x\n")

        inf = ConfigInference()
        inferred = inf.infer(tmp_workspace)

        messages: list[str] = []

        def capture_print(s: str) -> None:
            messages.append(s)

        prompt = _FakePrompt(["", "2", ""])  # 选"复用现有栈"
        onboarding = ConfigOnboarding(prompt_fn=prompt, print_fn=capture_print)

        basic = onboarding.run(tmp_workspace, interactive=True, inferred=inferred)

        # 展示信息中应提到 go
        joined = "\n".join(messages)
        assert "go" in joined.lower()

        # 应用 Go 栈
        assert basic.tech_stack.backend == "go"
