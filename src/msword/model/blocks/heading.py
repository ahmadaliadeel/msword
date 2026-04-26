"""HeadingBlock — heading paragraph (levels 1..6)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from msword.model.block import (
    Block,
    BlockRegistry,
    ParagraphSpec,
    Run,
    run_from_dict,
    run_to_dict,
)

_MIN_LEVEL = 1
_MAX_LEVEL = 6


@BlockRegistry.register
@dataclass(slots=True)
class HeadingBlock(Block):
    kind: ClassVar[str] = "heading"

    id: str
    level: int = _MIN_LEVEL
    runs: list[Run] = field(default_factory=list)
    paragraph_style_ref: str | None = None

    def __post_init__(self) -> None:
        if not _MIN_LEVEL <= self.level <= _MAX_LEVEL:
            raise ValueError(
                f"HeadingBlock.level must be {_MIN_LEVEL}..{_MAX_LEVEL}, got {self.level}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "level": self.level,
            "runs": [run_to_dict(r) for r in self.runs],
            "paragraph_style_ref": self.paragraph_style_ref,
        }

    def iter_paragraphs(self) -> Iterable[ParagraphSpec]:
        yield ParagraphSpec(tuple(self.runs), self.paragraph_style_ref, self.id)

    @classmethod
    def _from_dict_specific(cls, d: dict[str, Any]) -> HeadingBlock:
        return cls(
            id=d["id"],
            level=int(d["level"]),
            runs=[run_from_dict(r) for r in d.get("runs", [])],
            paragraph_style_ref=d.get("paragraph_style_ref"),
        )
