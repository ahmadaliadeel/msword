"""ParagraphBlock — body-text paragraph carrying a list of runs."""

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


@BlockRegistry.register
@dataclass(slots=True)
class ParagraphBlock(Block):
    kind: ClassVar[str] = "paragraph"

    id: str
    runs: list[Run] = field(default_factory=list)
    paragraph_style_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "runs": [run_to_dict(r) for r in self.runs],
            "paragraph_style_ref": self.paragraph_style_ref,
        }

    def iter_paragraphs(self) -> Iterable[ParagraphSpec]:
        yield ParagraphSpec(tuple(self.runs), self.paragraph_style_ref, self.id)

    @classmethod
    def _from_dict_specific(cls, d: dict[str, Any]) -> ParagraphBlock:
        return cls(
            id=d["id"],
            runs=[run_from_dict(r) for r in d.get("runs", [])],
            paragraph_style_ref=d.get("paragraph_style_ref"),
        )
