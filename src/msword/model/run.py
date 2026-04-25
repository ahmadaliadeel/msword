"""Inline run model.

# stub: replaced by unit-4

Minimal `Run` dataclass adequate for unit-6 block types. Unit-4 (`model-story-and-runs`)
ships the full inline-mark set (bold, italic, link, color_ref, opentype_features, ...)
per spec §4.2. Until then this stub captures only the fields unit-6 actually exercises:
text, font_ref, plus a free-form marks dict so callers can attach extras without
breaking when the real `Run` lands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Run:
    """Inline styled text fragment."""

    text: str
    font_ref: str | None = None
    marks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"text": self.text}
        if self.font_ref is not None:
            out["font_ref"] = self.font_ref
        if self.marks:
            out["marks"] = dict(self.marks)
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Run:
        return cls(
            text=data["text"],
            font_ref=data.get("font_ref"),
            marks=dict(data.get("marks", {})),
        )
