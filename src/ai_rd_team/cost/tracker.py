"""CostTracker：成本追踪 + 预算控制 + 模型降级（T2.7-T2.10）。

对应设计文档：openspec/specs/design/08-cost-control.md

核心组件：
- ``CostSnapshot``：某时刻的成本快照
- ``BudgetAction``：预算检查结果（continue/warn/smart_pause/block）
- ``CostTracker``：实时计量 + 预算检查 + 模型降级提示
- ``QuotaTracker``：日/周/月窗口额度（全局文件存储）

第一期（M2）范围：
- ✅ 5 类事件计量（spawn/message/broadcast/minute/iteration）
- ✅ 实时写 runtime/cost/resource-points.yaml
- ✅ 预算达标时触发 smart_pause（引擎处理）
- ✅ 多窗口额度记录
- ✅ 模型降级 semi_auto：达 75% 时发出建议（通过事件 + 记录，不直接切换）

不做（第一期限制）：
- ❌ 实际切换 CodeBuddy 模型（需要主 Agent 人工 /switch）
- ❌ 精确 token 计费（CodeBuddy 未暴露 API）
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

import yaml

from ai_rd_team.config.models import CostControl, RunMode
from ai_rd_team.runtime.state import utc_now_iso
from ai_rd_team.utils.file_ops import atomic_write, locked_append

logger = logging.getLogger(__name__)


class BudgetAction(str, Enum):
    """预算检查结果。"""

    CONTINUE = "continue"
    WARN = "warn"
    SMART_PAUSE = "smart_pause"
    BLOCK = "block"


class BudgetReason(str, Enum):
    """触发 smart_pause / block 的原因。"""

    RP_EXCEEDED = "rp_exceeded"
    RP_WARN_THRESHOLD = "rp_warn_threshold"
    MAX_MEMBERS = "max_members"
    MAX_MESSAGES = "max_messages"
    MAX_BROADCASTS = "max_broadcasts"
    MAX_RUNTIME = "max_runtime"
    MAX_ITERATIONS = "max_iterations"
    DAY_QUOTA = "day_quota"
    WEEK_QUOTA = "week_quota"
    MONTH_QUOTA = "month_quota"
    NONE = "none"


@dataclass
class CostSnapshot:
    """某时刻的成本快照（可变，便于累加）。"""

    run_id: str
    mode: RunMode
    started_at: str  # ISO 8601 UTC
    updated_at: str  # ISO 8601 UTC

    # 计数
    member_spawn_count: int = 0
    message_count: int = 0
    broadcast_count: int = 0  # 广播次数
    broadcast_target_count: int = 0  # 广播实际目标总数
    runtime_minutes: float = 0.0
    iteration_count: int = 0

    # Resource Points
    resource_points: int = 0
    rp_budget: int = 0  # 档位上限
    rp_usage_ratio: float = 0.0  # 0.0 - 1.0+

    # 窗口剩余（由 QuotaTracker 填充）
    day_used: int = 0
    week_used: int = 0
    month_used: int = 0
    day_remaining: int = 0
    week_remaining: int = 0
    month_remaining: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BudgetCheckResult:
    """预算检查的完整结果。"""

    action: BudgetAction
    reason: BudgetReason
    message: str  # 人类可读
    snapshot: CostSnapshot


# -----------------------------------------------------------------
# QuotaTracker（T2.9）
# -----------------------------------------------------------------

QUOTA_HISTORY_FILENAME = "quota-history.jsonl"


@dataclass
class QuotaTracker:
    """跨运行的时间窗口额度追踪（T2.9）。

    存储路径：``~/.ai-rd-team/quota-history.jsonl``（可被 home_dir 覆盖）
    每次 ``record_run_end`` 追加一条记录：``{ts, run_id, rp}``
    查询时读取最近 N 天，按窗口聚合。
    """

    home_dir: Path | None = None

    def __post_init__(self) -> None:
        if self.home_dir is None:
            self.home_dir = Path.home() / ".ai-rd-team"

    # --- 只读查询 ---

    def used_in_window(self, days: int) -> int:
        """返回最近 ``days`` 天内累计的 RP。"""
        if days <= 0:
            return 0
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        total = 0
        for entry in self._read_entries():
            try:
                ts = datetime.fromisoformat(entry["ts"])
            except (KeyError, ValueError):
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                total += int(entry.get("rp", 0))
        return total

    def day_used(self) -> int:
        return self.used_in_window(days=1)

    def week_used(self) -> int:
        return self.used_in_window(days=7)

    def month_used(self) -> int:
        return self.used_in_window(days=30)

    # --- 写入 ---

    def record_run_end(self, run_id: str, rp_used: int) -> None:
        """一次运行结束后写入额度累计。"""
        assert self.home_dir is not None
        self.home_dir.mkdir(parents=True, exist_ok=True)
        path = self.home_dir / QUOTA_HISTORY_FILENAME
        entry = {
            "ts": utc_now_iso(),
            "run_id": run_id,
            "rp": int(rp_used),
        }
        locked_append(path, json.dumps(entry, ensure_ascii=False) + "\n")

    def _read_entries(self) -> list[dict]:
        assert self.home_dir is not None
        path = self.home_dir / QUOTA_HISTORY_FILENAME
        if not path.is_file():
            return []
        entries: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                logger.warning("skip malformed quota-history line: %s", line[:80])
        return entries


# -----------------------------------------------------------------
# CostTracker（T2.7 + T2.8 + T2.10）
# -----------------------------------------------------------------


@dataclass
class CostTracker:
    """成本追踪器。

    典型用法::

        tracker = CostTracker(config=cost_config, cost_dir=runtime/cost)
        tracker.start_run(run_id="abc", mode="standard")

        # 事件发生时
        tracker.record_spawn()
        tracker.record_message(...)

        # 每 10 秒更新一次运行时长
        tracker.update_runtime()

        # 决定是否继续
        result = tracker.check_budget()
        if result.action != BudgetAction.CONTINUE:
            engine.handle_budget_breach(result)

        tracker.end_run()
    """

    config: CostControl
    cost_dir: Path
    quota_tracker: QuotaTracker | None = None

    # 内部状态（运行中）
    _snapshot: CostSnapshot | None = field(default=None, init=False)
    _start_dt: datetime | None = field(default=None, init=False)
    _warned_threshold: bool = field(default=False, init=False)
    _fallback_suggested: bool = field(default=False, init=False)

    # -----------------------------------------------------------------
    # 生命周期
    # -----------------------------------------------------------------

    def start_run(self, run_id: str, mode: RunMode) -> CostSnapshot:
        """开始一次运行的成本追踪。"""
        self.cost_dir.mkdir(parents=True, exist_ok=True)
        self._start_dt = datetime.now(timezone.utc)
        now_iso = utc_now_iso()

        budget = self._budget_for_mode(mode)
        self._snapshot = CostSnapshot(
            run_id=run_id,
            mode=mode,
            started_at=now_iso,
            updated_at=now_iso,
            rp_budget=budget.max_resource_points,
        )
        self._warned_threshold = False
        self._fallback_suggested = False
        self._refresh_quota_state()
        self._persist()
        return self._snapshot

    def end_run(self) -> CostSnapshot:
        """结束运行：返回最终快照 + 写入额度历史。"""
        snap = self.require_snapshot()
        snap.updated_at = utc_now_iso()
        self._persist()

        if self.quota_tracker is not None:
            self.quota_tracker.record_run_end(run_id=snap.run_id, rp_used=snap.resource_points)
        return snap

    # -----------------------------------------------------------------
    # 记录事件（5 类）
    # -----------------------------------------------------------------

    def record_spawn(self, count: int = 1) -> None:
        snap = self.require_snapshot()
        snap.member_spawn_count += count
        self._add_rp(self.config.resource_point_weights.per_member_spawn * count)

    def record_message(
        self,
        from_: str = "",
        to: str = "",
        msg_type: str = "message",
    ) -> None:
        snap = self.require_snapshot()
        snap.message_count += 1
        self._add_rp(self.config.resource_point_weights.per_message)

    def record_broadcast(self, recipient_count: int) -> None:
        snap = self.require_snapshot()
        snap.broadcast_count += 1
        snap.broadcast_target_count += recipient_count
        self._add_rp(self.config.resource_point_weights.per_broadcast_target * recipient_count)

    def record_iteration(self, iteration_type: str = "review") -> None:
        snap = self.require_snapshot()
        snap.iteration_count += 1
        self._add_rp(self.config.resource_point_weights.per_iteration)

    def update_runtime(self) -> None:
        """刷新运行时长（引擎定期调用，如每 10 秒）。"""
        snap = self.require_snapshot()
        if self._start_dt is None:
            return
        now = datetime.now(timezone.utc)
        minutes = (now - self._start_dt).total_seconds() / 60.0
        delta = max(0.0, minutes - snap.runtime_minutes)
        snap.runtime_minutes = minutes
        added = int(delta * self.config.resource_point_weights.per_minute_runtime)
        if added > 0:
            self._add_rp(added)
        else:
            # 刷新 updated_at
            self._snapshot_touch()

    # -----------------------------------------------------------------
    # 查询
    # -----------------------------------------------------------------

    def snapshot(self) -> CostSnapshot | None:
        return self._snapshot

    def require_snapshot(self) -> CostSnapshot:
        if self._snapshot is None:
            raise RuntimeError("CostTracker.start_run not called")
        return self._snapshot

    # -----------------------------------------------------------------
    # 预算检查（T2.8）
    # -----------------------------------------------------------------

    def check_budget(self) -> BudgetCheckResult:
        """根据当前快照返回应采取的动作。

        优先级：
          1. 日/周/月窗口耗尽 → BLOCK
          2. RP 超档位上限 → SMART_PAUSE
          3. 任一硬限超标（members/messages/runtime/iterations）→ SMART_PAUSE
          4. RP ≥ fallback_threshold 且未警告过 → WARN（建议降级）
          5. 其他 → CONTINUE
        """
        snap = self.require_snapshot()
        budget = self._budget_for_mode(snap.mode)

        # 1. 窗口额度
        if snap.day_remaining <= 0 and self.config.quota_enabled:
            return self._result(
                BudgetAction.BLOCK,
                BudgetReason.DAY_QUOTA,
                f"日额度已耗尽（used={snap.day_used}，windows={self.config.quota_windows.per_day}）",
            )
        if snap.week_remaining <= 0 and self.config.quota_enabled:
            return self._result(
                BudgetAction.BLOCK,
                BudgetReason.WEEK_QUOTA,
                "周额度已耗尽",
            )
        if snap.month_remaining <= 0 and self.config.quota_enabled:
            return self._result(
                BudgetAction.BLOCK,
                BudgetReason.MONTH_QUOTA,
                "月额度已耗尽",
            )

        # 2. RP 超档位
        if snap.resource_points >= budget.max_resource_points:
            return self._result(
                BudgetAction.SMART_PAUSE,
                BudgetReason.RP_EXCEEDED,
                f"RP 已达上限 {snap.resource_points}/{budget.max_resource_points}",
            )

        # 3. 硬限
        if snap.member_spawn_count > budget.max_members:
            return self._result(
                BudgetAction.SMART_PAUSE,
                BudgetReason.MAX_MEMBERS,
                f"成员数超限 {snap.member_spawn_count}/{budget.max_members}",
            )
        if snap.message_count > budget.max_messages:
            return self._result(
                BudgetAction.SMART_PAUSE,
                BudgetReason.MAX_MESSAGES,
                f"消息数超限 {snap.message_count}/{budget.max_messages}",
            )
        if budget.max_broadcasts > 0 and snap.broadcast_count > budget.max_broadcasts:
            return self._result(
                BudgetAction.SMART_PAUSE,
                BudgetReason.MAX_BROADCASTS,
                f"广播次数超限 {snap.broadcast_count}/{budget.max_broadcasts}",
            )
        if snap.runtime_minutes > budget.max_runtime_minutes:
            return self._result(
                BudgetAction.SMART_PAUSE,
                BudgetReason.MAX_RUNTIME,
                f"运行时长超限 {snap.runtime_minutes:.1f}/{budget.max_runtime_minutes}分钟",
            )
        if snap.iteration_count > budget.max_total_iterations:
            return self._result(
                BudgetAction.SMART_PAUSE,
                BudgetReason.MAX_ITERATIONS,
                f"迭代次数超限 {snap.iteration_count}/{budget.max_total_iterations}",
            )

        # 4. 模型降级建议（T2.10）
        if (
            self.config.model_fallback.enabled
            and not self._warned_threshold
            and snap.rp_usage_ratio >= self.config.model_fallback.trigger_threshold
        ):
            self._warned_threshold = True
            return self._result(
                BudgetAction.WARN,
                BudgetReason.RP_WARN_THRESHOLD,
                (
                    f"RP 已达预算 {int(snap.rp_usage_ratio * 100)}%"
                    f"（{snap.resource_points}/{budget.max_resource_points}），"
                    f"建议切换更低成本模型"
                ),
            )

        return self._result(BudgetAction.CONTINUE, BudgetReason.NONE, "预算正常")

    def suggest_model_fallback(self) -> str | None:
        """T2.10 模型降级 semi_auto：返回建议切换到的下一个模型。

        第一期返回建议，不实际切换（主 Agent 需手动 /switch）。
        """
        if not self.config.model_fallback.enabled:
            return None
        if self._fallback_suggested:
            return None
        chain = list(self.config.model_fallback.model_chain)
        if len(chain) < 2:
            return None
        # 简化：假设当前在 chain[0]，建议 chain[1]
        self._fallback_suggested = True
        return chain[1]

    # -----------------------------------------------------------------
    # 持久化
    # -----------------------------------------------------------------

    def _persist(self) -> None:
        snap = self.require_snapshot()
        path = self.cost_dir / "resource-points.yaml"
        atomic_write(
            path,
            yaml.safe_dump(snap.to_dict(), allow_unicode=True, sort_keys=False),
        )

    def write_post_run_record(
        self,
        ended_at: str | None = None,
        user_satisfaction: str | None = None,
        actual_tokens_reported: int | None = None,
        actual_cost_reported: float | None = None,
        notes: str = "",
    ) -> None:
        """写一条 post-run.jsonl 记录（供后续校准 RP 权重）。"""
        snap = self.require_snapshot()
        entry: dict = {
            "run_id": snap.run_id,
            "ended_at": ended_at or utc_now_iso(),
            "mode": snap.mode,
            "rp_used": snap.resource_points,
            "members_spawned": snap.member_spawn_count,
            "messages": snap.message_count,
            "broadcasts": snap.broadcast_count,
            "minutes": round(snap.runtime_minutes, 2),
            "iterations": snap.iteration_count,
        }
        if user_satisfaction:
            entry["user_satisfaction"] = user_satisfaction
        if actual_tokens_reported is not None:
            entry["actual_tokens_reported"] = actual_tokens_reported
        if actual_cost_reported is not None:
            entry["actual_cost_reported"] = actual_cost_reported
        if notes:
            entry["notes"] = notes

        path = self.cost_dir / "post-run.jsonl"
        locked_append(path, json.dumps(entry, ensure_ascii=False) + "\n")

    # -----------------------------------------------------------------
    # 内部
    # -----------------------------------------------------------------

    def _budget_for_mode(self, mode: RunMode):  # type: ignore[no-untyped-def]
        mapping = {
            "lite": self.config.budget_lite,
            "standard": self.config.budget_standard,
            "full": self.config.budget_full,
        }
        return mapping[mode]

    def raise_rp_budget(self, new_value: int) -> int:
        """提高当前 run 所属档位的 RP 硬限（T3.8b smart_pause 的 raise_budget 动作）。

        - 通过 dataclasses.replace 重建 Budget / CostControl（避免 frozen 限制）
        - 同步更新 snapshot.rp_budget + rp_usage_ratio
        - 重置 smart_pause 的一次性标志，让新预算下重新告警
        - 返回实际生效的新值

        Args:
            new_value: 新的 max_resource_points，必须大于当前值
        """
        import dataclasses

        snap = self.require_snapshot()
        if new_value <= snap.rp_budget:
            raise ValueError(
                f"new rp budget ({new_value}) must be greater than current ({snap.rp_budget})"
            )

        # 重建对应 mode 的 Budget 对象
        field_name = f"budget_{snap.mode}"
        old_budget = getattr(self.config, field_name)
        new_budget = dataclasses.replace(old_budget, max_resource_points=new_value)
        self.config = dataclasses.replace(self.config, **{field_name: new_budget})

        # 更新 snapshot
        snap.rp_budget = new_value
        if new_value > 0:
            snap.rp_usage_ratio = snap.resource_points / new_value

        # 重置一次性告警标志（让新预算下重新评估 WARN 阈值）
        self._warned_threshold = False
        self._fallback_suggested = False

        self._snapshot_touch()
        return new_value

    def _add_rp(self, delta: int) -> None:
        snap = self.require_snapshot()
        snap.resource_points += max(0, delta)
        if snap.rp_budget > 0:
            snap.rp_usage_ratio = snap.resource_points / snap.rp_budget
        self._snapshot_touch()

    def _snapshot_touch(self) -> None:
        snap = self.require_snapshot()
        snap.updated_at = utc_now_iso()
        self._refresh_quota_remaining()
        self._persist()

    def _refresh_quota_state(self) -> None:
        if self.quota_tracker is None:
            return
        self._refresh_quota_remaining()

    def _refresh_quota_remaining(self) -> None:
        if self.quota_tracker is None or self._snapshot is None:
            return
        snap = self._snapshot
        win = self.config.quota_windows
        snap.day_used = self.quota_tracker.day_used() + snap.resource_points
        snap.week_used = self.quota_tracker.week_used() + snap.resource_points
        snap.month_used = self.quota_tracker.month_used() + snap.resource_points
        snap.day_remaining = max(0, win.per_day - snap.day_used)
        snap.week_remaining = max(0, win.per_week - snap.week_used)
        snap.month_remaining = max(0, win.per_month - snap.month_used)

    def _result(
        self,
        action: BudgetAction,
        reason: BudgetReason,
        message: str,
    ) -> BudgetCheckResult:
        return BudgetCheckResult(
            action=action,
            reason=reason,
            message=message,
            snapshot=self.require_snapshot(),
        )


__all__ = [
    "BudgetAction",
    "BudgetCheckResult",
    "BudgetReason",
    "CostSnapshot",
    "CostTracker",
    "QUOTA_HISTORY_FILENAME",
    "QuotaTracker",
]
