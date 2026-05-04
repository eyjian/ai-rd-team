"""基础烟测：包可导入、版本号存在、CLI 入口可加载。"""

from __future__ import annotations


def test_package_importable() -> None:
    """包能被正确导入。"""
    import ai_rd_team

    assert ai_rd_team.__version__


def test_version_format() -> None:
    """版本号符合 semver 前缀格式。"""
    import ai_rd_team

    parts = ai_rd_team.__version__.split(".")
    assert len(parts) >= 2
    assert all(p.replace("-", "").replace("a", "").replace("b", "").isalnum() for p in parts)


def test_cli_app_loadable() -> None:
    """CLI 的 Typer app 能被加载。"""
    from ai_rd_team.cli.main import app

    assert app is not None
    assert app.info.name == "ai-rd-team"


def test_all_subpackages_importable() -> None:
    """所有子包都能被导入（骨架完整性检查）。"""
    from ai_rd_team import (
        adapter,
        artifacts,
        cli,
        config,
        cost,
        engine,
        hooks,
        memory,
        roles,
        runtime,
        service,
        utils,
        web,
    )

    assert all(
        mod is not None
        for mod in [
            adapter,
            artifacts,
            cli,
            config,
            cost,
            engine,
            hooks,
            memory,
            roles,
            runtime,
            service,
            utils,
            web,
        ]
    )
