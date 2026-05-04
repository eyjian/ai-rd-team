"""ProjectLayout：交付物落位布局决策。

对应设计文档：
- openspec/specs/design/07-artifacts.md §4
- openspec/changes/relocate-artifacts-to-root/design.md D1, D3

核心概念：
- **交付物**（代码 / 文档 / 测试 / 部署脚本）→ 项目根
- **过程数据**（评审 / 报告 / 日志 / manifest）→ .ai-rd-team/runtime/

ProjectLayout 只描述"交付物子路径"（process 部分是框架固定的）。

加载优先级（engine 层组合，本模块不组合）：
1. `<runtime_dir>/reports/data-project-layout.yaml`（架构师声明）
2. `config.advanced.yaml:artifacts.layout`（用户配置）
3. memory 中 `tech-stack-selected.md` 指向的 DEFAULT_LAYOUTS[lang]
4. DEFAULT_LAYOUTS["fallback"]
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------
# ProjectLayout dataclass
# ---------------------------------------------------------------


@dataclass(frozen=True)
class ProjectLayout:
    """项目交付物的目录布局。

    所有路径均为**相对项目根**的字符串（不含前导斜杠）。
    """

    # 代码模块映射：{逻辑模块名 → 项目根下的子目录}。
    # 架构师可显式声明（e.g. {"backend": "mysh", "cli": "mysqler"}），
    # 或直接让模块名 == 目录名（fallback 行为见 ArtifactRecorder.write_code）。
    code_dirs: dict[str, str] = field(default_factory=dict)

    # 文档根：所有 doc 类产出落在 <project_root>/<docs_root>/<subdirs[category]>/
    docs_root: str = "docs"

    # 文档子目录：按 category 分。四类固定（与 ArtifactRecorder.write_doc 对齐）。
    # 架构师想扁平化可覆盖为 {"requirements": "", "design": "", ...}
    docs_subdirs: dict[str, str] = field(
        default_factory=lambda: {
            "requirements": "requirements",
            "design": "design",
            "delivery": "delivery",
            "research": "research",
        }
    )

    # 测试根（separate 模式用）。alongside 模式此字段被忽略。
    tests_root: str | None = "tests"

    # 测试组织模式：
    # - "separate"：测试统一放 <tests_root>/ 下（Python/JS 惯例）
    # - "alongside"：测试与代码同目录（Go 的 *_test.go 惯例）
    tests_mode: str = "separate"

    # 部署产物子目录（k8s yaml 等非根级文件落此处）
    deploy_root: str = "deploy"

    # 部署产物中允许直接落项目根的文件名白名单
    root_level_files: list[str] = field(
        default_factory=lambda: [
            "Dockerfile",
            "docker-compose.yaml",
            "docker-compose.yml",
            "Makefile",
            ".dockerignore",
        ]
    )

    def with_overrides(self, overrides: dict[str, Any]) -> ProjectLayout:
        """基于当前 layout 应用 overrides 得到新 layout。

        overrides 顶层 key 必须是 ProjectLayout 的字段名。
        dict / list 类型字段整体替换（不深合并），遵循 ``data-project-layout.yaml``
        声明语义：架构师要精确控制某个字段，就整体重写它。
        """
        valid_fields = {f.name for f in self.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        sanitized: dict[str, Any] = {}
        for key, value in overrides.items():
            if key not in valid_fields:
                logger.warning(
                    "ProjectLayout.with_overrides: ignoring unknown field '%s'",
                    key,
                )
                continue
            sanitized[key] = value
        return replace(self, **sanitized)


# ---------------------------------------------------------------
# 默认布局表
# ---------------------------------------------------------------

# 说明：DEFAULT_LAYOUTS 是"常识默认"，适用于架构师没显式声明时兜底。
# key 小写，匹配 tech-stack 关键词（见 from_memory 的启发式）。
DEFAULT_LAYOUTS: dict[str, ProjectLayout] = {
    # Python 项目：src/ 布局 + tests/ 独立
    "python": ProjectLayout(
        code_dirs={"main": "src"},
        tests_root="tests",
        tests_mode="separate",
    ),
    # Go 项目：模块目录在根 + _test.go 同包
    "go": ProjectLayout(
        code_dirs={},  # 架构师自行列（如 {mysh: mysh, mysqler: mysqler}）
        tests_root=None,
        tests_mode="alongside",
    ),
    # JS/TS 通用：src/ + tests/
    "js": ProjectLayout(
        code_dirs={"main": "src"},
        tests_root="tests",
        tests_mode="separate",
    ),
    # Vue3 项目：前端单页
    "vue3": ProjectLayout(
        code_dirs={"frontend": "src"},
        tests_root="tests",
        tests_mode="separate",
    ),
    # 微信小程序
    "wechat-mp": ProjectLayout(
        code_dirs={"miniprogram": "miniprogram"},
        tests_root="tests",
        tests_mode="separate",
    ),
    # 最后兜底：src/ + tests/ 通用布局
    "fallback": ProjectLayout(
        code_dirs={"main": "src"},
        tests_root="tests",
        tests_mode="separate",
    ),
}


# 合法的 docs category 集合（对齐 ArtifactRecorder.write_doc）
VALID_DOC_CATEGORIES = frozenset(["requirements", "design", "delivery", "research"])

# 合法的 process kind 集合（对齐 ArtifactRecorder.write_process）
VALID_PROCESS_KINDS = frozenset(["review", "report", "log"])

# 合法的 tests_mode 值
VALID_TESTS_MODES = frozenset(["separate", "alongside"])


# ---------------------------------------------------------------
# 加载入口
# ---------------------------------------------------------------


def get_default_layout(preset: str) -> ProjectLayout:
    """按 preset 名字取默认 layout；未知则返回 fallback。"""
    return DEFAULT_LAYOUTS.get(preset.lower(), DEFAULT_LAYOUTS["fallback"])


def from_yaml(path: Path) -> ProjectLayout:
    """从架构师的 ``data-project-layout.yaml`` 加载 layout。

    YAML Schema::

        version: "1.0"
        base: "go"            # 可选，指向 DEFAULT_LAYOUTS 的 key；缺省视为 fallback
        overrides:            # 可选，覆盖 base 上的字段
          code_dirs: {mysh: mysh, mysqler: mysqler}
          tests_mode: alongside

    异常处理：任意读/解析/字段错误 SHALL 捕获并降级为 fallback + warning，
    MUST NOT 抛异常到调用方。调用方若想记录 events.jsonl，应该自行包装。
    """
    if not path.is_file():
        logger.warning("ProjectLayout.from_yaml: file not found: %s → fallback", path)
        return DEFAULT_LAYOUTS["fallback"]

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        logger.warning(
            "ProjectLayout.from_yaml: failed to parse %s (%s) → fallback",
            path,
            exc,
        )
        return DEFAULT_LAYOUTS["fallback"]

    if not isinstance(data, dict):
        logger.warning(
            "ProjectLayout.from_yaml: %s top-level not a mapping → fallback",
            path,
        )
        return DEFAULT_LAYOUTS["fallback"]

    base_name = str(data.get("base") or "fallback")
    base = get_default_layout(base_name)

    overrides = data.get("overrides") or {}
    if not isinstance(overrides, dict):
        logger.warning(
            "ProjectLayout.from_yaml: 'overrides' in %s is not a mapping → using base only",
            path,
        )
        return base

    try:
        return base.with_overrides(overrides)
    except (TypeError, ValueError) as exc:
        logger.warning(
            "ProjectLayout.from_yaml: overrides invalid in %s (%s) → base only",
            path,
            exc,
        )
        return base


def from_memory(memory_mgr: object | None) -> ProjectLayout:
    """从 memory 的 ``tech-stack-selected`` 条目推断 layout。

    启发式：读取 agent.d/tech-stack-selected 的原始文本，按关键词命中
    DEFAULT_LAYOUTS 的 preset。命中优先级（早命中早返回）：

    - "微信小程序" / "wechat" / "miniprogram"  → wechat-mp
    - "vue" → vue3
    - "go" / "golang" / "kratos" → go
    - "python" → python
    - "javascript" / "typescript" / "node" → js
    - 其它 → fallback

    ``memory_mgr`` 为 None 或无可用 tech-stack 文件时返回 fallback。
    """
    if memory_mgr is None:
        return DEFAULT_LAYOUTS["fallback"]

    text = _read_tech_stack_text(memory_mgr)
    if not text:
        return DEFAULT_LAYOUTS["fallback"]

    return _infer_layout_from_text(text)


def _read_tech_stack_text(memory_mgr: object) -> str | None:
    """尽可能拿到 tech-stack-selected 的正文。

    兼容两种 MemoryManager 接口风格：
    - 有 ``_find_in_layer(layer, name, include_global)`` 返回带 ``.content`` 的 item
    - 或直接读 ``<workspace_memory_dir>/agent.d/tech-stack-selected.md``

    任意异常都返回 None（调用方会 fallback）。
    """
    try:
        # 首选：通过 MemoryManager 的内部接口（保留 scope 语义）
        from ai_rd_team.memory.manager import MemoryLayer  # 局部 import，避免循环依赖

        find = getattr(memory_mgr, "_find_in_layer", None)
        if callable(find):
            item = find(MemoryLayer.AGENT_D, "tech-stack-selected", include_global=True)
            if item is not None:
                # MemoryItem 在当前实现中用 content_body；保留 content/body 兼容旧变体
                content = (
                    getattr(item, "content_body", None)
                    or getattr(item, "content", None)
                    or getattr(item, "body", None)
                )
                if isinstance(content, str) and content:
                    return content
    except Exception as exc:  # noqa: BLE001
        logger.debug("ProjectLayout.from_memory: _find_in_layer failed (%s)", exc)

    # 次选：直接读文件
    try:
        ws_dir = getattr(memory_mgr, "workspace_memory_dir", None)
        if ws_dir is None:
            return None
        path = Path(ws_dir) / "agent.d" / "tech-stack-selected.md"
        if path.is_file():
            return path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.debug("ProjectLayout.from_memory: direct read failed (%s)", exc)

    return None


def _infer_layout_from_text(text: str) -> ProjectLayout:
    """从自由文本推断最匹配的 preset。"""
    lowered = text.lower()

    # 微信小程序优先（避免被"javascript"先匹配）
    if any(kw in lowered for kw in ["微信小程序", "wechat", "miniprogram", "小程序"]):
        return DEFAULT_LAYOUTS["wechat-mp"]
    if "vue" in lowered:
        return DEFAULT_LAYOUTS["vue3"]
    if any(kw in lowered for kw in ["golang", "kratos", " go "]) or lowered.startswith("go"):
        return DEFAULT_LAYOUTS["go"]
    # 明确的 python 关键词
    if "python" in lowered or "py3" in lowered or "pyproject" in lowered:
        return DEFAULT_LAYOUTS["python"]
    if any(kw in lowered for kw in ["javascript", "typescript", "node.js", "nodejs"]):
        return DEFAULT_LAYOUTS["js"]

    return DEFAULT_LAYOUTS["fallback"]


__all__ = [
    "DEFAULT_LAYOUTS",
    "ProjectLayout",
    "VALID_DOC_CATEGORIES",
    "VALID_PROCESS_KINDS",
    "VALID_TESTS_MODES",
    "from_memory",
    "from_yaml",
    "get_default_layout",
]
