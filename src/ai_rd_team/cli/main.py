"""ai-rd-team CLI 入口。

对应设计文档：openspec/specs/design/10-config-schema.md §10（CLI 命令总览）

M1 实现：
- version: 显示版本
- init: 触发首次引导
- run: 启动团队
- config show / advanced / validate: 基础配置命令

附加命令（M2+）：
- skills (单数命令): CodeBuddy plugin marketplace 安装信息
- roles-skill list / show: 项目内三层 Skill（builtin/global/workspace），
  注入数字员工 prompt（注意与 ``skills`` 命令的语义区分）
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ai_rd_team import __version__
from ai_rd_team.config.inference import ConfigInference
from ai_rd_team.config.loader import ConfigLoader, ConfigValidationError
from ai_rd_team.config.onboarding import ConfigOnboarding
from ai_rd_team.engine.manager import TeamEnvironmentManager

app = typer.Typer(
    name="ai-rd-team",
    help="自主驱动的数字人研发团队",
    no_args_is_help=True,
)

console = Console()


# ============================================================
# 基础命令
# ============================================================


@app.command()
def version() -> None:
    """显示版本号。"""
    console.print(f"ai-rd-team v{__version__}")


@app.command()
def skills() -> None:
    """显示 ai-rd-team CodeBuddy marketplace 根，并给出 codebuddy plugin 安装命令。"""
    from ai_rd_team import codebuddy_marketplace_dir

    path = codebuddy_marketplace_dir()
    console.print(f"ai-rd-team CodeBuddy Marketplace 根：[bold]{path}[/bold]")
    if not path.is_dir():
        console.print("[yellow]⚠️ 目录不存在，可能需要从源码安装[/yellow]")
        return

    # 检查 marketplace 声明是否齐全
    marketplace_json = path / ".codebuddy-plugin" / "marketplace.json"
    plugin_dir = path / "plugins" / "ai-rd-team"
    plugin_json = plugin_dir / ".codebuddy-plugin" / "plugin.json"
    skills_root = plugin_dir / "skills"

    if not marketplace_json.is_file():
        console.print(f"[yellow]⚠️ 缺少 {marketplace_json.relative_to(path)}[/yellow]")
        return
    if not plugin_json.is_file():
        console.print(f"[yellow]⚠️ 缺少 {plugin_json.relative_to(path)}[/yellow]")
        return

    # 列出 plugin 下的 skill
    skill_dirs = sorted(p for p in skills_root.glob("*/SKILL.md") if p.is_file())
    if skill_dirs:
        console.print("\n包含的 Skills：")
        for s in skill_dirs:
            console.print(f"  - {s.parent.name}  ([dim]{s.relative_to(path)}[/dim])")

    console.print(
        "\n[bold]方式 1：从 GitHub 安装（推荐，最简单，已真机验证）[/bold]\n"
        "  [bold]codebuddy plugin marketplace add "
        "https://github.com/eyjian/ai-rd-team.git[/bold]\n"
        "  [bold]codebuddy plugin install ai-rd-team@ai-rd-team[/bold]\n"
        "  [dim]# 重启 CodeBuddy IDE，插件市场面板会出现 ai-rd-team[/dim]\n"
        "  [dim]# 无需 git clone，CodeBuddy 会自动拉取 + 管理更新[/dim]\n"
        "\n[bold]方式 2：从本地路径安装（适合二次开发 / 离线使用）[/bold]\n"
        f"  [bold]codebuddy plugin marketplace add {path}[/bold]\n"
        "  [bold]codebuddy plugin install ai-rd-team@ai-rd-team[/bold]\n"
        "  [dim]# 本地代码变更即时生效（无需 marketplace update）[/dim]\n"
        "\n[bold]方式 3：直接拷到用户级 Skill 目录（备用，跳过 marketplace）[/bold]\n"
        "  [bold]mkdir -p ~/.codebuddy/skills/[/bold]\n"
        f"  [bold]cp -r {skills_root}/* ~/.codebuddy/skills/[/bold]\n"
        "  [dim]# 失去插件级管理（范围 / 版本 / 卸载）能力[/dim]\n"
        "\n[dim]三种方式都需要重启 CodeBuddy IDE 生效。"
        "详见 docs/01-getting-started.md § 第 2 步。[/dim]"
    )


@app.command()
def init(
    interactive: bool = typer.Option(
        True,
        "--interactive/--yes",
        help="是否交互式引导（--yes 使用推荐默认）",
    ),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="工作区目录（默认当前目录）",
    ),
) -> None:
    """手动触发首次启动引导，生成 config.yaml。"""
    ws = workspace or Path.cwd()
    inf = ConfigInference()
    inferred = inf.infer(ws)

    onboarding = ConfigOnboarding()
    basic = onboarding.run(
        workspace=ws,
        interactive=interactive,
        inferred=inferred,
    )

    config_path = ws / ".ai-rd-team" / "config.yaml"
    console.print(
        Panel(
            f"✅ 已生成配置：[bold]{config_path}[/bold]\n"
            f"   档位：{basic.run_mode}\n"
            f"   预算：{basic.budget.per_run} RP/次, {basic.budget.per_day} RP/天\n"
            f"   技术栈：{_format_tech_stack(basic.tech_stack)}",
            title="init 完成",
            border_style="green",
        )
    )


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="监听地址"),
    port: int = typer.Option(8765, help="监听端口"),
    workspace: Path | None = typer.Option(
        None, "--workspace", "-w", help="工作区根目录（默认当前目录）"
    ),
    reload: bool = typer.Option(False, help="开发模式自动重载"),
) -> None:
    """启动 Web 面板服务（只读模式，不启动引擎）。

    使用 ``ai-rd-team run`` 会自动启动 Web 面板；本命令用于独立查看历史数据。
    """
    import uvicorn

    from ai_rd_team.service.app import create_app

    ws = workspace or Path.cwd()
    runtime_dir = ws / ".ai-rd-team" / "runtime"
    if not runtime_dir.is_dir():
        console.print(
            "[yellow]警告[/yellow]：工作区 runtime 目录不存在，"
            "Web 面板将显示为空。\n"
            f"  期望路径：[dim]{runtime_dir}[/dim]"
        )

    app_instance = create_app(workspace=ws, engine=None)
    url = f"http://{host}:{port}"
    console.print(
        Panel.fit(
            f"ai-rd-team Web 面板\n\n访问：[bold]{url}[/bold]\n工作区：[dim]{ws}[/dim]",
            title="serve",
            border_style="blue",
        )
    )
    uvicorn.run(app_instance, host=host, port=port, reload=reload, log_level="info")


@app.command()
def run(
    requirement: str = typer.Argument(..., help="需求描述"),
    mode: str | None = typer.Option(
        None,
        "--mode",
        help="运行档位: lite / standard / full（覆盖 config 中的 run_mode）",
    ),
    no_onboarding: bool = typer.Option(
        False,
        "--no-onboarding",
        help="跳过首次引导（即使 config.yaml 缺失也用默认值）",
    ),
    openspec: str = typer.Option(
        "ask",
        "--openspec",
        help=(
            "是否走 OpenSpec 流程："
            "ask（默认，由首个发声者在启动后询问真实用户） / "
            "yes（launcher 已代用户同意走 OpenSpec） / "
            "no（已代用户决定跳过） / "
            "skip（完全不提 OpenSpec）。"
        ),
    ),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
        help="工作区目录（默认当前目录）",
    ),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="详细日志"),
) -> None:
    """启动团队执行需求。"""
    if verbose:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
        )

    ws = workspace or Path.cwd()

    # 档位合法性检查
    if mode is not None and mode not in ("lite", "standard", "full"):
        console.print(f"[red]无效的档位 {mode!r}，必须是 lite/standard/full[/red]")
        raise typer.Exit(code=2)

    # OpenSpec 指令合法性检查
    openspec_directive = (openspec or "ask").lower()
    if openspec_directive not in ("ask", "yes", "no", "skip"):
        console.print(
            f"[red]无效的 --openspec {openspec!r}，必须是 ask/yes/no/skip[/red]"
        )
        raise typer.Exit(code=2)

    console.print(
        Panel(
            f"[bold]需求：[/bold]{requirement}\n"
            f"[bold]工作区：[/bold]{ws}\n"
            f"[bold]档位：[/bold]{mode or '（按 config 决定）'}",
            title="ai-rd-team run",
            border_style="blue",
        )
    )

    engine = TeamEnvironmentManager(workspace=ws)
    try:
        engine.initialize(
            preset=mode,  # type: ignore[arg-type]
            allow_onboarding=not no_onboarding,
            interactive=True,
        )
    except ConfigValidationError as e:
        console.print(f"[red]配置校验失败：{e}[/red]")
        raise typer.Exit(code=1) from e
    except Exception as e:
        console.print(f"[red]初始化失败：{e}[/red]")
        if verbose:
            raise
        raise typer.Exit(code=1) from e

    # 启动运行
    try:
        ctx = engine.start_run(
            requirement=requirement,
            openspec_directive=openspec_directive,
        )
    except Exception as e:
        console.print(f"[red]启动运行失败：{e}[/red]")
        if verbose:
            raise
        raise typer.Exit(code=1) from e

    # 展示成员列表
    table = Table(title=f"团队成员（run_id={ctx.run_id}）")
    table.add_column("实例名", style="cyan")
    table.add_column("角色", style="magenta")
    table.add_column("中文名")
    for member in ctx.members.values():
        table.add_row(member.member_id, member.role, member.display_name)
    console.print(table)

    console.print(
        Panel(
            f"✅ 团队已启动，开始自主工作。\n\n"
            f"观察产出：[bold]{ws / '.ai-rd-team' / 'runtime' / 'artifacts'}[/bold]\n"
            f"观察状态：[bold]{ws / '.ai-rd-team' / 'runtime' / 'state'}[/bold]\n\n"
            f"（M1 版本：运行中不阻塞主进程；M2+ 会加入 Web 面板）",
            title="运行中",
            border_style="green",
        )
    )


# ============================================================
# config 子命令
# ============================================================

config_app = typer.Typer(help="配置管理")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show(
    layer: str = typer.Option(
        "effective",
        help="basic / advanced / effective",
    ),
    workspace: Path | None = typer.Option(
        None,
        "--workspace",
        "-w",
    ),
) -> None:
    """查看配置。"""
    ws = workspace or Path.cwd()
    loader = ConfigLoader(workspace_dir=ws / ".ai-rd-team")

    if layer == "basic":
        basic = loader.load_basic()
        if basic is None:
            console.print(f"[yellow]Basic 配置不存在（{ws / '.ai-rd-team/config.yaml'}）[/yellow]")
            raise typer.Exit(code=1)
        console.print(
            f"[bold]run_mode:[/bold] {basic.run_mode}\n"
            f"[bold]tech_stack:[/bold] {_format_tech_stack(basic.tech_stack)}\n"
            f"[bold]budget:[/bold] {basic.budget.per_run} RP/次, "
            f"{basic.budget.per_day} RP/天\n"
            f"[bold]description:[/bold] {basic.project.description}"
        )
    elif layer == "advanced":
        adv = loader.load_advanced()
        if adv is None:
            console.print("[yellow]Advanced 配置不存在[/yellow]")
            raise typer.Exit(code=1)
        import yaml

        console.print(yaml.safe_dump(adv, allow_unicode=True, sort_keys=False))
    else:
        try:
            config = loader.load(allow_onboarding=False, interactive=False)
        except ConfigValidationError as e:
            console.print(f"[red]配置加载失败：{e}[/red]")
            raise typer.Exit(code=1) from e

        table = Table(title="EffectiveConfig 摘要")
        table.add_column("字段", style="cyan")
        table.add_column("值")
        table.add_row("config_version", config.config_version)
        table.add_row("project.name", config.project.name)
        table.add_row("project.workspace", str(config.project.workspace))
        table.add_row("active_mode", config.active_mode)
        table.add_row(
            "active_budget",
            f"{config.active_budget.max_resource_points} RP",
        )
        table.add_row(
            "billing_mode",
            config.cost_control.billing_mode,
        )
        table.add_row(
            "display_currency",
            config.cost_control.display_currency,
        )
        console.print(table)


@config_app.command("advanced")
def config_advanced(
    workspace: Path | None = typer.Option(None, "--workspace", "-w"),
) -> None:
    """导出当前 EffectiveConfig 为 config.advanced.yaml。"""
    ws = workspace or Path.cwd()
    loader = ConfigLoader(workspace_dir=ws / ".ai-rd-team")

    try:
        config = loader.load(allow_onboarding=False, interactive=False)
    except ConfigValidationError as e:
        console.print(f"[red]配置加载失败：{e}[/red]")
        raise typer.Exit(code=1) from e

    import yaml

    # M1 最小版：仅导出关键字段
    dumped = {
        "config_version": config.config_version,
        "project": {
            "description": config.project.description,
        },
        "cost_control": {
            "billing_mode": config.cost_control.billing_mode,
            "default_mode": config.cost_control.default_mode,
            "remembered_mode": config.cost_control.remembered_mode,
            "budget_lite": _budget_to_dict(config.cost_control.budget_lite),
            "budget_standard": _budget_to_dict(config.cost_control.budget_standard),
            "budget_full": _budget_to_dict(config.cost_control.budget_full),
        },
    }

    target = ws / ".ai-rd-team" / "config.advanced.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "# ai-rd-team 高级配置（由 `ai-rd-team config advanced` 生成）\n"
        "# 编辑后下次启动生效；可删除不想改的字段回退到 Basic/default\n\n"
        + yaml.safe_dump(dumped, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    console.print(f"✅ 已生成：[bold]{target}[/bold]")


@config_app.command("preset")
def config_preset(
    mode: str = typer.Option(
        "standard",
        "--mode",
        "-m",
        help="lite / standard / full",
    ),
    workspace: Path | None = typer.Option(None, "--workspace", "-w"),
    force: bool = typer.Option(False, "--force", help="已存在时覆盖"),
    list_only: bool = typer.Option(False, "--list", help="只列出可用 preset，不导出"),
) -> None:
    """导出档位 preset 到 `.ai-rd-team/config.advanced.yaml`。"""
    from ai_rd_team.config.presets_loader import (
        PresetError,
        export_preset_to_workspace,
        list_presets,
    )

    if list_only:
        presets = list_presets()
        console.print("可用 preset：")
        for p in presets:
            console.print(f"  - {p}")
        return

    ws = workspace or Path.cwd()
    try:
        dst = export_preset_to_workspace(mode, ws, force=force)
    except PresetError as e:
        console.print(f"[red]导出失败：[/red]{e}")
        raise typer.Exit(code=1) from None

    console.print(f"✅ 已导出 preset [bold]{mode}[/bold] 到：{dst}")
    console.print("\n建议：")
    console.print("  1. 根据项目实际需要编辑该文件")
    console.print("  2. ai-rd-team config validate 校验")
    console.print("  3. ai-rd-team run '你的需求' 启动")


@config_app.command("validate")
def config_validate(
    workspace: Path | None = typer.Option(None, "--workspace", "-w"),
) -> None:
    """校验 config.yaml 和 config.advanced.yaml。"""
    ws = workspace or Path.cwd()
    loader = ConfigLoader(workspace_dir=ws / ".ai-rd-team")

    errors: list[str] = []

    basic_path = ws / ".ai-rd-team" / "config.yaml"
    if basic_path.is_file():
        import yaml

        try:
            raw = yaml.safe_load(basic_path.read_text(encoding="utf-8")) or {}
            errors.extend(loader.validate(raw, layer="basic"))
        except yaml.YAMLError as e:
            errors.append(f"basic: YAML parse error: {e}")

    if errors:
        console.print("[red]校验失败：[/red]")
        for e in errors:
            console.print(f"  - {e}")
        raise typer.Exit(code=1)

    console.print("✅ 配置校验通过")


# ============================================================
# roles-skill 子命令（项目内 Skill 体系：注入到数字员工 prompt）
# ============================================================
#
# 注意：与单数命令 ``ai-rd-team skills`` 区分——
# - ``ai-rd-team skills``       -> CodeBuddy plugin marketplace 安装信息
# - ``ai-rd-team roles-skill *`` -> 项目内三层 Skill（builtin/global/workspace），
#                                   spawn 数字员工时注入到其 system prompt
#
# 设计文档：openspec/specs/design/05-roles-skills.md

roles_skill_app = typer.Typer(
    help="管理注入数字员工 prompt 的项目内 Skill（builtin / global / workspace 三层）",
)
app.add_typer(roles_skill_app, name="roles-skill")


def _truncate(text: str, width: int = 80) -> str:
    """单行截断字符串，超长尾部用 ``…`` 标记。"""
    text = text.replace("\n", " ").strip()
    if len(text) <= width:
        return text
    return text[: width - 1].rstrip() + "…"


def _format_default_for(default_for: tuple[str, ...]) -> str:
    """格式化 default_for 字段为人类可读字符串。"""
    if not default_for:
        return "（需在 config 显式引用）"
    return "默认装配: " + ", ".join(default_for)


@roles_skill_app.command("list")
def roles_skill_list(
    workspace: Path | None = typer.Option(
        None, "--workspace", "-w", help="工作区目录（默认当前目录）"
    ),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出，便于脚本消费"),
    scope: str | None = typer.Option(
        None,
        "--scope",
        help="只列出某层：builtin / global / workspace",
    ),
) -> None:
    """列出三层可用的 Skill（含元数据：description + default_for）。"""
    from ai_rd_team.roles.skills_loader import SkillsLoader

    if scope is not None and scope not in ("builtin", "global", "workspace"):
        console.print(f"[red]无效的 scope {scope!r}，必须是 builtin/global/workspace[/red]")
        raise typer.Exit(code=2)

    ws = workspace or Path.cwd()
    loader = SkillsLoader.create_default(workspace=ws / ".ai-rd-team")
    available = loader.list_available()

    # 收集每个 skill 的元数据（容错：单个文件出错不影响整体）
    layers: dict[str, list[dict[str, object]]] = {}
    for layer_name, names in available.items():
        if scope is not None and layer_name != scope:
            continue
        rows: list[dict[str, object]] = []
        for name in names:
            try:
                skill = loader.load(f"{layer_name}:{name}")
                rows.append(
                    {
                        "name": name,
                        "scope": layer_name,
                        "description": skill.description,
                        "default_for": list(skill.default_for),
                        "estimated_tokens": skill.estimated_tokens,
                        "path": str(skill.path),
                    }
                )
            except Exception as e:  # noqa: BLE001 - 单个文件解析失败不能拖垮列表
                rows.append(
                    {
                        "name": name,
                        "scope": layer_name,
                        "description": None,
                        "default_for": [],
                        "estimated_tokens": 0,
                        "path": "",
                        "error": str(e),
                    }
                )
        layers[layer_name] = rows

    if json_output:
        import json

        # 注意：用 print 而非 console.print，避免 Rich 的 ANSI 控制字符污染 JSON
        print(json.dumps(layers, ensure_ascii=False, indent=2))
        return

    # 人类可读格式
    icons = {"builtin": "📦", "global": "🏠", "workspace": "📁"}
    # 每层根目录（用于标题旁展示"安装到哪儿"，以及空目录时的引导）
    layer_dirs: dict[str, Path] = {
        "builtin": loader.builtin_dir,
        "global": loader.global_dir,
        "workspace": loader.workspace_dir,
    }

    for layer_name in ("builtin", "global", "workspace"):
        if layer_name not in layers:
            continue
        rows = layers[layer_name]
        icon = icons[layer_name]
        layer_dir = layer_dirs[layer_name]
        title = f"{icon} {layer_name.capitalize()} ({len(rows)})"
        # 标题行直接展示该层根目录，让"装在哪儿"一眼可见
        console.print(f"\n[bold]{title}[/bold]  [dim]{layer_dir}[/dim]")

        if not rows:
            hint = (
                "（暂无；目录不存在，需要时手动 mkdir 即可）"
                if not layer_dir.is_dir()
                else "（空目录）"
            )
            console.print(f"  [dim]{hint}[/dim]")
            continue

        for row in rows:
            name = row["name"]
            default_for = tuple(row.get("default_for", []) or ())  # type: ignore[arg-type]
            err = row.get("error")
            path_str = str(row.get("path", "") or "")
            if err:
                console.print(f"  [red]✗[/red] {name}  [red]解析失败：{err}[/red]")
                if path_str:
                    console.print(f"    [dim]{path_str}[/dim]")
                continue

            tag = _format_default_for(default_for)
            tag_color = "cyan" if default_for else "dim"
            console.print(
                f"  [green]✓[/green] [bold]{name}[/bold]  [{tag_color}]{tag}[/{tag_color}]"
            )

            desc = row.get("description")
            if desc:
                console.print(f"    [dim]{_truncate(str(desc))}[/dim]")
            # 文件路径——告诉用户这个 skill 实际装在哪里，方便复制定位
            if path_str:
                console.print(f"    [dim]↳ {path_str}[/dim]")


@roles_skill_app.command("show")
def roles_skill_show(
    skill_ref: str = typer.Argument(
        ...,
        help="Skill 引用：name 或 scope:name（如 'python-best-practices' 或 'builtin:pytest-guide'）",
    ),
    workspace: Path | None = typer.Option(
        None, "--workspace", "-w", help="工作区目录（默认当前目录）"
    ),
    show_content: bool = typer.Option(
        False, "--content", help="同时打印 Skill 正文（注入数字员工 prompt 的内容）"
    ),
) -> None:
    """查看单个 Skill 的元数据和路径。"""
    from ai_rd_team.roles.skills_loader import (
        SkillNotFoundError,
        SkillReferenceError,
        SkillsLoader,
    )

    ws = workspace or Path.cwd()
    loader = SkillsLoader.create_default(workspace=ws / ".ai-rd-team")

    try:
        skill = loader.load(skill_ref)
    except SkillReferenceError as e:
        console.print(f"[red]引用语法错误：{e}[/red]")
        raise typer.Exit(code=2) from e
    except SkillNotFoundError as e:
        console.print(f"[red]Skill 未找到：{e}[/red]")
        raise typer.Exit(code=1) from e

    table = Table(title=f"Skill: {skill.ref}")
    table.add_column("字段", style="cyan")
    table.add_column("值")
    table.add_row("name", skill.name)
    table.add_row("scope", skill.scope)
    table.add_row("path", str(skill.path))
    table.add_row("estimated_tokens", str(skill.estimated_tokens))
    table.add_row("description", skill.description or "[dim](未设置)[/dim]")
    table.add_row(
        "default_for",
        ", ".join(skill.default_for) if skill.default_for else "[dim](空)[/dim]",
    )
    console.print(table)

    if show_content:
        console.print("\n[bold]正文：[/bold]")
        console.print(skill.content)


# ============================================================
# 辅助函数
# ============================================================


def _format_tech_stack(ts: object) -> str:
    """把 BasicTechStack 格式化为紧凑字符串。"""
    parts: list[str] = []
    for attr in ("backend", "frontend", "mobile"):
        val = getattr(ts, attr, None)
        if val:
            parts.append(f"{attr}={val}")
    return ", ".join(parts) if parts else "auto（架构师自决）"


def _budget_to_dict(budget: object) -> dict[str, int]:
    return {
        "max_members": getattr(budget, "max_members", 0),
        "max_messages": getattr(budget, "max_messages", 0),
        "max_broadcasts": getattr(budget, "max_broadcasts", 0),
        "max_runtime_minutes": getattr(budget, "max_runtime_minutes", 0),
        "max_total_iterations": getattr(budget, "max_total_iterations", 0),
        "max_resource_points": getattr(budget, "max_resource_points", 0),
    }


if __name__ == "__main__":  # pragma: no cover
    app()
