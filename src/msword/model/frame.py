"""Stub frame model.

Real implementation lives in unit-3 (`model-frame`). This stub exposes the
attributes the measurements palette reads (geometry, columns, gutter,
vertical-align, baseline-grid override) and accepts mutation by commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Frame:
    """Geometric frame stub.

    Coordinates and sizes are in PostScript points (1pt = 1/72 inch).
    """

    id: str = "frame-stub"
    x: float = 0.0
    y: float = 0.0
    w: float = 100.0
    h: float = 100.0
    rotation: float = 0.0
    skew: float = 0.0
    locked: bool = False
    aspect_locked: bool = False


@dataclass
class TextFrame(Frame):
    """Text frame stub adding column / vertical-align / baseline-grid fields."""

    columns: int = 1
    gutter: float = 12.0
    vertical_align: str = "top"  # one of: top | center | bottom | justify
    baseline_grid: bool = False


@dataclass
class ImageFrame(Frame):
    """Image frame stub."""

    asset_ref: str | None = None


@dataclass
class ShapeFrame(Frame):
    """Shape frame stub."""

    shape: str = "rect"
    stroke_width: float = 1.0


@dataclass
class GroupFrame(Frame):
    """Group frame stub."""

    children: list[Frame] = field(default_factory=list)
