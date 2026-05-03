"""指标收集器

在原型实验中记录各项指标到 YAML 文件，便于 REPORT.md 汇总。

使用：
    collector = MetricsCollector("01-basic-team")
    collector.record_event("member_spawned", member="architect")
    collector.record_event("message_sent", from_="architect", to="developer")
    collector.save()
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class MetricEvent:
    ts: float
    name: str
    data: dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """简单的事件记录器。"""

    def __init__(self, experiment_id: str, output_dir: Path | None = None):
        self.experiment_id = experiment_id
        self.start_ts = time.time()
        self.events: list[MetricEvent] = []
        self.output_dir = output_dir or Path(__file__).parent.parent / experiment_id / "results"

    def record_event(self, event_name: str, **data: Any) -> None:
        """记录一个事件。"""
        self.events.append(MetricEvent(ts=time.time(), name=event_name, data=data))

    def summary(self) -> dict[str, Any]:
        """产出汇总统计。"""
        from collections import Counter

        counts = Counter(e.name for e in self.events)
        duration = (self.events[-1].ts - self.start_ts) if self.events else 0

        return {
            "experiment_id": self.experiment_id,
            "start_ts": self.start_ts,
            "duration_seconds": round(duration, 2),
            "event_counts": dict(counts),
            "total_events": len(self.events),
        }

    def save(self, filename: str = "metrics.yaml") -> Path:
        """保存到 YAML 文件。"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.output_dir / filename

        payload = {
            **self.summary(),
            "events": [
                {
                    "ts_offset": round(e.ts - self.start_ts, 3),
                    "name": e.name,
                    **e.data,
                }
                for e in self.events
            ],
        }

        if yaml:
            out_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False))
        else:
            # 降级为简单的 key: value 格式
            lines = [f"{k}: {v}" for k, v in payload.items() if k != "events"]
            lines.append("events:")
            for e in payload["events"]:
                lines.append(f"  - {e}")
            out_path.write_text("\n".join(lines))

        return out_path


if __name__ == "__main__":
    mc = MetricsCollector("test")
    mc.record_event("team_created", team_name="demo")
    time.sleep(0.1)
    mc.record_event("member_spawned", member="alice")
    time.sleep(0.05)
    mc.record_event("message_sent", from_="alice", to="bob", tokens=42)
    print(mc.summary())
