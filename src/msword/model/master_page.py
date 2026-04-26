"""Master page model — templates with chained inheritance.

Per spec §4 master pages may be based on each other (A-Master / B-Master /
…). Each `MasterPage` optionally points to a parent via `parent_master_id`;
`resolve_parent_chain` walks that chain and returns it root-first.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from msword.model.page import A4_HEIGHT_PT, A4_WIDTH_PT, Bleeds, FrameLike, Margins


@dataclass(slots=True)
class MasterPage:
    """A reusable page template.

    `parent_master_id` lets masters inherit from each other; cycles are
    rejected by `resolve_parent_chain`.
    """

    id: str
    name: str
    parent_master_id: str | None = None
    width_pt: float = A4_WIDTH_PT
    height_pt: float = A4_HEIGHT_PT
    margins: Margins = field(default_factory=Margins)
    bleeds: Bleeds = field(default_factory=Bleeds)
    frames: list[FrameLike] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "parent_master_id": self.parent_master_id,
            "width_pt": self.width_pt,
            "height_pt": self.height_pt,
            "margins": self.margins.to_dict(),
            "bleeds": self.bleeds.to_dict(),
            "frames": [frame.to_dict() for frame in self.frames],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MasterPage:
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", "")),
            parent_master_id=data.get("parent_master_id"),
            width_pt=float(data.get("width_pt", A4_WIDTH_PT)),
            height_pt=float(data.get("height_pt", A4_HEIGHT_PT)),
            margins=Margins.from_dict(data.get("margins", {})),
            bleeds=Bleeds.from_dict(data.get("bleeds", {})),
            frames=[],
        )

    def resolve_parent_chain(
        self, masters: Iterable[MasterPage] | Mapping[str, MasterPage]
    ) -> list[MasterPage]:
        """Return the inheritance chain ending at `self`, root-first.

        For chain `A → B → C` (where C's parent is B and B's parent is A),
        `C.resolve_parent_chain(...)` returns `[A, B, C]`.

        Raises `ValueError` if a cycle is detected or if a referenced parent
        master is missing.
        """
        if isinstance(masters, Mapping):
            by_id: dict[str, MasterPage] = dict(masters)
        else:
            by_id = {m.id: m for m in masters}
        # Ensure self is reachable so callers can pass `document.master_pages`
        # directly without first having to insert `self`.
        by_id.setdefault(self.id, self)

        chain: list[MasterPage] = []
        seen: set[str] = set()
        current: MasterPage | None = self
        while current is not None:
            if current.id in seen:
                raise ValueError(
                    f"Cycle detected in master page parent chain at id={current.id!r}"
                )
            seen.add(current.id)
            chain.append(current)
            if current.parent_master_id is None:
                break
            parent = by_id.get(current.parent_master_id)
            if parent is None:
                raise ValueError(
                    f"Master page {current.id!r} references missing parent "
                    f"{current.parent_master_id!r}"
                )
            current = parent
        chain.reverse()
        return chain
