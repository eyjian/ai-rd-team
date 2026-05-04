"""ai-rd-team: 自主驱动的数字人研发团队。

设计文档：openspec/specs/design/
"""

from pathlib import Path

__version__ = "0.1.0b1"


def codebuddy_marketplace_dir() -> Path:
    """返回 ai-rd-team 作为 CodeBuddy marketplace 的根目录路径。

    此目录是一个标准 CodeBuddy marketplace，结构::

        <root>/
        ├── .codebuddy-plugin/marketplace.json   # marketplace 声明
        └── plugins/ai-rd-team/
            ├── .codebuddy-plugin/plugin.json   # plugin 元数据
            └── skills/
                ├── ai-rd-team-launcher/SKILL.md
                └── ai-rd-team-bridge/SKILL.md

    用户把本目录链接到 ``~/.codebuddy/plugins/marketplaces/`` 下，
    CodeBuddy 会自动发现并提示启用 plugin。

    典型用法::

        $ python -c "import ai_rd_team; print(ai_rd_team.codebuddy_marketplace_dir())"
    """
    here = Path(__file__).resolve().parent  # .../src/ai_rd_team
    # 源码布局：<root>/src/ai_rd_team → <root>/（含 .codebuddy-plugin/）
    candidate_src_layout = here.parent.parent
    marker = candidate_src_layout / ".codebuddy-plugin" / "marketplace.json"
    if marker.is_file():
        return candidate_src_layout

    # pip install 场景的退化路径（后续可能改用 importlib.resources）
    return here / "codebuddy-marketplace"


def skills_dir() -> Path:
    """已弃用别名。返回 codebuddy_marketplace_dir()。

    历史版本（M1 ~ 0.1.0b1）返回仓库根下的 ``skills/`` 目录（单 .md 文件式）。
    M6 修复后 ai-rd-team 改为标准 CodeBuddy marketplace 布局，本函数
    重定向到 ``codebuddy_marketplace_dir()`` 以保持向后兼容。

    新代码请直接用 ``codebuddy_marketplace_dir()``。
    """
    return codebuddy_marketplace_dir()


def builtin_skills_dir() -> Path:
    """返回成员级内置 Skills（Markdown 文件）的目录。

    这些 Skills 供团队成员（developer / architect 等）加载到 Prompt 中，
    由 ``ai_rd_team.roles.skills_loader.SkillsLoader`` 使用。

    与 ``codebuddy_marketplace_dir()`` 返回的 **CodeBuddy marketplace 根** 区分清楚：
    - `codebuddy_marketplace_dir()` → 给 CodeBuddy 主 Agent 用的 launcher/bridge Skill
    - `builtin_skills_dir()` → 给数字员工用的 python-best-practices / pytest-guide 等
    """
    return Path(__file__).resolve().parent / "skills" / "builtin"


__all__ = [
    "__version__",
    "builtin_skills_dir",
    "codebuddy_marketplace_dir",
    "skills_dir",
]
