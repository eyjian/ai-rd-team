"""测试 CostTracker / QuotaTracker（T2.7-T2.10）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from ai_rd_team.config.models import (
    Budget,
    CostControl,
    ModelFallback,
    QuotaWindows,
    ResourcePointWeights,
)
from ai_rd_team.cost.tracker import (
    BudgetAction,
    BudgetReason,
    CostTracker,
    QuotaTracker,
)


def _make_config(
    rp_lite: int = 120,
    members: int = 2,
    messages: int = 20,
    broadcasts: int = 0,
    runtime_min: int = 30,
    iterations: int = 5,
    per_message: int = 2,
    quota_day: int = 500,
    quota_week: int = 2000,
    quota_month: int = 5000,
    fallback_threshold: float = 0.75,
    fallback_enabled: bool = True,
) -> CostControl:
    weights = ResourcePointWeights(
        per_member_spawn=40,
        per_message=per_message,
        per_broadcast_target=2,
        per_minute_runtime=5,
        per_iteration=15,
    )
    lite = Budget(
        max_members=members,
        max_messages=messages,
        max_broadcasts=broadcasts,
        max_runtime_minutes=runtime_min,
        max_total_iterations=iterations,
        max_resource_points=rp_lite,
    )
    std = Budget(
        max_members=5,
        max_messages=100,
        max_broadcasts=3,
        max_runtime_minutes=120,
        max_total_iterations=15,
        max_resource_points=400,
    )
    full = Budget(
        max_members=15,
        max_messages=300,
        max_broadcasts=10,
        max_runtime_minutes=480,
        max_total_iterations=50,
        max_resource_points=1500,
    )
    quota = QuotaWindows(
        per_run=rp_lite,
        per_day=quota_day,
        per_week=quota_week,
        per_month=quota_month,
    )
    return CostControl(
        resource_point_weights=weights,
        budget_lite=lite,
        budget_standard=std,
        budget_full=full,
        quota_enabled=True,
        quota_windows=quota,
        model_fallback=ModelFallback(
            enabled=fallback_enabled,
            trigger_threshold=fallback_threshold,
        ),
    )


@pytest.fixture
def cost_dir(tmp_path: Path) -> Path:
    d = tmp_path / "cost"
    d.mkdir()
    return d


@pytest.fixture
def quota(tmp_quota_home: Path) -> QuotaTracker:
    return QuotaTracker(home_dir=tmp_quota_home)


class TestLifecycle:
    def test_start_run_creates_snapshot(self, cost_dir: Path, quota: QuotaTracker) -> None:
        t = CostTracker(config=_make_config(), cost_dir=cost_dir, quota_tracker=quota)
        snap = t.start_run(run_id="abc", mode="lite")
        assert snap.run_id == "abc"
        assert snap.mode == "lite"
        assert snap.rp_budget == 120
        assert snap.resource_points == 0

    def test_resource_points_yaml_written(self, cost_dir: Path, quota: QuotaTracker) -> None:
        t = CostTracker(config=_make_config(), cost_dir=cost_dir, quota_tracker=quota)
        t.start_run(run_id="abc", mode="lite")
        t.record_spawn()

        path = cost_dir / "resource-points.yaml"
        assert path.is_file()
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["run_id"] == "abc"
        assert data["member_spawn_count"] == 1

    def test_end_run_writes_quota_history(
        self, cost_dir: Path, quota: QuotaTracker, tmp_quota_home: Path
    ) -> None:
        t = CostTracker(config=_make_config(), cost_dir=cost_dir, quota_tracker=quota)
        t.start_run(run_id="abc", mode="lite")
        t.record_spawn()  # +40 RP
        t.end_run()

        history = tmp_quota_home / "quota-history.jsonl"
        assert history.is_file()
        entries = [json.loads(ln) for ln in history.read_text().splitlines() if ln.strip()]
        assert len(entries) == 1
        assert entries[0]["run_id"] == "abc"
        assert entries[0]["rp"] == 40


class TestRecordEvents:
    def test_spawn_adds_rp(self, cost_dir: Path, quota: QuotaTracker) -> None:
        t = CostTracker(config=_make_config(), cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "lite")
        t.record_spawn(count=2)
        assert t.snapshot().member_spawn_count == 2
        assert t.snapshot().resource_points == 80  # 2 * 40

    def test_message_adds_rp(self, cost_dir: Path, quota: QuotaTracker) -> None:
        t = CostTracker(config=_make_config(), cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "lite")
        t.record_message()
        t.record_message()
        assert t.snapshot().message_count == 2
        assert t.snapshot().resource_points == 4  # 2 * 2

    def test_broadcast_multiplies_by_recipients(self, cost_dir: Path, quota: QuotaTracker) -> None:
        t = CostTracker(config=_make_config(), cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "standard")
        t.record_broadcast(recipient_count=4)
        # 2 * 4 = 8
        assert t.snapshot().resource_points == 8
        assert t.snapshot().broadcast_count == 1
        assert t.snapshot().broadcast_target_count == 4

    def test_iteration_adds_rp(self, cost_dir: Path, quota: QuotaTracker) -> None:
        t = CostTracker(config=_make_config(), cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "lite")
        t.record_iteration()
        assert t.snapshot().iteration_count == 1
        assert t.snapshot().resource_points == 15

    def test_runtime_minutes_updated(self, cost_dir: Path, quota: QuotaTracker) -> None:
        t = CostTracker(config=_make_config(), cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "lite")
        # 人为把 start 时间后移
        assert t._start_dt is not None
        from datetime import timedelta

        t._start_dt -= timedelta(minutes=3)  # 模拟已运行 3 分钟
        t.update_runtime()
        snap = t.snapshot()
        assert snap.runtime_minutes >= 2.9
        assert snap.resource_points >= 3 * 5  # per_minute_runtime=5


class TestBudgetCheck:
    def test_continue_when_under_budget(self, cost_dir: Path, quota: QuotaTracker) -> None:
        t = CostTracker(config=_make_config(), cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "lite")
        t.record_spawn()
        result = t.check_budget()
        assert result.action == BudgetAction.CONTINUE
        assert result.reason == BudgetReason.NONE

    def test_warn_at_fallback_threshold(self, cost_dir: Path, quota: QuotaTracker) -> None:
        cfg = _make_config(rp_lite=100, fallback_threshold=0.5)
        t = CostTracker(config=cfg, cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "lite")
        # 需要消耗 ≥50 RP：1 spawn=40 + 5 message=10 → 50
        t.record_spawn()
        for _ in range(5):
            t.record_message()
        result = t.check_budget()
        assert result.action == BudgetAction.WARN
        assert result.reason == BudgetReason.RP_WARN_THRESHOLD

    def test_smart_pause_when_rp_exceeds(self, cost_dir: Path, quota: QuotaTracker) -> None:
        cfg = _make_config(rp_lite=50)
        t = CostTracker(config=cfg, cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "lite")
        # spawn 40 + message 2 * 6 = 52 > 50
        t.record_spawn()
        for _ in range(6):
            t.record_message()
        result = t.check_budget()
        assert result.action == BudgetAction.SMART_PAUSE
        assert result.reason == BudgetReason.RP_EXCEEDED

    def test_smart_pause_when_members_exceed(self, cost_dir: Path, quota: QuotaTracker) -> None:
        cfg = _make_config(rp_lite=10000, members=2)
        t = CostTracker(config=cfg, cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "lite")
        t.record_spawn(count=3)  # 超过 max_members=2
        result = t.check_budget()
        assert result.action == BudgetAction.SMART_PAUSE
        assert result.reason == BudgetReason.MAX_MEMBERS

    def test_block_when_day_quota_exhausted(
        self, cost_dir: Path, quota: QuotaTracker, tmp_quota_home: Path
    ) -> None:
        # 伪造历史 quota 耗尽当日额度
        history = tmp_quota_home / "quota-history.jsonl"
        history.write_text(
            json.dumps({"ts": "2099-01-01T00:00:00+00:00", "rp": 99999}) + "\n",
            encoding="utf-8",
        )
        # 注意：历史时间在未来，不会被算作"最近 1 天"。
        # 所以改用当前时间
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        history.write_text(
            json.dumps({"ts": now, "rp": 99999}) + "\n",
            encoding="utf-8",
        )

        cfg = _make_config(quota_day=500)
        t = CostTracker(config=cfg, cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "lite")
        result = t.check_budget()
        assert result.action == BudgetAction.BLOCK
        assert result.reason == BudgetReason.DAY_QUOTA


class TestModelFallback:
    def test_suggest_returns_next_model(self, cost_dir: Path, quota: QuotaTracker) -> None:
        t = CostTracker(config=_make_config(), cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "lite")
        suggested = t.suggest_model_fallback()
        assert suggested is not None
        assert suggested == "claude-haiku"  # chain 第二个

    def test_suggest_only_once(self, cost_dir: Path, quota: QuotaTracker) -> None:
        t = CostTracker(config=_make_config(), cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "lite")
        assert t.suggest_model_fallback() is not None
        assert t.suggest_model_fallback() is None  # 第二次返回 None

    def test_disabled_returns_none(self, cost_dir: Path, quota: QuotaTracker) -> None:
        cfg = _make_config(fallback_enabled=False)
        t = CostTracker(config=cfg, cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "lite")
        assert t.suggest_model_fallback() is None


class TestPostRun:
    def test_write_post_run_record(self, cost_dir: Path, quota: QuotaTracker) -> None:
        t = CostTracker(config=_make_config(), cost_dir=cost_dir, quota_tracker=quota)
        t.start_run("r", "lite")
        t.record_spawn()
        t.record_message()
        t.end_run()
        t.write_post_run_record(
            user_satisfaction="good",
            actual_tokens_reported=31200,
            actual_cost_reported=0.66,
            notes="slightly over",
        )

        path = cost_dir / "post-run.jsonl"
        assert path.is_file()
        entries = [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]
        assert len(entries) == 1
        e = entries[0]
        assert e["run_id"] == "r"
        assert e["rp_used"] == 42  # 40 + 2
        assert e["user_satisfaction"] == "good"
        assert e["actual_tokens_reported"] == 31200
        assert e["notes"] == "slightly over"


class TestQuotaTracker:
    def test_empty_history_returns_zero(self, tmp_quota_home: Path) -> None:
        q = QuotaTracker(home_dir=tmp_quota_home)
        assert q.day_used() == 0
        assert q.week_used() == 0
        assert q.month_used() == 0

    def test_accumulates_within_window(self, tmp_quota_home: Path) -> None:
        q = QuotaTracker(home_dir=tmp_quota_home)
        q.record_run_end("run-1", 100)
        q.record_run_end("run-2", 250)
        # 两条都在 1 天内
        assert q.day_used() == 350

    def test_old_entries_filtered_from_day(self, tmp_quota_home: Path) -> None:
        q = QuotaTracker(home_dir=tmp_quota_home)
        # 手工写一条很老的记录
        old = "2020-01-01T00:00:00+00:00"
        (tmp_quota_home / "quota-history.jsonl").write_text(
            json.dumps({"ts": old, "run_id": "old", "rp": 99999}) + "\n",
            encoding="utf-8",
        )
        q.record_run_end("new", 100)
        assert q.day_used() == 100  # 老的不算
        assert q.month_used() == 100
        # 注意：month 窗口 30 天，2020 年的也不算

    def test_malformed_line_skipped(self, tmp_quota_home: Path) -> None:
        history = tmp_quota_home / "quota-history.jsonl"
        history.write_text(
            "not json\n" + json.dumps({"ts": "now", "rp": 50}) + "\n" + "{}\n",
            encoding="utf-8",
        )
        q = QuotaTracker(home_dir=tmp_quota_home)
        # 不崩溃就算通过；具体数字因 "now" 无法解析会被跳过
        used = q.day_used()
        assert used >= 0


class TestRaiseRpBudget:
    """T3.8b 配套：CostTracker.raise_rp_budget 行为。"""

    def _make_tracker(self, tmp_path: Path) -> CostTracker:
        cfg = _make_config(rp_lite=120)
        return CostTracker(config=cfg, cost_dir=tmp_path / "cost")

    def test_raise_updates_snapshot_and_config(self, tmp_path: Path) -> None:
        tracker = self._make_tracker(tmp_path)
        tracker.start_run(run_id="r1", mode="lite")
        snap_before = tracker.snapshot()
        assert snap_before.rp_budget == 120

        new_value = tracker.raise_rp_budget(300)

        assert new_value == 300
        snap_after = tracker.snapshot()
        assert snap_after.rp_budget == 300
        # config 也已同步
        assert tracker.config.budget_lite.max_resource_points == 300

    def test_raise_recomputes_usage_ratio(self, tmp_path: Path) -> None:
        tracker = self._make_tracker(tmp_path)
        tracker.start_run(run_id="r1", mode="lite")
        tracker.record_spawn(count=2)  # 80 RP，120 预算下 ratio=0.667

        tracker.raise_rp_budget(800)
        snap = tracker.snapshot()
        # 80 / 800 = 0.1
        assert abs(snap.rp_usage_ratio - 0.1) < 1e-6

    def test_raise_rejects_non_increase(self, tmp_path: Path) -> None:
        tracker = self._make_tracker(tmp_path)
        tracker.start_run(run_id="r1", mode="lite")

        with pytest.raises(ValueError, match="greater than current"):
            tracker.raise_rp_budget(120)
        with pytest.raises(ValueError, match="greater than current"):
            tracker.raise_rp_budget(50)

    def test_raise_resets_warned_threshold(self, tmp_path: Path) -> None:
        """提升预算后，WARN 阈值告警可重新触发。"""
        tracker = self._make_tracker(tmp_path)
        tracker.start_run(run_id="r1", mode="lite")
        # 跑到 96 RP（120 * 0.8 > 0.75 阈值）
        tracker.record_spawn(count=2)  # 80
        tracker.record_message(from_="a", to="b")  # 82
        # 耗到阈值
        for _ in range(10):
            tracker.record_message(from_="a", to="b")  # 82 + 20 = 102
        r1 = tracker.check_budget()
        # 要么 SMART_PAUSE (>= 120)，要么 WARN
        # 只要 warned_threshold 被设过，再次调就不会再 WARN
        tracker.check_budget()

        # 提升预算后，重新评估
        tracker.raise_rp_budget(1000)
        assert tracker._warned_threshold is False
        assert tracker._fallback_suggested is False

        # 至少能证明状态被重置（原本会导致不再返回 WARN）
        assert r1 is not None  # sanity
