"""Recorder × Layout 组合测试（M7 任务 2.8）。

test_runtime_and_artifacts.py 已经覆盖了 recorder 的核心行为，
这里聚焦"不同 ProjectLayout 下同一 write_* 方法落位差异"，
确保 DEFAULT_LAYOUTS 六档在各 write_* 方法上的路径分派正确。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_rd_team.artifacts.layout import DEFAULT_LAYOUTS, ProjectLayout
from ai_rd_team.artifacts.recorder import (
    CATEGORY_DELIVERY,
    CATEGORY_PROCESS,
    ArtifactRecorder,
)


@pytest.fixture
def recorder_factory(tmp_path: Path):
    """返回一个 factory：给定 layout 构造一个独立项目根的 recorder。"""
    counter = {"n": 0}

    def _make(layout: ProjectLayout) -> ArtifactRecorder:
        counter["n"] += 1
        project_root = tmp_path / f"proj_{counter['n']}"
        runtime_dir = project_root / ".ai-rd-team" / "runtime"
        project_root.mkdir(parents=True, exist_ok=True)
        return ArtifactRecorder(
            project_root=project_root,
            runtime_dir=runtime_dir,
            layout=layout,
        )

    return _make


# ---------------------------------------------------------------
# write_code × layout
# ---------------------------------------------------------------


class TestWriteCodeAcrossLayouts:
    def test_python_layout_maps_main_to_src(self, recorder_factory) -> None:
        rec = recorder_factory(DEFAULT_LAYOUTS["python"])
        path = rec.write_code(module="main", filename="app.py", content="", producer="d1")
        assert path.parent == rec.project_root / "src"

    def test_go_layout_falls_back_to_module_name(self, recorder_factory) -> None:
        # Go 默认 code_dirs 空，module 直接当目录名
        rec = recorder_factory(DEFAULT_LAYOUTS["go"])
        path = rec.write_code(module="mysh", filename="main.go", content="", producer="d1")
        assert path.parent == rec.project_root / "mysh"

    def test_js_layout_maps_main_to_src(self, recorder_factory) -> None:
        rec = recorder_factory(DEFAULT_LAYOUTS["js"])
        path = rec.write_code(module="main", filename="index.ts", content="", producer="d1")
        assert path.parent == rec.project_root / "src"

    def test_vue3_layout_maps_frontend_to_src(self, recorder_factory) -> None:
        rec = recorder_factory(DEFAULT_LAYOUTS["vue3"])
        path = rec.write_code(module="frontend", filename="App.vue", content="", producer="d1")
        assert path.parent == rec.project_root / "src"

    def test_wechat_mp_layout_keeps_miniprogram(self, recorder_factory) -> None:
        rec = recorder_factory(DEFAULT_LAYOUTS["wechat-mp"])
        path = rec.write_code(
            module="miniprogram",
            filename="app.js",
            content="",
            producer="d1",
        )
        assert path.parent == rec.project_root / "miniprogram"


# ---------------------------------------------------------------
# write_test × layout
# ---------------------------------------------------------------


class TestWriteTestAcrossLayouts:
    def test_python_separate_tests_root(self, recorder_factory) -> None:
        rec = recorder_factory(DEFAULT_LAYOUTS["python"])
        path = rec.write_test(module=None, filename="test_x.py", content="", producer="tester")
        assert path.parent == rec.project_root / "tests"

    def test_go_alongside_code(self, recorder_factory) -> None:
        rec = recorder_factory(DEFAULT_LAYOUTS["go"])
        path = rec.write_test(module="mysh", filename="x_test.go", content="", producer="tester")
        assert path.parent == rec.project_root / "mysh"

    def test_js_separate_tests_root(self, recorder_factory) -> None:
        rec = recorder_factory(DEFAULT_LAYOUTS["js"])
        path = rec.write_test(
            module=None,
            filename="index.test.ts",
            content="",
            producer="tester",
        )
        assert path.parent == rec.project_root / "tests"

    def test_alongside_without_module_raises_across_layouts(self, recorder_factory) -> None:
        # 构造一个 alongside 的 python layout（非默认）
        layout = DEFAULT_LAYOUTS["python"].with_overrides({"tests_mode": "alongside"})
        rec = recorder_factory(layout)
        with pytest.raises(ValueError, match="alongside mode requires module"):
            rec.write_test(module=None, filename="x.py", content="", producer="tester")


# ---------------------------------------------------------------
# write_doc × layout
# ---------------------------------------------------------------


class TestWriteDocAcrossLayouts:
    def test_default_docs_root_is_docs(self, recorder_factory) -> None:
        rec = recorder_factory(DEFAULT_LAYOUTS["fallback"])
        path = rec.write_doc(
            category="design",
            filename="A.md",
            content="",
            producer="architect",
        )
        assert path.parent == rec.project_root / "docs" / "design"

    def test_custom_docs_root_override(self, recorder_factory) -> None:
        layout = DEFAULT_LAYOUTS["fallback"].with_overrides({"docs_root": "documentation"})
        rec = recorder_factory(layout)
        path = rec.write_doc(
            category="design",
            filename="A.md",
            content="",
            producer="architect",
        )
        assert path.parent == rec.project_root / "documentation" / "design"

    def test_custom_category_subdir_override(self, recorder_factory) -> None:
        layout = DEFAULT_LAYOUTS["fallback"].with_overrides(
            {
                "docs_subdirs": {
                    "design": "arch",
                    "requirements": "req",
                    "delivery": "final",
                    "research": "rnd",
                }
            }
        )
        rec = recorder_factory(layout)
        path = rec.write_doc(
            category="requirements",
            filename="R.md",
            content="",
            producer="analyst",
        )
        assert path.parent == rec.project_root / "docs" / "req"


# ---------------------------------------------------------------
# write_deploy × layout
# ---------------------------------------------------------------


class TestWriteDeployAcrossLayouts:
    def test_custom_root_level_files_list(self, recorder_factory) -> None:
        layout = DEFAULT_LAYOUTS["fallback"].with_overrides({"root_level_files": ["boot.sh"]})
        rec = recorder_factory(layout)
        # boot.sh 在白名单 → 根
        p1 = rec.write_deploy(filename="boot.sh", content="", producer="devops")
        assert p1.parent == rec.project_root

        # Dockerfile 不在自定义白名单 → deploy/
        p2 = rec.write_deploy(filename="Dockerfile", content="", producer="devops")
        assert p2.parent == rec.project_root / "deploy"

    def test_custom_deploy_root(self, recorder_factory) -> None:
        layout = DEFAULT_LAYOUTS["fallback"].with_overrides({"deploy_root": "infra"})
        rec = recorder_factory(layout)
        path = rec.write_deploy(filename="k8s.yaml", content="", producer="devops")
        assert path.parent == rec.project_root / "infra"


# ---------------------------------------------------------------
# 跨类型 manifest 归档
# ---------------------------------------------------------------


class TestMixedManifest:
    def test_all_five_writers_in_one_manifest(self, recorder_factory) -> None:
        """一个项目混用 5 类 write_*，manifest 正确分档。"""
        rec = recorder_factory(DEFAULT_LAYOUTS["go"])

        rec.write_code(module="mysh", filename="main.go", content="", producer="d1")
        rec.write_doc(category="design", filename="A.md", content="", producer="architect")
        rec.write_test(module="mysh", filename="m_test.go", content="", producer="tester")
        rec.write_deploy(filename="Dockerfile", content="", producer="devops")
        rec.write_process(kind="review", name="spec-review", content="", producer="reviewer")

        manifest = rec.read_manifest()
        items = manifest["artifacts"]
        assert len(items) == 5

        delivery = [a for a in items if a["category"] == CATEGORY_DELIVERY]
        process = [a for a in items if a["category"] == CATEGORY_PROCESS]
        assert len(delivery) == 4  # code + doc + test + deploy
        assert len(process) == 1  # review

        kinds = {a["kind"] for a in items}
        assert kinds == {"code", "doc", "test", "deploy", "review"}

    def test_delivery_paths_are_project_relative(self, recorder_factory) -> None:
        rec = recorder_factory(DEFAULT_LAYOUTS["go"])
        rec.write_code(module="mysh", filename="main.go", content="", producer="d1")
        rec.write_deploy(filename="Dockerfile", content="", producer="devops")

        items = rec.list_artifacts(category=CATEGORY_DELIVERY)
        paths = {a["path"] for a in items}
        # 都是相对项目根的斜杠分隔路径
        assert paths == {"mysh/main.go", "Dockerfile"}

    def test_process_paths_are_runtime_relative(self, recorder_factory) -> None:
        rec = recorder_factory(DEFAULT_LAYOUTS["fallback"])
        rec.write_process(kind="review", name="r1", content="", producer="reviewer")
        rec.write_process(kind="report", name="rep1", content="", producer="pm")
        rec.write_process(kind="log", name="l1", content="", producer="pm", ext="jsonl")

        items = rec.list_artifacts(category=CATEGORY_PROCESS)
        paths = {a["path"] for a in items}
        assert paths == {
            "review/r1.md",
            "report/rep1.md",
            "log/l1.jsonl",
        }
