"""TableFrame — page-bound frame that lays out a row/column grid of cells.

Per spec §4.1 the full frame hierarchy is ``Frame`` (abstract) → ``TextFrame``,
``ImageFrame``, ``ShapeFrame``, ``TableFrame``, ``GroupFrame``. Unit-3
(``model-frame``) ships every frame type *except* ``TableFrame``; this module
adds ``TableFrame`` alongside it without modifying ``frame.py`` (per the
unit-7 boundary).

Until unit-3 lands, this module also carries a minimal :class:`Frame` stub so
``TableFrame`` is independently importable. Field names and method signatures
mirror what unit-3 will land, so the only follow-up needed when unit-3 merges
is to switch the import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

# --- Frame stub (replaced by unit-3 `model-frame`) ---------------------------


VerticalAlign = Literal["top", "center", "bottom"]


@dataclass(frozen=True)
class Padding:
    """Inner inset of a frame's content from its bounding box, in points."""

    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {"top": self.top, "right": self.right, "bottom": self.bottom, "left": self.left}

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> Padding:
        return cls(
            top=float(data.get("top", 0.0)),
            right=float(data.get("right", 0.0)),
            bottom=float(data.get("bottom", 0.0)),
            left=float(data.get("left", 0.0)),
        )


@dataclass
class Frame:
    """Abstract base for all page-bound frames.

    # stub: replaced by unit-3
    """

    kind: ClassVar[str] = ""

    id: str
    page_id: str
    x_pt: float
    y_pt: float
    w_pt: float
    h_pt: float
    rotation_deg: float = 0.0
    skew_deg: float = 0.0
    z_order: int = 0
    locked: bool = False
    visible: bool = True
    object_style_ref: str | None = None
    text_wrap: Literal["none", "box", "contour"] = "none"
    padding: Padding = field(default_factory=Padding)
    parent_group_id: str | None = None


# --- Table-specific value types ---------------------------------------------


@dataclass
class Row:
    """One row of a :class:`TableFrame`."""

    height_pt: float
    is_header: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"height_pt": self.height_pt, "is_header": self.is_header}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Row:
        return cls(
            height_pt=float(data["height_pt"]),
            is_header=bool(data.get("is_header", False)),
        )


@dataclass
class Col:
    """One column of a :class:`TableFrame`."""

    width_pt: float

    def to_dict(self) -> dict[str, Any]:
        return {"width_pt": self.width_pt}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Col:
        return cls(width_pt=float(data["width_pt"]))


@dataclass
class TableCell:
    """One cell in a :class:`TableFrame`.

    Cells own ``block_ids`` rather than nested blocks: the actual content lives
    in the story tree, and the table only references it by id. (Compare with
    :class:`msword.model.blocks.table.BlockCell`, which *does* inline nested
    blocks because a ``TableBlock`` is itself part of a story.)
    """

    block_ids: list[str] = field(default_factory=list)
    rowspan: int = 1
    colspan: int = 1
    vertical_align: VerticalAlign = "top"

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_ids": list(self.block_ids),
            "rowspan": self.rowspan,
            "colspan": self.colspan,
            "vertical_align": self.vertical_align,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TableCell:
        return cls(
            block_ids=list(data.get("block_ids", [])),
            rowspan=int(data.get("rowspan", 1)),
            colspan=int(data.get("colspan", 1)),
            vertical_align=data.get("vertical_align", "top"),
        )


# --- TableFrame -------------------------------------------------------------


