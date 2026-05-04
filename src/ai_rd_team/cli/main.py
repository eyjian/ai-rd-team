"""ai-rd-team CLI 入口（骨架版）。

完整实现见 M1 任务 T1.13，对应设计文档：
- 10-config-schema.md §10（CLI 命令总览）
"""

from __future__ import annotations

import typer
from rich.console import Console

from ai_rd_team import __version__

app = typer.Typer(
    name="ai-rd-team",
    help="自主驱动的数字人研发团队",
    no_args_is_help=True,
)

console = Console()


@app.command()
def version() -> None:
    """显示版本号。"""
    console.print(f"ai-rd-team v{__version__}")


@app.command()
def init(
    interactive: bool = typer.Option(
        True,
        "--interactive/--yes",
        help="是否交互式引导（--yes 使用推荐默认）",
    ),
) -> None:
    """手动触发首次引导（M1 实现）。"""
    console.print("[yellow]init 命令尚未实现，将在 M1 阶段完成[/yellow]")
    raise typer.Exit(code=1)


@app.command()
def run(
    requirement: str = typer.Argument(..., help="需求描述"),
    mode: str | None = typer.Option(None, "--mode", help="运行档位: lite/standard/full"),
    no_onboarding: bool = typer.Option(False, help="跳过首次引导"),
) -> None:
    """启动团队执行需求（M1 实现）。"""
    console.print("[yellow]run 命令尚未实现，将在 M1 阶段完成[/yellow]")
    console.print(f"  requirement: {requirement}")
    console.print(f"  mode: {mode or 'auto'}")
    raise typer.Exit(code=1)


config_app = typer.Typer(help="配置管理")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show(
    layer: str = typer.Option("effective", help="basic/advanced/effective"),
    source: str | None = typer.Option(None, help="查询某字段的来源"),
) -> None:
    """查看配置（M1 实现）。"""
    console.print(f"[yellow]config show 尚未实现（layer={layer}）[/yellow]")
    raise typer.Exit(code=1)


@config_app.command("advanced")
def config_advanced() -> None:
    """生成 config.advanced.yaml（M1 实现）。"""
    console.print("[yellow]config advanced 尚未实现[/yellow]")
    raise typer.Exit(code=1)


@config_app.command("validate")
def config_validate() -> None:
    """校验配置文件（M1 实现）。"""
    console.print("[yellow]config validate 尚未实现[/yellow]")
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
