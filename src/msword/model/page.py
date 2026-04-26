"""Page model — geometry, margins, bleeds, frame list.

Per spec §4 a `Page` references a master, owns its frames, and carries trim
geometry plus optional bleed (for PDF/X export). Pure data; no Qt widgets,
no rendering, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Self, runtime_checkable


@runtime_checkable
class FrameLike(Protocol):
    """Minimal duck-typed view of a frame, for the model-page layer.

    The full `Frame` hierarchy lands in unit-3 (`model/frame.py`). This
    `Protocol` lets `Page` hold and (de)serialize frames without importing
    any concrete frame class.

    # stub: replaced by unit-3
    """

    id: str

    def to_dict(self) -> dict[str, Any]: ...


@dataclass(slots=True)
class _EdgeOffsets:
    """Four-edge offsets in points (1pt = 1/72 inch).

    Base for `Margins`, `Bleeds`, and (in unit-3) frame padding — anywhere a
    rectangular inset is needed. Subclasses keep nominal types so spec
    vocabulary ("margins", "bleeds") survives in signatures and serialization.
    """

    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {"top": self.top, "right": self.right, "bottom": self.bottom, "left": self.left}

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> Self:
        return cls(
            top=float(data.get("top", 0.0)),
            right=float(data.get("right", 0.0)),
            bottom=float(data.get("bottom", 0.0)),
            left=float(data.get("left", 0.0)),
        )


@dataclass(slots=True)
class Margins(_EdgeOffsets):
    """Page margins in points."""


@dataclass(slots=True)
class Bleeds(_EdgeOffsets):
    """Bleed region in points, per spec §7 (PDF/X export sets BleedBox)."""


# A4 in points: 595.276 x 841.890 — kept as module-level defaults for ergonomic
# Page() construction (e.g. in tests). Callers that need other sizes pass them
# explicitly.
A4_WIDTH_PT: float = 595.2755905511812
A4_HEIGHT_PT: float = 841.8897637795275


@dataclass(slots=True)
class Page:
    """A document page.

    `frames` holds frame objects (concrete types in unit-3); we only require
    `to_dict()` here, hence the `FrameLike` protocol. `master_id` is `None`
    for pages that are not bound to any master.
    """

    id: str
    master_id: str | None = None
    width_pt: float = A4_WIDTH_PT
    height_pt: float = A4_HEIGHT_PT
    margins: Margins = field(default_factory=Margins)
    bleeds: Bleeds = field(default_factory=Bleeds)
    background_color_ref: str | None = None
    frames: list[FrameLike] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "master_id": self.master_id,
            "width_pt": self.width_pt,
            "height_pt": self.height_pt,
            "margins": self.margins.to_dict(),
            "bleeds": self.bleeds.to_dict(),
            "background_color_ref": self.background_color_ref,
            "frames": [frame.to_dict() for frame in self.frames],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Page:
        # Frames stay opaque at this layer — unit-3 provides a real factory.
        # We round-trip an empty frame list; callers that need full frame
        # rehydration go through the full document loader (unit-10).
        return cls(
            id=str(data["id"]),
            master_id=data.get("master_id"),
            width_pt=float(data.get("width_pt", A4_WIDTH_PT)),
            height_pt=float(data.get("height_pt", A4_HEIGHT_PT)),
            margins=Margins.from_dict(data.get("margins", {})),
            bleeds=Bleeds.from_dict(data.get("bleeds", {})),
            background_color_ref=data.get("background_color_ref"),
            frames=[],
        )