@dataclass
class TableFrame(Frame):
    """A frame that lays out a grid of cells over rows and columns."""

    kind: ClassVar[str] = "table"

    rows: list[Row] = field(default_factory=list)
    cols: list[Col] = field(default_factory=list)
    cells: dict[tuple[int, int], TableCell] = field(default_factory=dict)

    # --- access ----------------------------------------------------------

    def cell_at(self, row: int, col: int) -> TableCell:
        """Return the cell anchored at ``(row, col)``.

        Raises :class:`KeyError` if no cell is anchored there. A cell occupies
        the rectangle ``[row, row + rowspan) x [col, col + colspan)`` but is
        stored only at its anchor.
        """
        return self.cells[(row, col)]

    # --- mutation --------------------------------------------------------

    def merge_cells(
        self,
        start_row: int,
        start_col: int,
        end_row: int,
        end_col: int,
    ) -> TableCell:
        """Merge the inclusive rectangle ``[start_row..end_row, start_col..end_col]``.

        The cell anchored at ``(start_row, start_col)`` absorbs the others'
        ``block_ids`` (in row-major order) and grows to span the rectangle.
        Other anchors inside the rectangle are removed. Returns the merged
        cell. The rectangle must be non-empty, in-bounds, and contain only
        unit-1x1 cells (i.e. a freshly-merged region must be split first).
        """
        if not (
            0 <= start_row <= end_row < len(self.rows)
            and 0 <= start_col <= end_col < len(self.cols)
        ):
            raise ValueError(
                f"merge rectangle [{start_row}..{end_row}, {start_col}..{end_col}] "
                f"is out of bounds for {len(self.rows)}x{len(self.cols)} table"
            )
        anchor = self.cells.get((start_row, start_col))
        if anchor is None:
            raise KeyError((start_row, start_col))
        for r in range(start_row, end_row + 1):
            for c in range(start_col, end_col + 1):
                if (r, c) == (start_row, start_col):
                    continue
                other = self.cells.get((r, c))
                if other is None:
                    raise ValueError(
                        f"cannot merge: cell ({r},{c}) is already part of another span"
                    )
                if other.rowspan != 1 or other.colspan != 1:
                    raise ValueError(
                        f"cannot merge: cell ({r},{c}) already spans "
                        f"{other.rowspan}x{other.colspan} — split it first"
                    )
                anchor.block_ids.extend(other.block_ids)
                del self.cells[(r, c)]
        anchor.rowspan = end_row - start_row + 1
        anchor.colspan = end_col - start_col + 1
        return anchor

    def split_cell(self, row: int, col: int) -> None:
        """Inverse of :meth:`merge_cells`: restore unit cells inside the span.

        The anchor cell keeps its ``block_ids`` and shrinks to 1x1; every other
        position in its former span gets a fresh empty cell.
        """
        anchor = self.cells.get((row, col))
        if anchor is None:
            raise KeyError((row, col))
        rowspan, colspan = anchor.rowspan, anchor.colspan
        if rowspan == 1 and colspan == 1:
            return
        anchor.rowspan = 1
        anchor.colspan = 1
        for r in range(row, row + rowspan):
            for c in range(col, col + colspan):
                if (r, c) == (row, col):
                    continue
                self.cells[(r, c)] = TableCell()

    # --- (de)serialization ---------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "page_id": self.page_id,
            "x_pt": self.x_pt,
            "y_pt": self.y_pt,
            "w_pt": self.w_pt,
            "h_pt": self.h_pt,
            "rotation_deg": self.rotation_deg,
            "skew_deg": self.skew_deg,
            "z_order": self.z_order,
            "locked": self.locked,
            "visible": self.visible,
            "object_style_ref": self.object_style_ref,
            "text_wrap": self.text_wrap,
            "padding": self.padding.to_dict(),
            "parent_group_id": self.parent_group_id,
            "rows": [r.to_dict() for r in self.rows],
            "cols": [c.to_dict() for c in self.cols],
            "cells": [
                {"row": r, "col": c, **cell.to_dict()}
                for (r, c), cell in sorted(self.cells.items())
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TableFrame:
        cells: dict[tuple[int, int], TableCell] = {}
        for entry in data.get("cells", []):
            row = int(entry["row"])
            col = int(entry["col"])
            cells[(row, col)] = TableCell.from_dict(entry)
        padding_raw = data.get("padding")
        return cls(
            id=data["id"],
            page_id=data["page_id"],
            x_pt=float(data["x_pt"]),
            y_pt=float(data["y_pt"]),
            w_pt=float(data["w_pt"]),
            h_pt=float(data["h_pt"]),
            rotation_deg=float(data.get("rotation_deg", 0.0)),
            skew_deg=float(data.get("skew_deg", 0.0)),
            z_order=int(data.get("z_order", 0)),
            locked=bool(data.get("locked", False)),
            visible=bool(data.get("visible", True)),
            object_style_ref=data.get("object_style_ref"),
            text_wrap=data.get("text_wrap", "none"),
            padding=Padding.from_dict(padding_raw) if padding_raw else Padding(),
            parent_group_id=data.get("parent_group_id"),
            rows=[Row.from_dict(r) for r in data.get("rows", [])],
            cols=[Col.from_dict(c) for c in data.get("cols", [])],
            cells=cells,
        )


__all__ = [
    "Col",
    "Frame",
    "Padding",
    "Row",
    "TableCell",
    "TableFrame",
    "VerticalAlign",
]
