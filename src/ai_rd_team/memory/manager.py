"""Memory Manager：三层记忆管理器（T2.2 + T2.3）。

对应设计文档：openspec/specs/design/06-memory-system.md

职责：
- 三层目录管理：`agent.d/` / `memory.d/` / `decisions/`
- 双作用域：workspace（项目级）+ global（用户级），workspace 优先
- 文件格式：YAML frontmatter + Markdown 正文
- ADR 编号自动分配（0001 起，按现有文件递增）
- Token 预算控制：agent.d 总和 ≤ 8K，单文件 ≤ 2K（软限）

核心接口：
- load_agent_d(role)：成员 spawn 时加载
- load_memory_d(topic)：按需检索（M2 只做目录浏览）
- load_decision(adr_id) / list_decisions()
- write_agent_d / write_memory_d / write_decision
- next_adr_id()：分配下一个 ADR ID
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from ai_rd_team.utils.file_ops import atomic_write

logger = logging.getLogger(__name__)


# agent.d 加载总 token 软限（06-memory-system §4.2）
AGENT_D_TOTAL_TOKEN_LIMIT = 8000
# agent.d 单文件 token 软限（仅警告，不拦截）
AGENT_D_PER_FILE_TOKEN_LIMIT = 2000


class MemoryLayer(str, Enum):
    """三种记忆层。"""

    AGENT_D = "agent.d"
    MEMORY_D = "memory.d"
    DECISIONS = "decisions"


class MemoryScope(str, Enum):
    """记忆作用域。"""

    PROJECT = "project"
    GLOBAL = "global"


class MemoryError(Exception):
    """Memory 操作基类异常。"""


class MemoryNotFoundError(MemoryError):
    """请求的记忆文件不存在。"""


class MemoryParseError(MemoryError):
    """frontmatter / 内容解析失败。"""


@dataclass(frozen=True)
class MemoryItem:
    """加载后的记忆条目。"""

    layer: MemoryLayer
    path: Path
    title: str  # 从 Markdown 第一个 `#` 标题提取
    frontmatter: dict[str, Any]
    content_body: str  # 去掉 frontmatter 的正文
    estimated_tokens: int
    scope: MemoryScope  # project / global

    @property
    def name(self) -> str:
        """文件名（不含 .md 后缀 / 不含父目录）。"""
        return self.path.stem


def _estimate_tokens(text: str) -> int:
    """与 roles/prompt.py 保持一致的粗略估算。"""
    if not text:
        return 0
    chinese = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - chinese
    return int(chinese / 1.5) + int(other / 4)


def _utc_date() -> str:
    """返回 YYYY-MM-DD 格式（UTC）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _utc_datetime() -> str:
    """返回带时区的 ISO 8601 时间戳（毫秒精度）。"""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# -----------------------------------------------------------------
# Frontmatter 解析
# -----------------------------------------------------------------

_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(?P<meta>.*?)\n---\s*\n(?P<body>.*)$",
    re.DOTALL,
)


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """拆 Markdown 的 YAML frontmatter 与 body。"""
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return {}, text
    meta_raw = match.group("meta")
    body = match.group("body")
    try:
        meta = yaml.safe_load(meta_raw) or {}
    except yaml.YAMLError as e:
        raise MemoryParseError(f"failed to parse frontmatter: {e}") from e
    if not isinstance(meta, dict):
        raise MemoryParseError(
            f"frontmatter must be a YAML mapping, got {type(meta).__name__}"
        )
    return meta, body


def _extract_title(body: str) -> str:
    """提取 Markdown 第一个 `# 标题`；找不到则用空串。"""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _format_frontmatter(meta: dict[str, Any]) -> str:
    """把 frontmatter dict 格式化回 YAML 块（含 `---` 分隔）。"""
    body = yaml.safe_dump(
        meta,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    )
    return f"---\n{body}---\n"


# -----------------------------------------------------------------
# MemoryManager
# -----------------------------------------------------------------


