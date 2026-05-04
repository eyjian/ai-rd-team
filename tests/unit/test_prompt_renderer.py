"""测试 PromptRenderer（T1.9）。"""

from __future__ import annotations

from pathlib import Path

from ai_rd_team.config.models import (
    CostControl,
    EffectiveConfig,
    ProjectInfo,
    Role,
)
from ai_rd_team.roles.prompt import (
    ROLE_TO_DIR,
    PromptRenderer,
    RenderedPrompt,
    builtin_roles,
)


def _make_config(description: str = "测试项目", mode: str = "standard") -> EffectiveConfig:
    return EffectiveConfig(
        config_version="1.0",
        project=ProjectInfo(
            name="test",
            description=description,
            workspace=Path("/tmp/ws"),
        ),
        cost_control=CostControl(default_mode=mode),  # type: ignore[arg-type]
    )


class TestRender:
    def test_render_architect(self) -> None:
        renderer = PromptRenderer()
        role = builtin_roles()["architect"]
        cfg = _make_config(description="实现一个用户管理")

        rendered = renderer.render(
            role=role,
            instance_name="architect",
            config=cfg,
            team_roster=[("architect", "architect"), ("developer_1", "developer")],
        )

        assert isinstance(rendered, RenderedPrompt)
        assert rendered.instance_name == "architect"
        assert rendered.role_name == "architect"

        # 核心占位符被替换
        content = rendered.content
        assert "$display_name" not in content
        assert "$persona" not in content
        assert "陈架构" in content  # display_name
        assert "实现一个用户管理" in content  # project_description
        assert "standard" in content  # run_mode
        assert "architect" in content

    def test_render_developer_scalable(self) -> None:
        """可伸缩角色的 display_name 应附加编号。"""
        renderer = PromptRenderer()
        role = builtin_roles()["developer"]
        cfg = _make_config()

        rendered = renderer.render(
            role=role,
            instance_name="developer_1",
            config=cfg,
            team_roster=[("developer_1", "developer"), ("developer_2", "developer")],
        )
        # display_name = "林" + "1"
        assert "林1" in rendered.content

    def test_render_team_roster(self) -> None:
        renderer = PromptRenderer()
        role = builtin_roles()["architect"]
        cfg = _make_config()

        rendered = renderer.render(
            role=role,
            instance_name="architect",
            config=cfg,
            team_roster=[
                ("pm", "pm"),
                ("architect", "architect"),
                ("developer_1", "developer"),
            ],
        )

        # 每个成员都在 roster 里
        assert "pm（pm）" in rendered.content
        assert "architect（architect）" in rendered.content
        assert "developer_1（developer）" in rendered.content

    def test_render_role_dir_mapping(self) -> None:
        """渲染应使用 ROLE_TO_DIR 映射。"""
        renderer = PromptRenderer()
        cfg = _make_config()

        # developer → code
        role = builtin_roles()["developer"]
        rendered = renderer.render(
            role=role,
            instance_name="developer_1",
            config=cfg,
            team_roster=[("developer_1", "developer")],
        )
        assert "/artifacts/code/" in rendered.content

        # architect → design
        role_arch = builtin_roles()["architect"]
        rendered_arch = renderer.render(
            role=role_arch,
            instance_name="architect",
            config=cfg,
            team_roster=[("architect", "architect")],
        )
        assert "/artifacts/design/" in rendered_arch.content

    def test_responsibilities_included(self) -> None:
        renderer = PromptRenderer()
        role = builtin_roles()["tester"]
        rendered = renderer.render(
            role=role,
            instance_name="tester",
            config=_make_config(),
            team_roster=[("tester", "tester")],
        )

        # 应包含 tester 的职责清单
        assert "测试用例" in rendered.content

    def test_default_starter_message_placeholder(self) -> None:
        renderer = PromptRenderer()
        rendered = renderer.render(
            role=builtin_roles()["pm"],
            instance_name="pm",
            config=_make_config(description=""),
            team_roster=[("pm", "pm")],
        )
        # 空 description 应有兜底文字
        assert "启动消息" in rendered.content


class TestHelpers:
    def test_role_to_dir_mapping(self) -> None:
        assert ROLE_TO_DIR["architect"] == "design"
        assert ROLE_TO_DIR["developer"] == "code"
        assert ROLE_TO_DIR["tester"] == "test"

    def test_estimate_tokens_rough(self) -> None:
        # 中文字符数估算
        text = "你好世界"  # 4 个中文字符 → 约 4/1.5 = 2 tokens
        assert PromptRenderer.estimate_tokens(text) >= 2

        # 空字符串
        assert PromptRenderer.estimate_tokens("") == 0

    def test_builtin_roles_count(self) -> None:
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

    def test_builtin_developer_is_scalable(self) -> None:
        roles = builtin_roles()
        assert roles["developer"].scalable is True
        assert roles["developer"].default_instances >= 1

    def test_resolve_display_name_non_scalable(self) -> None:
        role = Role(name="architect", display_name="陈架构", scalable=False)
        name = PromptRenderer._resolve_display_name(role, "architect")
        assert name == "陈架构"

    def test_resolve_display_name_scalable(self) -> None:
        role = Role(name="developer", display_name="林", scalable=True)
        name = PromptRenderer._resolve_display_name(role, "developer_2")
        assert name == "林2"

    def test_resolve_display_name_fallback(self) -> None:
        role = Role(name="custom")  # 无 display_name
        name = PromptRenderer._resolve_display_name(role, "custom_1")
        assert name == "custom_1"
