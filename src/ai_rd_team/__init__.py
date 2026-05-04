"""ai-rd-team: 自主驱动的数字人研发团队。

设计文档：openspec/specs/design/
"""

from pathlib import Path

__version__ = "0.1.0"


def skills_dir() -> Path:
    """返回 ai-rd-team 的 Skills 目录路径。

    用户可以把此目录链接/复制到 ~/.codebuddy/plugins/marketplaces/local/skills/
    以启用 bridge 和 launcher Skills。

    典型用法：
        $ python -c "import ai_rd_team; print(ai_rd_team.skills_dir())"
    """
    # 项目结构：<root>/src/ai_rd_team/__init__.py
    # Skills 在：<root>/skills/
    # 从本文件向上走两层到 <root>/src，再上一层到 <root>
    here = Path(__file__).resolve().parent  # .../src/ai_rd_team
    candidate_src_layout = here.parent.parent / "skills"  # .../skills
    if candidate_src_layout.is_dir():
        return candidate_src_layout

    # 若是 pip install 后的场景（skills 可能以 data_files 或 package_data 形式）
    # 退化方案：返回本模块目录下的 skills（若存在）
    return here / "skills"


__all__ = ["__version__", "skills_dir"]
