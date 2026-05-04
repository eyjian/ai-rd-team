"""ai-rd-team: 自主驱动的数字人研发团队。

设计文档：openspec/specs/design/
"""

from pathlib import Path

__version__ = "0.1.0b1"


def skills_dir() -> Path:
    """返回 ai-rd-team 的 CodeBuddy Skills 目录路径。

    这个目录存放 **CodeBuddy Skill 包**（launcher / bridge 等给主 Agent 用的 Skill），
    与 ``builtin_skills_dir()`` 返回的 **成员级技能 Markdown** 目录不同。

    用户可以把此目录链接/复制到 ~/.codebuddy/plugins/marketplaces/local/skills/
    以启用 bridge 和 launcher Skills。

    典型用法::

        $ python -c "import ai_rd_team; print(ai_rd_team.skills_dir())"
    """
    here = Path(__file__).resolve().parent  # .../src/ai_rd_team
    # 源码布局：<root>/src/ai_rd_team → <root>/skills
    candidate_src_layout = here.parent.parent / "skills"
    # 只有包含 CodeBuddy Skill 文件（ai-rd-team-*.md）才认为是 CodeBuddy Skills 目录
    if candidate_src_layout.is_dir() and any(candidate_src_layout.glob("ai-rd-team-*.md")):
        return candidate_src_layout

    # pip install 场景的退化路径（后续可能改用 importlib.resources）
    return here / "codebuddy-skills"


def builtin_skills_dir() -> Path:
    """返回成员级内置 Skills（Markdown 文件）的目录。

    这些 Skills 供团队成员（developer / architect 等）加载到 Prompt 中，
    由 ``ai_rd_team.roles.skills_loader.SkillsLoader`` 使用。

    与 ``skills_dir()`` 返回的 **CodeBuddy Skill 包目录** 区分清楚：
    - `skills_dir()` → 给 CodeBuddy 主 Agent 用的 launcher/bridge Skill
    - `builtin_skills_dir()` → 给数字员工用的 python-best-practices / pytest-guide 等
    """
    return Path(__file__).resolve().parent / "skills" / "builtin"


__all__ = ["__version__", "builtin_skills_dir", "skills_dir"]
