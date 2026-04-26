"""Inline run model: a contiguous span of text sharing inline marks.

A `Run` is the unit of inline styling inside a block (per spec §4.2). Runs are
immutable value objects — every mutation produces a new `Run`. The block tree
holds tuples of runs; the layout pipeline (unit-13) consumes them via
`ParagraphSpec` (see :mod:`msword.model.story`).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class Run:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    code: bool = False
    link: str | None = None
    color_ref: str | None = None
    highlight_ref: str | None = None
    font_ref: str | None = None
    size_pt: float | None = None
    tracking: float = 0.0
    baseline_shift_pt: float = 0.0
    opentype_features: frozenset[str] = field(default_factory=frozenset)
    language_override: str | None = None

    def with_text(self, s: str) -> Run:
        return dataclasses.replace(self, text=s)

    def merge_marks(self, other: Run) -> dict[str, Any]:
        """Return a dict of inline-mark fields from `other`, ignoring text.

        Used by editing commands that need to combine or compare marks across
        runs without comparing their text payloads.
        """
        return {
            f.name: getattr(other, f.name)
            for f in dataclasses.fields(other)
            if f.name != "text"
        }

    def split_at(self, i: int) -> tuple[Run, Run]:
        return self.with_text(self.text[:i]), self.with_text(self.text[i:])

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}
        d["opentype_features"] = sorted(self.opentype_features)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Run:
        payload = dict(data)
        feats = payload.get("opentype_features")
        if feats is not None:
            payload["opentype_features"] = frozenset(feats)
        return cls(**payload)
