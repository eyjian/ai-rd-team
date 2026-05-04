"""ProjectLayout 数据层测试（M7 任务 1.3）。

覆盖：
- 六档 DEFAULT_LAYOUTS 构造
- ProjectLayout.with_overrides 字段替换 + 非法字段忽略
- from_yaml：base+overrides 合并 / 文件不存在 / YAML 解析失败 / 非 mapping → fallback
- from_memory：MemoryManager 路径 / 直接读文件路径 / 各关键词命中
- 相等性
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from ai_rd_team.artifacts.layout import (
    DEFAULT_LAYOUTS,
    VALID_DOC_CATEGORIES,
    VALID_PROCESS_KINDS,
    VALID_TESTS_MODES,
    ProjectLayout,
    from_memory,
    from_yaml,
    get_default_layout,
)

# ---------------------------------------------------------------
# 默认布局
# ---------------------------------------------------------------


class TestDefaultLayouts:
    def test_all_six_presets_exist(self) -> None:
        expected = {"python", "go", "js", "vue3", "wechat-mp", "fallback"}
        assert expected.issubset(DEFAULT_LAYOUTS.keys())

    def test_all_presets_are_project_layout(self) -> None:
        for name, layout in DEFAULT_LAYOUTS.items():
            assert isinstance(layout, ProjectLayout), f"{name} is not ProjectLayout"

    def test_python_uses_separate_tests(self) -> None:
        assert DEFAULT_LAYOUTS["python"].tests_mode == "separate"
        assert DEFAULT_LAYOUTS["python"].tests_root == "tests"

    def test_go_uses_alongside_tests(self) -> None:
        assert DEFAULT_LAYOUTS["go"].tests_mode == "alongside"
        assert DEFAULT_LAYOUTS["go"].tests_root is None

    def test_wechat_mp_code_dir(self) -> None:
        assert DEFAULT_LAYOUTS["wechat-mp"].code_dirs == {"miniprogram": "miniprogram"}

    def test_fallback_is_python_like(self) -> None:
        # fallback 约定为 src/ + tests/ 的通用布局
        fb = DEFAULT_LAYOUTS["fallback"]
        assert fb.code_dirs == {"main": "src"}
        assert fb.tests_root == "tests"
        assert fb.tests_mode == "separate"

    def test_get_default_layout_unknown_returns_fallback(self) -> None:
        assert get_default_layout("does-not-exist") is DEFAULT_LAYOUTS["fallback"]

    def test_get_default_layout_case_insensitive(self) -> None:
        assert get_default_layout("Python") is DEFAULT_LAYOUTS["python"]
        assert get_default_layout("GO") is DEFAULT_LAYOUTS["go"]


class TestConstants:
    def test_valid_doc_categories(self) -> None:
        assert frozenset(["requirements", "design", "delivery", "research"]) == VALID_DOC_CATEGORIES

    def test_valid_process_kinds(self) -> None:
        assert frozenset(["review", "report", "log"]) == VALID_PROCESS_KINDS

    def test_valid_tests_modes(self) -> None:
        assert frozenset(["separate", "alongside"]) == VALID_TESTS_MODES


# ---------------------------------------------------------------
# with_overrides
# ---------------------------------------------------------------


class TestWithOverrides:
    def test_replaces_dict_field_entirely(self) -> None:
        base = DEFAULT_LAYOUTS["go"]
        new = base.with_overrides({"code_dirs": {"mysh": "mysh", "mysqler": "mysqler"}})
        assert new.code_dirs == {"mysh": "mysh", "mysqler": "mysqler"}
        # base 不变（frozen + replace 产生新对象）
        assert base.code_dirs == {}

    def test_replaces_scalar_field(self) -> None:
        base = DEFAULT_LAYOUTS["python"]
        new = base.with_overrides({"tests_mode": "alongside"})
        assert new.tests_mode == "alongside"
        assert new.docs_root == base.docs_root  # 未 override 的字段保持

    def test_unknown_field_is_ignored_with_warning(self, caplog) -> None:
        base = DEFAULT_LAYOUTS["python"]
        with caplog.at_level("WARNING"):
            new = base.with_overrides({"unknown_field": "x", "tests_mode": "alongside"})
        assert new.tests_mode == "alongside"
        assert any("unknown_field" in rec.message for rec in caplog.records)

    def test_empty_overrides_returns_equivalent(self) -> None:
        base = DEFAULT_LAYOUTS["python"]
        new = base.with_overrides({})
        assert new == base


# ---------------------------------------------------------------
# from_yaml
# ---------------------------------------------------------------


class TestFromYaml:
    def test_base_plus_overrides_merge(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "data-project-layout.yaml"
        yaml_path.write_text(
            """
version: "1.0"
base: go
overrides:
  code_dirs:
    mysh: mysh
    mysqler: mysqler
  tests_mode: alongside
