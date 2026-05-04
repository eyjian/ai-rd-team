"""Skills 三层加载器（T2.1）。

对应设计文档：openspec/specs/design/05-roles-skills.md §6

三层结构：
- **builtin**：随代码分发（`src/ai_rd_team/skills/builtin/`）
- **global**：用户级（`~/.ai-rd-team/skills/`）
- **workspace**：项目级（`<workspace>/.ai-rd-team/skills/`）

引用语法：
- `builtin:xxx`、`global:xxx`、`workspace:xxx`：强制指定层
- `xxx`（不带 scope）：按优先级 workspace > global > builtin 查找

Skills 是 Markdown 文件（≤ 500 行），纯文档，无执行代码。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SkillScope = Literal["builtin", "global", "workspace"]

_SCOPE_ORDER: tuple[SkillScope, ...] = ("workspace", "global", "builtin")
_VALID_SCOPES: frozenset[str] = frozenset({"builtin", "global", "workspace"})


class SkillError(Exception):
    """Skills 加载基类异常。"""


class SkillNotFoundError(SkillError):
    """Skill 未找到。"""


class SkillReferenceError(SkillError):
    """Skill 引用语法错误。"""


@dataclass(frozen=True)
class LoadedSkill:
    """加载后的 Skill。"""

    name: str  # 不含 scope 前缀
    scope: SkillScope
    path: Path
    content: str
    estimated_tokens: int

    @property
    def ref(self) -> str:
        """规范化引用（带 scope）。"""
        return f"{self.scope}:{self.name}"


def _estimate_tokens(text: str) -> int:
    """粗略估算 Markdown 的 token 数。

    规则与 `roles/prompt.py` 保持一致：
    - 中文字符每 1.5 个 ≈ 1 token
    - 其他字符每 4 个 ≈ 1 token
    """
    if not text:
        return 0
    chinese = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - chinese
    return int(chinese / 1.5) + int(other / 4)


def default_builtin_dir() -> Path:
    """返回包内置的 builtin skills 目录。"""
    # src/ai_rd_team/roles/skills_loader.py → src/ai_rd_team/skills/builtin/
    return Path(__file__).resolve().parent.parent / "skills" / "builtin"


def default_global_dir() -> Path:
    """返回默认的全局 skills 目录。"""
    return Path.home() / ".ai-rd-team" / "skills"


@dataclass
class SkillsLoader:
    """三层 Skills 加载器。

    典型用法::

        loader = SkillsLoader.create_default(workspace=Path.cwd() / ".ai-rd-team")
        skill = loader.load("python-best-practices")         # 优先级查找
        skill = loader.load("workspace:project-conventions") # 强制层
        skills = loader.load_for_role(role)                  # 加载角色的全部 Skills
    """

    builtin_dir: Path
    global_dir: Path
    workspace_dir: Path

    # -----------------------------------------------------------------
    # 构造
    # -----------------------------------------------------------------

    @classmethod
    def create_default(
        cls,
        workspace: Path,
        builtin_dir: Path | None = None,
        global_dir: Path | None = None,
    ) -> SkillsLoader:
        """创建默认配置的 Loader。

        Args:
            workspace: 工作区 `.ai-rd-team` 目录（不含 skills 子目录）
            builtin_dir: 覆盖内置目录（默认包内 skills/builtin）
            global_dir: 覆盖全局目录（默认 ~/.ai-rd-team/skills）
        """
        return cls(
            builtin_dir=builtin_dir or default_builtin_dir(),
            global_dir=global_dir or default_global_dir(),
            workspace_dir=workspace / "skills",
        )

    # -----------------------------------------------------------------
    # 加载
    # -----------------------------------------------------------------

    def load(self, skill_ref: str) -> LoadedSkill:
        """加载一个 Skill。

        Args:
            skill_ref: `builtin:xxx` / `global:xxx` / `workspace:xxx` / `xxx`

        Raises:
            SkillReferenceError: 引用语法错误
            SkillNotFoundError: Skill 未找到
        """
        scope, name = self._parse_ref(skill_ref)
        if scope is not None:
            return self._load_from(scope, name)

        for s in _SCOPE_ORDER:
            try:
                return self._load_from(s, name)
            except SkillNotFoundError:
                continue
        raise SkillNotFoundError(skill_ref)

    def load_many(
        self,
        skill_refs: list[str] | tuple[str, ...],
        missing_ok: bool = False,
    ) -> list[LoadedSkill]:
        """加载多个 Skill。

        Args:
            skill_refs: Skill 引用列表
            missing_ok: True 时，找不到的 Skill 被跳过；False 时抛 SkillNotFoundError
        """
        result: list[LoadedSkill] = []
        for ref in skill_refs:
            try:
                result.append(self.load(ref))
            except SkillNotFoundError:
                if not missing_ok:
                    raise
        return result

    def load_for_role(self, role: object, missing_ok: bool = True) -> list[LoadedSkill]:
        """加载某角色的全部 Skills。

        Args:
            role: 带 ``skills`` 属性的角色对象（如 ``config.models.Role``）
            missing_ok: 默认 True——M2 阶段很多 Skills 还没实现，避免硬失败
        """
        skills_attr = getattr(role, "skills", ())
        return self.load_many(list(skills_attr), missing_ok=missing_ok)

    def list_available(self) -> dict[str, list[str]]:
        """列出各层可用的 skill 名称（不带 scope 前缀）。"""
        return {
            "builtin": self._list_in(self.builtin_dir),
            "global": self._list_in(self.global_dir),
            "workspace": self._list_in(self.workspace_dir),
        }

    # -----------------------------------------------------------------
    # 内部
    # -----------------------------------------------------------------

    @staticmethod
    def _parse_ref(skill_ref: str) -> tuple[SkillScope | None, str]:
        """解析 ``scope:name`` 或 ``name``。"""
        if not skill_ref:
            raise SkillReferenceError("skill_ref must be a non-empty string")
        if ":" not in skill_ref:
            return None, skill_ref

        scope_str, name = skill_ref.split(":", 1)
        if scope_str not in _VALID_SCOPES:
            raise SkillReferenceError(
                f"invalid scope {scope_str!r}; "
                f"valid scopes: builtin / global / workspace"
            )
        if not name:
            raise SkillReferenceError(f"skill name is empty in {skill_ref!r}")
        return scope_str, name  # type: ignore[return-value]

    def _load_from(self, scope: SkillScope, name: str) -> LoadedSkill:
        """从指定层加载。"""
        dir_map: dict[SkillScope, Path] = {
            "builtin": self.builtin_dir,
            "global": self.global_dir,
            "workspace": self.workspace_dir,
        }
        base = dir_map[scope]
        path = base / f"{name}.md"
        if not path.is_file():
            raise SkillNotFoundError(f"{scope}:{name} (looked at {path})")

        content = path.read_text(encoding="utf-8")
        return LoadedSkill(
            name=name,
            scope=scope,
            path=path,
            content=content,
            estimated_tokens=_estimate_tokens(content),
        )

    @staticmethod
    def _list_in(directory: Path) -> list[str]:
        if not directory.is_dir():
            return []
        return sorted(p.stem for p in directory.glob("*.md"))


__all__ = [
    "LoadedSkill",
    "SkillError",
    "SkillNotFoundError",
    "SkillReferenceError",
    "SkillScope",
    "SkillsLoader",
    "default_builtin_dir",
    "default_global_dir",
]
