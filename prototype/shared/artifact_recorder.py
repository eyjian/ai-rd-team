"""制品记录器

在原型实验中跟踪各成员产出的制品文件，记录时间戳/大小/token 估算。

使用：
    rec = ArtifactRecorder("01-basic-team")
    rec.record("architect", "design-note.md", content)
    rec.record("developer", "calculator.py", content)
    rec.save_manifest()
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from token_counter import estimate_tokens

try:
    import yaml
except ImportError:
    yaml = None


@dataclass
class ArtifactRecord:
    producer: str          # 生产者角色名
    filename: str          # 制品文件名
    ts: float              # 生产时间戳
    size_bytes: int        # 字节数
    estimated_tokens: int  # 估算 token 数
    content_sha1: str      # 内容哈希（用于检测并发冲突）


class ArtifactRecorder:
    def __init__(self, experiment_id: str, artifact_dir: Path | None = None):
        self.experiment_id = experiment_id
        base = Path(__file__).parent.parent / experiment_id
        self.artifact_dir = artifact_dir or (base / "results" / "artifacts")
        self.manifest_path = base / "results" / "artifact-manifest.yaml"
        self.records: list[ArtifactRecord] = []
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def record(self, producer: str, filename: str, content: str) -> Path:
        """写入制品文件并记录元数据。"""
        out_path = self.artifact_dir / filename
        out_path.write_text(content, encoding="utf-8")

        self.records.append(
            ArtifactRecord(
                producer=producer,
                filename=filename,
                ts=time.time(),
                size_bytes=len(content.encode("utf-8")),
                estimated_tokens=estimate_tokens(content),
                content_sha1=hashlib.sha1(content.encode("utf-8")).hexdigest()[:12],
            )
        )
        return out_path

    def save_manifest(self) -> Path:
        """输出 manifest。"""
        payload = {
            "experiment_id": self.experiment_id,
            "artifact_count": len(self.records),
            "total_tokens": sum(r.estimated_tokens for r in self.records),
            "total_bytes": sum(r.size_bytes for r in self.records),
            "artifacts": [asdict(r) for r in self.records],
        }

        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        if yaml:
            self.manifest_path.write_text(
                yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
            )
        else:
            self.manifest_path.write_text(str(payload))

        return self.manifest_path


if __name__ == "__main__":
    rec = ArtifactRecorder("test")
    rec.record("architect", "design.md", "# 设计\n接口：`def calc(op, a, b)`")
    rec.record("developer", "calc.py", "def calc(op, a, b):\n    ...")
    path = rec.save_manifest()
    print(f"Saved to: {path}")