""",
            encoding="utf-8",
        )
        layout = from_yaml(yaml_path)
        assert layout.tests_mode == "alongside"
        assert layout.code_dirs == {"mysh": "mysh", "mysqler": "mysqler"}
        # base(go) 继承的字段
        assert layout.docs_root == DEFAULT_LAYOUTS["go"].docs_root
        assert layout.tests_root is None

    def test_base_only_no_overrides(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "layout.yaml"
        yaml_path.write_text("base: python\n", encoding="utf-8")
        layout = from_yaml(yaml_path)
        assert layout == DEFAULT_LAYOUTS["python"]

    def test_file_not_found_returns_fallback(self, tmp_path: Path) -> None:
        layout = from_yaml(tmp_path / "does-not-exist.yaml")
        assert layout is DEFAULT_LAYOUTS["fallback"]

    def test_invalid_yaml_returns_fallback(self, tmp_path: Path, caplog) -> None:
        yaml_path = tmp_path / "bad.yaml"
        yaml_path.write_text("base: [unclosed", encoding="utf-8")
        with caplog.at_level("WARNING"):
            layout = from_yaml(yaml_path)
        assert layout is DEFAULT_LAYOUTS["fallback"]
        assert any("fallback" in rec.message for rec in caplog.records)

    def test_yaml_not_a_mapping_returns_fallback(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "bad.yaml"
        yaml_path.write_text("- item1\n- item2\n", encoding="utf-8")
        layout = from_yaml(yaml_path)
        assert layout is DEFAULT_LAYOUTS["fallback"]

    def test_unknown_base_treated_as_fallback(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "layout.yaml"
        yaml_path.write_text("base: rust\n", encoding="utf-8")
        layout = from_yaml(yaml_path)
        assert layout == DEFAULT_LAYOUTS["fallback"]

    def test_overrides_not_a_mapping_uses_base_only(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "layout.yaml"
        yaml_path.write_text("base: go\noverrides: nope\n", encoding="utf-8")
        layout = from_yaml(yaml_path)
        assert layout == DEFAULT_LAYOUTS["go"]

    def test_unknown_field_in_overrides_ignored(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "layout.yaml"
        yaml_path.write_text(
            "base: go\noverrides:\n  code_dir: {a: b}\n  tests_mode: alongside\n",
            encoding="utf-8",
        )
        layout = from_yaml(yaml_path)
        # code_dir 拼错被忽略；tests_mode 生效
        assert layout.code_dirs == DEFAULT_LAYOUTS["go"].code_dirs
        assert layout.tests_mode == "alongside"


# ---------------------------------------------------------------
# from_memory
# ---------------------------------------------------------------


class _FakeMemory:
    """最小 memory mock：只暴露 workspace_memory_dir，让 from_memory 走文件分支。"""

    def __init__(self, workspace_memory_dir: Path) -> None:
        self.workspace_memory_dir = workspace_memory_dir


def _write_tech_stack(memory_dir: Path, body: str) -> None:
    target = memory_dir / "agent.d" / "tech-stack-selected.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


class TestFromMemory:
    def test_none_memory_returns_fallback(self) -> None:
        assert from_memory(None) is DEFAULT_LAYOUTS["fallback"]

    def test_no_file_returns_fallback(self, tmp_path: Path) -> None:
        mm = _FakeMemory(workspace_memory_dir=tmp_path / "memory")
        assert from_memory(mm) is DEFAULT_LAYOUTS["fallback"]

    @pytest.mark.parametrize(
        "text,expected_key",
        [
            ("# 技术栈\n\n使用 Go + Kratos 框架", "go"),
            ("- 语言：Python 3.10+\n- 依赖：stdlib", "python"),
            ("前端使用 Vue 3 + Pinia", "vue3"),
            ("微信小程序 + 云开发", "wechat-mp"),
            ("Backend: Node.js + TypeScript", "js"),
            ("这是一个嵌入式 C 项目", "fallback"),
        ],
    )
    def test_keyword_inference(self, tmp_path: Path, text: str, expected_key: str) -> None:
        mm = _FakeMemory(workspace_memory_dir=tmp_path / "memory")
        _write_tech_stack(tmp_path / "memory", text)
        layout = from_memory(mm)
        assert layout == DEFAULT_LAYOUTS[expected_key], (
            f"text={text!r} expected={expected_key} got={layout}"
        )

    def test_wechat_mp_beats_js(self, tmp_path: Path) -> None:
        # 同时提到 TypeScript 和微信小程序 → 小程序优先（避免 js 误命中）
        mm = _FakeMemory(workspace_memory_dir=tmp_path / "memory")
        _write_tech_stack(
            tmp_path / "memory",
            "微信小程序 + TypeScript 云开发",
        )
        assert from_memory(mm) == DEFAULT_LAYOUTS["wechat-mp"]


# ---------------------------------------------------------------
# 相等性 & 不可变性
# ---------------------------------------------------------------


class TestEquality:
    def test_two_default_layouts_of_same_preset_are_equal(self) -> None:
        # DEFAULT_LAYOUTS 是同一实例，但我们也验证"结构相等"
        a = DEFAULT_LAYOUTS["go"]
        b = DEFAULT_LAYOUTS["go"]
        assert a == b
        assert a is b

    def test_with_overrides_produces_new_object(self) -> None:
        base = DEFAULT_LAYOUTS["python"]
        new = base.with_overrides({"tests_mode": "alongside"})
        assert new is not base
        assert new != base

    def test_frozen_prevents_mutation(self) -> None:
        layout = DEFAULT_LAYOUTS["python"]
        with pytest.raises(FrozenInstanceError):
            layout.docs_root = "other"  # type: ignore[misc]
