"""TableBlock — nestable, in-story table whose cells contain blocks.

Per spec §4.2: distinct from :class:`msword.model.table_frame.TableFrame` (a
page-level container that owns geometry and references story content by id).
A ``TableBlock`` is *itself* part of a story; its cells inline child blocks
directly so a table inside a footnote inside a callout serializes cleanly via
:class:`BlockRegistry`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

from msword.model.block import Block, BlockRegistry, ParagraphSpec

VerticalAlign = Literal["top", "center", "bottom"]


@dataclass
class BlockRow:
    """One row in a :class:`TableBlock`."""

    height_pt: float = 0.0
    is_header: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"height_pt": self.height_pt, "is_header": self.is_header}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlockRow:
        return cls(
            height_pt=float(data.get("height_pt", 0.0)),
            is_header=bool(data.get("is_header", False)),
        )


@dataclass
class BlockCol:
    """One column in a :class:`TableBlock`."""

    width_pt: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"width_pt": self.width_pt}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlockCol:
        return cls(width_pt=float(data.get("width_pt", 0.0)))


@dataclass
class BlockCell:
    """One cell of a :class:`TableBlock`. Carries inline child blocks."""

    blocks: list[Block] = field(default_factory=list)
    rowspan: int = 1
    colspan: int = 1
    vertical_align: VerticalAlign = "top"

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocks": [b.to_dict() for b in self.blocks],
            "rowspan": self.rowspan,
            "colspan": self.colspan,
            "vertical_align": self.vertical_align,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlockCell:
        return cls(
            blocks=[BlockRegistry.resolve(b) for b in data.get("blocks", [])],
            rowspan=int(data.get("rowspan", 1)),
            colspan=int(data.get("colspan", 1)),
            vertical_align=data.get("vertical_align", "top"),
        )


@dataclass
class TableBlock(Block):
    """An in-story table; cells contain blocks (paragraphs, images, even tables)."""

    kind: ClassVar[str] = "table-block"

    id: str
    rows: list[BlockRow] = field(default_factory=list)
    cols: list[BlockCol] = field(default_factory=list)
    cells: dict[tuple[int, int], BlockCell] = field(default_factory=dict)

    def iter_paragraphs(self) -> Iterator[ParagraphSpec]:
        """Walk cells in row-major order, yielding paragraphs from each child block."""
        for r in range(len(self.rows)):
            for c in range(len(self.cols)):
                cell = self.cells.get((r, c))
                if cell is None:
                    continue
                for block in cell.blocks:
                    yield from block.iter_paragraphs()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "rows": [r.to_dict() for r in self.rows],
            "cols": [c.to_dict() for c in self.cols],
            "cells": [
                {"row": r, "col": c, **cell.to_dict()}
                for (r, c), cell in sorted(self.cells.items())
            ],
        }

    @classmethod
    def _from_dict_specific(cls, data: dict[str, Any]) -> TableBlock:
        cells: dict[tuple[int, int], BlockCell] = {}
        for entry in data.get("cells", []):
            row = int(entry["row"])
            col = int(entry["col"])
            cells[(row, col)] = BlockCell.from_dict(entry)
        return cls(
            id=data["id"],
            rows=[BlockRow.from_dict(r) for r in data.get("rows", [])],
            cols=[BlockCol.from_dict(c) for c in data.get("cols", [])],
            cells=cells,
        )


BlockRegistry.register(TableBlock)


__all__ = [
    "BlockCell",
    "BlockCol",
    "BlockRow",
    "TableBlock",
    "VerticalAlign",
]
