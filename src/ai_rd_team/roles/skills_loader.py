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

可选的 YAML frontmatter（参考 Anthropic Skills 规范）::

    ---
    name: code-review-checklist
    description: 代码评审清单。在评审 PR / 代码质量检查时使用。
    default_for: [architect, reviewer]
    ---

    # 正文 ...

约定：
- 有 frontmatter 时，``LoadedSkill.content`` 只含正文（已剥离 ``---`` 块），
  解析后的字段通过 ``LoadedSkill.metadata`` 暴露（只读 Mapping）。
- 无 frontmatter 时，``metadata`` 为 ``None``，``content`` 为整个文件内容（向后兼容）。
- ``estimated_tokens`` 仅基于正文计算，不计 frontmatter。

frontmatter 字段说明：
- ``name``：标识符，与文件名 ``<name>.md`` 一致（仅文档价值，不影响加载）
- ``description``：一段简短描述，用于文档生成与未来对外分发为标准 Skill
- ``default_for``：本项目自定义扩展，标记 "默认装配给哪些角色"，
  应与 ``roles.prompt._DEFAULT_ROLE_SKILLS`` 镜像一致
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Mapping

import yaml

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
    """加载后的 Skill。

    Attributes:
        name: 不含 scope 前缀的 skill 名（与文件名 ``<name>.md`` 对应）
        scope: 来源层（builtin / global / workspace）
        path: 文件路径
        content: 正文 Markdown（**已剥离 frontmatter**）
        estimated_tokens: 仅基于 ``content`` 估算的 token 数
        metadata: 解析后的 frontmatter；无 frontmatter 时为 ``None``
    """

    name: str  # 不含 scope 前缀
    scope: SkillScope
    path: Path
    content: str
    estimated_tokens: int
    metadata: Mapping[str, Any] | None = field(default=None)

    @property
    def ref(self) -> str:
        """规范化引用（带 scope）。"""
        return f"{self.scope}:{self.name}"

    @property
    def description(self) -> str | None:
        """快捷访问 frontmatter 的 description 字段。"""
        if self.metadata is None:
            return None
        value = self.metadata.get("description")
        return value if isinstance(value, str) else None

    @property
    def default_for(self) -> tuple[str, ...]:
        """快捷访问 frontmatter 的 default_for 字段（默认空元组）。"""
        if self.metadata is None:
            return ()
        value = self.metadata.get("default_for", ())
        if isinstance(value, (list, tuple)):
            return tuple(str(v) for v in value)
        return ()


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

# YAML frontmatter 的开/闭分隔符：必须是独占一行的 ``---``（允许行尾空白）。
# 注意：不用正则吞整个块，避免 catastrophic backtracking——按行扫描 O(n)。
_FRONTMATTER_FENCE = "---"


def _is_fence_line(line: str) -> bool:
    """判断一行是否是合法的 frontmatter 分隔符 ``---``（去除 \\r 与右侧空白后）。"""
    return line.rstrip("\r").rstrip() == _FRONTMATTER_FENCE


def _parse_frontmatter(text: str) -> tuple[Mapping[str, Any] | None, str]:
    """从 Markdown 文本顶部解析可选的 YAML frontmatter。

    采用**按行扫描**而非单一正则匹配，避免在病态输入下出现指数回溯。

    Args:
        text: 文件原始文本

    Returns:
        (metadata, body)：
        - 没有 frontmatter（或起始 ``---`` 后找不到闭合分隔符）时，metadata 为
          ``None``，body 为原文本（**保留** 原始 ``---`` —— 不是 frontmatter 时
          可能是正文里的 horizontal rule，不应被吞）
        - 有 frontmatter 但 YAML 解析失败 / 顶层不是 mapping 时，metadata 按
          ``None`` 处理（容错），但仍会剥掉 ``---`` 块——避免污染 prompt
        - 解析成功时 metadata 是只读 ``MappingProxyType``
    """
    # 去除 BOM（不修改 text 之外的可见字符）
    if text.startswith("\ufeff"):
        text = text[1:]

    # 必须以 ``---`` 行开头才进入解析流程；否则原样返回
    lines = text.split("\n")
    if not lines or not _is_fence_line(lines[0]):
        return None, text

    # 从第 2 行起寻找闭合 fence
    closing_idx: int | None = None
    for i in range(1, len(lines)):
        if _is_fence_line(lines[i]):
            closing_idx = i
            break

    if closing_idx is None:
        # 起始 ``---`` 没有配对闭合 —— 不算 frontmatter，原样返回
        return None, text

    yaml_block = "\n".join(lines[1:closing_idx])
    # body 取闭合 fence 之后所有内容，并丢弃紧随其后的空行
    body_lines = lines[closing_idx + 1:]
    while body_lines and body_lines[0].strip() == "":
        body_lines.pop(0)
    body = "\n".join(body_lines)

    try:
        parsed = yaml.safe_load(yaml_block) if yaml_block.strip() else None
    except yaml.YAMLError:
        # frontmatter 格式坏了：仍剥掉 ``---`` 块，但不暴露 metadata
        return None, body

    if not isinstance(parsed, dict):
        return None, body

    return MappingProxyType(dict(parsed)), body


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
                f"invalid scope {scope_str!r}; valid scopes: builtin / global / workspace"
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

        raw = path.read_text(encoding="utf-8")
        metadata, body = _parse_frontmatter(raw)
        return LoadedSkill(
            name=name,
            scope=scope,
            path=path,
            content=body,
            estimated_tokens=_estimate_tokens(body),
            metadata=metadata,
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
