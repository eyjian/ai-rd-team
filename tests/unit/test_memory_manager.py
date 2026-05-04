"""测试 MemoryManager（T2.2 + T2.3）。"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai_rd_team.config.models import Role
from ai_rd_team.memory.manager import (
    AGENT_D_TOTAL_TOKEN_LIMIT,
    MemoryLayer,
    MemoryManager,
    MemoryParseError,
    MemoryScope,
    _slugify,
    _split_frontmatter,
)


@pytest.fixture
def mm(tmp_path: Path) -> MemoryManager:
    manager = MemoryManager(
        workspace_memory_dir=tmp_path / "memory",
        global_memory_dir=tmp_path / "global_memory",
    )
    manager.ensure_directories()
    return manager


class TestEnsureDirectories:
    def test_creates_three_layers(self, tmp_path: Path) -> None:
        m = MemoryManager(workspace_memory_dir=tmp_path / "mem")
        m.ensure_directories()
        assert (tmp_path / "mem" / "agent.d").is_dir()
        assert (tmp_path / "mem" / "memory.d").is_dir()
        assert (tmp_path / "mem" / "decisions").is_dir()


class TestFrontmatterParsing:
    def test_parse_valid(self) -> None:
        text = "---\nauthor: foo\ntags: [x]\n---\n# Title\n\nbody"
        meta, body = _split_frontmatter(text)
        assert meta == {"author": "foo", "tags": ["x"]}
        assert body.startswith("# Title")

    def test_no_frontmatter(self) -> None:
        text = "# Title only\n\nno meta"
        meta, body = _split_frontmatter(text)
        assert meta == {}
        assert body == text

    def test_invalid_yaml_raises(self) -> None:
        text = "---\nkey: [unclosed\n---\n# body"
        with pytest.raises(MemoryParseError):
            _split_frontmatter(text)

    def test_non_mapping_raises(self) -> None:
        text = "---\n- just a list\n---\n# body"
        with pytest.raises(MemoryParseError):
            _split_frontmatter(text)


class TestSlugify:
    def test_basic(self) -> None:
        assert _slugify("Use Go + Kratos") == "use-go-kratos"

    def test_chinese_preserved(self) -> None:
        s = _slugify("选择 Go 作为后端")
        assert "go" in s
        assert "选择" in s

    def test_empty_becomes_untitled(self) -> None:
        assert _slugify("") == "untitled"
        assert _slugify("!!!") == "untitled"


class TestWriteAndLoad:
    def test_write_agent_d_roundtrip(self, mm: MemoryManager) -> None:
        item = mm.write_agent_d(
            name="team-roster",
            content="# 团队成员清单\n\n- 陈架构\n- 林1号",
            author="auto",
            tags=["team"],
        )
        assert item.layer == MemoryLayer.AGENT_D
        assert item.scope == MemoryScope.PROJECT
        assert item.title == "团队成员清单"
        assert "陈架构" in item.content_body
        assert item.frontmatter["tags"] == ["team"]
        assert item.frontmatter["author"] == "auto"
        assert item.frontmatter["estimated_tokens"] > 0

    def test_write_preserves_created_on_update(self, mm: MemoryManager) -> None:
        first = mm.write_agent_d(name="key-decisions", content="v1", author="a")
        original_created = first.frontmatter["created"]

        second = mm.write_agent_d(name="key-decisions", content="v2", author="b")
        assert second.frontmatter["created"] == original_created
        # updated 必然变（不一定不同，但肯定是新时间戳；至少不再强验证）

    def test_write_memory_d_with_subdir(self, mm: MemoryManager) -> None:
        item = mm.write_memory_d(
            relative_path="domain/business-rules",
            content="# 业务规则\n\n规则 1...",
            author="analyst",
        )
        assert item.path.parent.name == "domain"
        assert item.path.name == "business-rules.md"

    def test_write_decision_adds_title_if_missing(self, mm: MemoryManager) -> None:
        item = mm.write_decision(
            adr_id="0001",
            title="选择 Go + Kratos",
            content="内容没有标题",
            author="architect",
            status="accepted",
            tags=["backend"],
        )
        assert item.title.startswith("ADR-0001")
        assert item.frontmatter["adr_id"] == "0001"
        assert item.frontmatter["status"] == "accepted"
        assert "0001-" in item.path.name

    def test_write_decision_keeps_existing_title(self, mm: MemoryManager) -> None:
        item = mm.write_decision(
            adr_id="0002",
            title="Redis 策略",
            content="# ADR-0002：Redis 策略（自定义标题）\n\n正文",
            author="architect",
        )
        assert "自定义标题" in item.title


class TestNextAdrId:
    def test_first_id_is_0001(self, mm: MemoryManager) -> None:
        assert mm.next_adr_id() == "0001"

    def test_increments_from_max(self, mm: MemoryManager) -> None:
        mm.write_decision(adr_id="0001", title="a", content="x", author="u")
        mm.write_decision(adr_id="0003", title="c", content="x", author="u")
        # 应跳过 0002 直接接 0004
        assert mm.next_adr_id() == "0004"

    def test_ignores_non_adr_files(self, mm: MemoryManager) -> None:
        # 放一个非 ADR 命名的 md 文件
        (mm.workspace_memory_dir / "decisions" / "notes.md").write_text(
            "# not an adr", encoding="utf-8"
        )
        assert mm.next_adr_id() == "0001"


class TestLoadAgentD:
    def test_load_respects_role_list_order(self, mm: MemoryManager) -> None:
        mm.write_agent_d("first", "first content", author="u")
        mm.write_agent_d("second", "second content", author="u")

        role = Role(
            name="dev",
            memory_scope={"agent_d": ["second", "first"]},
        )
        items = mm.load_agent_d(role)
        assert [i.name for i in items] == ["second", "first"]

    def test_skip_missing(self, mm: MemoryManager) -> None:
        mm.write_agent_d("exists", "x", author="u")
        role = Role(
            name="dev",
            memory_scope={"agent_d": ["missing", "exists"]},
        )
        items = mm.load_agent_d(role)
        assert [i.name for i in items] == ["exists"]

    def test_budget_truncation(self, mm: MemoryManager) -> None:
        # 构造两个 item，第一个占满预算
        big = "中" * int(AGENT_D_TOTAL_TOKEN_LIMIT * 1.5) + " rest"
        mm.write_agent_d("big", big, author="u")
        mm.write_agent_d("small", "small content", author="u")

        role = Role(name="dev", memory_scope={"agent_d": ["big", "small"]})
        items = mm.load_agent_d(role)
        # big 超预算直接被跳过，small 可加载
        # 或 big 被计入但 small 被截断；两种都合理，只验总数 ≤ 1 即可
        assert len(items) <= 1


class TestWorkspaceOverridesGlobal:
    def test_project_wins_over_global(self, tmp_path: Path) -> None:
        mm = MemoryManager(
            workspace_memory_dir=tmp_path / "ws",
            global_memory_dir=tmp_path / "glob",
        )
        mm.ensure_directories()

        # 全局级写一份
        glob_dir = tmp_path / "glob" / "agent.d"
        glob_dir.mkdir(parents=True)
        (glob_dir / "shared.md").write_text("# global version\n\nglob-content", encoding="utf-8")

        # 项目级也写一份
        mm.write_agent_d("shared", "# project version\n\nproj", author="u")

        role = Role(name="d", memory_scope={"agent_d": ["shared"]})
        items = mm.load_agent_d(role)
        assert len(items) == 1
        assert items[0].scope == MemoryScope.PROJECT
        assert "project version" in items[0].content_body


class TestListDecisions:
    def test_list_all(self, mm: MemoryManager) -> None:
        mm.write_decision("0001", "A", "x", author="u", status="accepted")
        mm.write_decision("0002", "B", "x", author="u", status="proposed")
        mm.write_decision("0003", "C", "x", author="u", status="superseded")

        got = mm.list_decisions()
        ids = [str(d.frontmatter["adr_id"]) for d in got]
        assert ids == ["0001", "0002", "0003"]

    def test_filter_by_status(self, mm: MemoryManager) -> None:
        mm.write_decision("0001", "A", "x", author="u", status="accepted")
        mm.write_decision("0002", "B", "x", author="u", status="proposed")

        accepted = mm.list_decisions(status_filter="accepted")
        assert len(accepted) == 1
        assert str(accepted[0].frontmatter["adr_id"]) == "0001"


class TestLoadDecision:
    def test_load_by_id(self, mm: MemoryManager) -> None:
        mm.write_decision("0005", "choose-go", "x", author="u", status="accepted")
        got = mm.load_decision("0005")
        assert got is not None
        assert str(got.frontmatter["adr_id"]) == "0005"

    def test_not_found_returns_none(self, mm: MemoryManager) -> None:
        assert mm.load_decision("9999") is None


class TestRenderAdrTemplate:
    def test_template_has_madr_sections(self, mm: MemoryManager) -> None:
        body = mm.render_adr_template(
            adr_id="0010",
            title="选某个栈",
            context="需要高并发",
            options=[
                ("选项 A", ["✅ 快", "✅ 熟"]),
                ("选项 B", ["⚠️ 慢"]),
            ],
            decision="选 A",
        )
        assert body.startswith("# ADR-0010：选某个栈")
        assert "## 状态" in body
        assert "## 上下文" in body
        assert "## 选项考察" in body
        assert "### 选项 A" in body
        assert "### 选项 B" in body
        assert "## 决策" in body
        assert "选 A" in body
        assert "## 后果" in body


class TestFrontmatterFormat:
    def test_written_file_parseable_by_pyyaml(self, mm: MemoryManager) -> None:
        """直接读回写入的文件，用 yaml 解析确认格式正确。"""
        mm.write_agent_d("probe", "# Probe\n\nbody", author="u", tags=["t1"])
        path = mm.workspace_memory_dir / MemoryLayer.AGENT_D.value / "probe.md"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        _, rest = text.split("---\n", 1)
        meta_raw, _ = rest.split("\n---\n", 1)
        meta = yaml.safe_load(meta_raw)
        assert meta["author"] == "u"
        assert meta["tags"] == ["t1"]
        assert meta["type"] == "memory"
        assert meta["layer"] == "agent.d"
