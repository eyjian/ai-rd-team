from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class Bookmark:
    """A bookmark record."""

    id: int
    url: str
    title: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    created: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # JSON 里的 tags 用 list，保持可读
        data["tags"] = list(self.tags)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Bookmark":
        return cls(
            id=int(data["id"]),
            url=str(data["url"]),
            title=str(data["title"]),
            tags=tuple(data.get("tags", []) or []),
            created=str(data.get("created", "")),
        )