@dataclass
class MemoryManager:
    """三层记忆管理器。

    典型用法::

        mm = MemoryManager(
            workspace_memory_dir=ws / ".ai-rd-team/memory",
        )
        mm.ensure_directories()
        items = mm.load_agent_d(role)
        mm.write_decision(
            adr_id=mm.next_adr_id(),
            title="Go + Kratos",
            content="...",
            author="architect",
        )
    """

    workspace_memory_dir: Path
    global_memory_dir: Path | None = None

    # 每个 (scope, layer, name) 缓存一次（避免重复解析）
    _cache: dict[tuple[str, str, str], MemoryItem] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.global_memory_dir is None:
            self.global_memory_dir = Path.home() / ".ai-rd-team" / "memory"

    # -----------------------------------------------------------------
    # 目录管理
    # -----------------------------------------------------------------

    def ensure_directories(self) -> None:
        """创建项目级 memory 的三个子目录（idempotent）。"""
        for layer in MemoryLayer:
            (self.workspace_memory_dir / layer.value).mkdir(
                parents=True, exist_ok=True
            )

    # -----------------------------------------------------------------
    # 加载：agent.d（启动加载，有预算控制）
    # -----------------------------------------------------------------

    def load_agent_d(
        self,
        role: object,
        include_global: bool = True,
    ) -> list[MemoryItem]:
        """加载某角色启动时需要的 agent.d 内容。

        顺序：按 role.memory_scope["agent_d"] 列表顺序；
        预算：累计 tokens ≤ AGENT_D_TOTAL_TOKEN_LIMIT，超出则截断。

        Args:
            role: 带 ``memory_scope`` 属性的角色对象
            include_global: 是否允许回退到全局层

        Returns:
            按引用顺序的 MemoryItem 列表，总 tokens 不超上限
        """
        memory_scope = getattr(role, "memory_scope", None) or {}
        files = list(memory_scope.get("agent_d") or [])

        items: list[MemoryItem] = []
        total = 0
        for name in files:
            item = self._find_in_layer(
                MemoryLayer.AGENT_D, name, include_global=include_global
            )
            if item is None:
                logger.debug("agent.d not found: %s", name)
                continue
            if total + item.estimated_tokens > AGENT_D_TOTAL_TOKEN_LIMIT:
                logger.warning(
                    "agent.d budget exceeded; truncating at %s tokens (limit %s)",
                    total,
                    AGENT_D_TOTAL_TOKEN_LIMIT,
                )
                break
            if item.estimated_tokens > AGENT_D_PER_FILE_TOKEN_LIMIT:
                logger.warning(
                    "agent.d file %s exceeds soft limit (%s > %s tokens)",
                    item.name,
                    item.estimated_tokens,
                    AGENT_D_PER_FILE_TOKEN_LIMIT,
                )
            items.append(item)
            total += item.estimated_tokens
        return items

    # -----------------------------------------------------------------
    # 加载：memory.d（按需检索）
    # -----------------------------------------------------------------

    def load_memory_d(
        self,
        topic: str | None = None,
        tag_filter: list[str] | None = None,
        include_global: bool = True,
    ) -> list[MemoryItem]:
        """按主题/tag 加载 memory.d 内容。

        Args:
            topic: 子目录名（如 ``domain`` / ``past-cases``）；None 时遍历全部
            tag_filter: 只返回 frontmatter.tags 包含其中任一 tag 的文件
        """
        results: list[MemoryItem] = []
        seen: set[str] = set()  # 项目级同名覆盖全局级

        for scope_dir, scope in self._iter_scope_dirs(include_global):
            base = scope_dir / MemoryLayer.MEMORY_D.value
            if not base.is_dir():
                continue
            glob_dir = base / topic if topic else base
            if topic and not glob_dir.is_dir():
                continue
            for path in sorted(glob_dir.rglob("*.md")):
                rel_key = str(path.relative_to(base))
                if rel_key in seen:
                    continue
                seen.add(rel_key)
                item = self._parse_file(MemoryLayer.MEMORY_D, path, scope)
                if tag_filter:
                    tags = item.frontmatter.get("tags") or []
                    if not any(t in tags for t in tag_filter):
                        continue
                results.append(item)
        return results

    # -----------------------------------------------------------------
    # 加载：decisions（ADR）
    # -----------------------------------------------------------------

    def load_decision(
        self,
        adr_id: str,
        include_global: bool = True,
    ) -> MemoryItem | None:
        """加载某 ADR（按 adr_id 查找文件）。"""
        for scope_dir, scope in self._iter_scope_dirs(include_global):
            base = scope_dir / MemoryLayer.DECISIONS.value
            if not base.is_dir():
                continue
            for path in base.glob(f"{adr_id}-*.md"):
                return self._parse_file(MemoryLayer.DECISIONS, path, scope)
        return None

    def list_decisions(
        self,
        status_filter: str | None = None,
        include_global: bool = False,
    ) -> list[MemoryItem]:
        """列出所有 ADR。

        Args:
            status_filter: proposed / accepted / deprecated / superseded；None 表示全部
            include_global: 默认只看项目级（全局级 ADR 很少用）
        """
        results: list[MemoryItem] = []
        seen_ids: set[str] = set()

        for scope_dir, scope in self._iter_scope_dirs(include_global):
            base = scope_dir / MemoryLayer.DECISIONS.value
            if not base.is_dir():
                continue
            for path in sorted(base.glob("*.md")):
                item = self._parse_file(MemoryLayer.DECISIONS, path, scope)
                adr_id = str(item.frontmatter.get("adr_id") or item.name.split("-")[0])
                if adr_id in seen_ids:
                    continue
                seen_ids.add(adr_id)
                if status_filter is not None and (
                    item.frontmatter.get("status") != status_filter
                ):
                    continue
                results.append(item)
        return results

    def next_adr_id(self) -> str:
        """分配下一个 ADR ID（如 ``0005``）。

        扫描项目级 decisions/ 目录下所有 `{id}-*.md`，取最大 +1。
        """
        base = self.workspace_memory_dir / MemoryLayer.DECISIONS.value
        if not base.is_dir():
            return "0001"

        max_id = 0
        for path in base.glob("*.md"):
            name = path.stem
            m = re.match(r"^(\d{4})-", name)
            if m:
                max_id = max(max_id, int(m.group(1)))
        return f"{max_id + 1:04d}"

    # -----------------------------------------------------------------
    # 写入：agent.d / memory.d / decisions
    # -----------------------------------------------------------------

    def write_agent_d(
        self,
        name: str,
        content: str,
        author: str,
        tags: list[str] | None = None,
        related: list[str] | None = None,
    ) -> MemoryItem:
        """写或更新 agent.d 文件。"""
        path = self.workspace_memory_dir / MemoryLayer.AGENT_D.value / f"{name}.md"
        return self._write_memory_file(
            path=path,
            layer=MemoryLayer.AGENT_D,
            content=content,
            author=author,
            tags=tags,
            related=related,
            extra_meta=None,
        )

    def write_memory_d(
        self,
        relative_path: str,
        content: str,
        author: str,
        tags: list[str] | None = None,
        related: list[str] | None = None,
    ) -> MemoryItem:
        """写或更新 memory.d 文件。

        Args:
            relative_path: 相对 memory.d 的路径，如 ``domain/business-rules`` 或 ``past-cases/2026-05-auth``
        """
        # 去掉可能的 .md 后缀
        if relative_path.endswith(".md"):
            relative_path = relative_path[:-3]
        path = (
            self.workspace_memory_dir
            / MemoryLayer.MEMORY_D.value
            / f"{relative_path}.md"
        )
        return self._write_memory_file(
            path=path,
            layer=MemoryLayer.MEMORY_D,
            content=content,
            author=author,
            tags=tags,
            related=related,
            extra_meta=None,
        )

    def write_decision(
        self,
        adr_id: str,
        title: str,
        content: str,
        author: str,
        status: str = "proposed",
        supersedes: str | None = None,
        tags: list[str] | None = None,
        related: list[str] | None = None,
    ) -> MemoryItem:
        """写一个新 ADR。

        文件名：``{adr_id}-{title-slug}.md``
        若 content 不以 ``#`` 开头，会自动加一级标题。
        """
        slug = _slugify(title)
        path = (
            self.workspace_memory_dir
            / MemoryLayer.DECISIONS.value
            / f"{adr_id}-{slug}.md"
        )

        # 若正文不含一级标题，自动加
        if not content.lstrip().startswith("# "):
            content = f"# ADR-{adr_id}：{title}\n\n{content.lstrip()}"

        return self._write_memory_file(
            path=path,
            layer=MemoryLayer.DECISIONS,
            content=content,
            author=author,
            tags=tags,
            related=related,
            extra_meta={
                "adr_id": adr_id,
                "status": status,
                "supersedes": supersedes,
                "superseded_by": None,
            },
        )

    def render_adr_template(
        self,
        adr_id: str,
        title: str,
        *,
        context: str = "",
        options: list[tuple[str, list[str]]] | None = None,
        decision: str = "",
        consequences: str = "",
    ) -> str:
        """生成 MADR 风格的 ADR 模板正文（不含 frontmatter）。

        Args:
            adr_id: ADR 编号
            title: 标题
            context: "上下文（Why 需要这个决策）"
            options: [(选项名, [要点列表]), ...]
            decision: 最终决策
            consequences: "后果（正面/负面）"

        Returns:
            Markdown 正文（以 `# ADR-xxxx：title` 起始）
        """
        parts = [f"# ADR-{adr_id}：{title}", ""]
        parts += ["## 状态", f"Proposed（{_utc_date()}）", ""]
        parts += ["## 上下文（Why 需要这个决策）", context or "（待补充）", ""]

        parts.append("## 选项考察")
        if options:
            for opt_name, bullets in options:
                parts.append(f"\n### {opt_name}")
                for bullet in bullets:
                    parts.append(f"- {bullet}")
        else:
            parts.append("\n（待列出选项 A / B / C 并对比）")
        parts.append("")

        parts += ["## 决策", decision or "（待填）", ""]
        parts += [
            "## 理由",
            "1. （待补充）",
            "",
            "## 后果",
            consequences or "**正面**：\n- （待补充）\n\n**负面**：\n- （待补充）",
            "",
            "## 相关",
            "- （链接到 artifacts/design 的相关设计）",
            "",
        ]
        return "\n".join(parts)

    # -----------------------------------------------------------------
    # 内部：解析、写入、目录遍历
    # -----------------------------------------------------------------

    def _iter_scope_dirs(
        self, include_global: bool
    ) -> list[tuple[Path, MemoryScope]]:
        """按优先级顺序返回 scope 目录列表（project 在前）。"""
        result: list[tuple[Path, MemoryScope]] = [
            (self.workspace_memory_dir, MemoryScope.PROJECT)
        ]
        if include_global and self.global_memory_dir is not None:
            result.append((self.global_memory_dir, MemoryScope.GLOBAL))
        return result

    def _find_in_layer(
        self,
        layer: MemoryLayer,
        name: str,
        include_global: bool = True,
    ) -> MemoryItem | None:
        """按 scope 优先级查找 `layer/{name}.md`。"""
        if name.endswith(".md"):
            name = name[:-3]
        for scope_dir, scope in self._iter_scope_dirs(include_global):
            path = scope_dir / layer.value / f"{name}.md"
            if path.is_file():
                return self._parse_file(layer, path, scope)
        return None

    def _parse_file(
        self,
        layer: MemoryLayer,
        path: Path,
        scope: MemoryScope,
    ) -> MemoryItem:
        """解析 Markdown → MemoryItem（带缓存）。"""
        cache_key = (scope.value, layer.value, str(path))
        cached = self._cache.get(cache_key)
        # 若文件修改了（mtime 不同），失效重读
        if cached is not None:
            try:
                if cached.path.stat().st_mtime == path.stat().st_mtime:
                    return cached
            except OSError:
                pass  # 继续重读

        text = path.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(text)
        title = _extract_title(body) or path.stem

        tokens_from_meta = frontmatter.get("estimated_tokens")
        if isinstance(tokens_from_meta, int) and tokens_from_meta > 0:
            tokens = tokens_from_meta
        else:
            tokens = _estimate_tokens(body)

        item = MemoryItem(
            layer=layer,
            path=path,
            title=title,
            frontmatter=frontmatter,
            content_body=body,
            estimated_tokens=tokens,
            scope=scope,
        )
        self._cache[cache_key] = item
        return item

    def _write_memory_file(
        self,
        path: Path,
        layer: MemoryLayer,
        content: str,
        author: str,
        tags: list[str] | None,
        related: list[str] | None,
        extra_meta: dict[str, Any] | None,
    ) -> MemoryItem:
        """统一的写入流程：补 frontmatter → 原子写 → 重解析返回 MemoryItem。"""
        path.parent.mkdir(parents=True, exist_ok=True)

        # 读取旧 frontmatter 以保留 created 字段
        created = _utc_date()
        if path.is_file():
            try:
                old_text = path.read_text(encoding="utf-8")
                old_meta, _ = _split_frontmatter(old_text)
                if old_meta.get("created"):
                    created = str(old_meta["created"])
            except (OSError, MemoryParseError):
                pass

        meta: dict[str, Any] = {
            "type": "adr" if layer == MemoryLayer.DECISIONS else "memory",
            "layer": layer.value,
            "author": author,
            "created": created,
            "updated": _utc_datetime(),
        }
        if extra_meta:
            # 过滤掉 None 值以保持 YAML 整洁（supersedes/superseded_by 默认 None 也留着）
            for k, v in extra_meta.items():
                meta[k] = v
        if related:
            meta["related"] = list(related)
        if tags:
            meta["tags"] = list(tags)

        # body + token 估算写入 meta
        meta["estimated_tokens"] = _estimate_tokens(content)

        text = _format_frontmatter(meta) + "\n" + content.rstrip() + "\n"
        atomic_write(path, text)

        # 缓存失效
        self._cache.clear()
        return self._parse_file(
            layer,
            path,
            MemoryScope.PROJECT,
        )


# -----------------------------------------------------------------
# 工具函数
# -----------------------------------------------------------------


_SLUG_STRIP = re.compile(r"[^\w\u4e00-\u9fff-]+", re.UNICODE)


def _slugify(title: str) -> str:
    """把标题转成文件名安全的 slug。

    - 空白 → 单个连字符
    - 去掉标点（保留字母 / 数字 / 下划线 / 中文 / 连字符）
    - 全小写（中文不受影响）
    - 合并多个连字符
    """
    s = title.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = _SLUG_STRIP.sub("-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


__all__ = [
    "AGENT_D_PER_FILE_TOKEN_LIMIT",
    "AGENT_D_TOTAL_TOKEN_LIMIT",
    "MemoryError",
    "MemoryItem",
    "MemoryLayer",
    "MemoryManager",
    "MemoryNotFoundError",
    "MemoryParseError",
    "MemoryScope",
]
