"""Frame model — geometry-bearing nodes that live on a page.

Per spec §4.1: every frame carries page-relative geometry, transform, z-order,
lock/visibility flags, optional object-style reference, text-wrap mode, padding,
and an optional parent-group id. Concrete subclasses add type-specific data:

* :class:`TextFrame` — references a story; columns, gutter, vertical alignment.
* :class:`ImageFrame` — references an asset; fit mode, optional crop, image rotation.
* :class:`ShapeFrame` — vector primitive (rect / ellipse / line / polygon) with
  optional stroke + fill.
* :class:`GroupFrame` — purely structural; children reference it by id.

``TableFrame`` is intentionally absent here; it lands in unit-7 alongside the
table block model.

All types are pure data: ``@dataclass(slots=True)``, no Qt, no I/O. Serialization
goes through :py:meth:`Frame.to_dict` / :py:meth:`Frame.from_dict`, which use a
``kind`` discriminator to dispatch to the right subclass.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, ClassVar, Literal, Protocol

# --- helper value types ------------------------------------------------------


@dataclass(slots=True, frozen=True)
class Padding:
    """Inner inset of a frame's content from its bounding box, in points."""

    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0

    @classmethod
    def zero(cls) -> Padding:
        return cls(0.0, 0.0, 0.0, 0.0)

    @classmethod
    def uniform(cls, value: float) -> Padding:
        return cls(value, value, value, value)


@dataclass(slots=True, frozen=True)
class Margins:
    """Page margins in points (top/right/bottom/left)."""

    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0


@dataclass(slots=True, frozen=True)
class Bleeds:
    """Page bleed extents in points."""

    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    left: float = 0.0


@dataclass(slots=True, frozen=True)
class Rect:
    """Axis-aligned rectangle in points."""

    x: float
    y: float
    w: float
    h: float


@dataclass(slots=True, frozen=True)
class ColumnRule:
    """Vertical rule drawn between text-frame columns."""

    color_ref: str
    width_pt: float = 0.5
    dash_pattern: tuple[float, ...] = ()


@dataclass(slots=True, frozen=True)
class Stroke:
    """Stroke spec for a shape frame."""

    color_ref: str
    width_pt: float = 1.0
    dash_pattern: tuple[float, ...] = ()


@dataclass(slots=True, frozen=True)
class Fill:
    """Fill spec for a shape frame.

    ``color_ref`` names a swatch; ``gradient_ref`` is a placeholder for the
    gradient registry that lands with unit-8 (``model-styles``). Exactly one
    should be set in well-formed data.
    """

    color_ref: str | None = None
    gradient_ref: str | None = None


# --- stubs from sibling units ------------------------------------------------


class Story(Protocol):
    """Minimal Story interface needed by TextFrame.

    Replaced by the real Story model from unit-4 (``model-story-and-runs``).
    """

    # stub: replaced by unit-4
    @property
    def id(self) -> str: ...


# --- type aliases ------------------------------------------------------------

TextWrap = Literal["none", "box", "contour"]
TextDirection = Literal["ltr", "rtl", "inherit"]
VerticalAlign = Literal["top", "center", "bottom", "justify"]
ImageFit = Literal["fill", "fit", "stretch", "none"]
ShapeKind = Literal["rect", "ellipse", "line", "polygon"]
FrameKind = Literal["text", "image", "shape", "group"]


# --- base frame --------------------------------------------------------------


@dataclass(slots=True)
class Frame:
    """Abstract base for all page-bound frames.

    Geometry is page-relative and in points. Transforms (rotation, skew) are
    in degrees and apply about the frame's center.
    """

    KIND: ClassVar[FrameKind]  # set by each concrete subclass

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
    text_wrap: TextWrap = "none"
    padding: Padding = field(default_factory=Padding.zero)
    parent_group_id: str | None = None

    def bbox(self) -> Rect:
        """Axis-aligned bounding rect, ignoring rotation and skew."""
        return Rect(self.x_pt, self.y_pt, self.w_pt, self.h_pt)

    def to_dict(self) -> dict[str, Any]:
        return _frame_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Frame:
        kind = data.get("kind")
        subclass = _KIND_REGISTRY.get(kind)  # type: ignore[arg-type]
        if subclass is None:
            raise ValueError(f"unknown frame kind: {kind!r}")
        return subclass._from_dict(data)

    # subclass hook: build an instance from a dict (without the discriminator)
    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> Frame:
        return cls(**_decode_fields(cls, data))


# --- concrete frame types ----------------------------------------------------


@dataclass(slots=True)
class TextFrame(Frame):
    """Text-bearing frame; references a story and supports multi-column layout."""

    KIND: ClassVar[FrameKind] = "text"

    story_ref: str = ""
    story_index: int = 0
    columns: int = 1
    gutter_pt: float = 0.0
    column_rule: ColumnRule | None = None
    text_direction: TextDirection = "inherit"
    vertical_align: VerticalAlign = "top"

    def column_rects(self) -> list[Rect]:
        """Return the content rects for each column, with gutters between them.

        Columns are equal-width; total occupied width is
        ``w_pt - left_pad - right_pad``, minus ``(columns - 1) * gutter_pt``
        for inter-column gaps. Padding is honored on all four sides.
        """
        if self.columns < 1:
            raise ValueError(f"columns must be >= 1, got {self.columns}")
        pad = self.padding
        inner_x = self.x_pt + pad.left
        inner_y = self.y_pt + pad.top
        inner_w = self.w_pt - pad.left - pad.right
        inner_h = self.h_pt - pad.top - pad.bottom
        n = self.columns
        total_gutter = self.gutter_pt * (n - 1)
        col_w = (inner_w - total_gutter) / n
        return [
            Rect(inner_x + i * (col_w + self.gutter_pt), inner_y, col_w, inner_h)
            for i in range(n)
        ]


@dataclass(slots=True)
class ImageFrame(Frame):
    """Frame that displays a raster/vector asset."""

    KIND: ClassVar[FrameKind] = "image"

    asset_ref: str = ""  # sha256 of asset
    fit: ImageFit = "fit"
    crop: Rect | None = None
    image_rotation_deg: float = 0.0


@dataclass(slots=True)
class ShapeFrame(Frame):
    """Vector primitive frame."""

    KIND: ClassVar[FrameKind] = "shape"

    shape_kind: ShapeKind = "rect"
    points: list[tuple[float, float]] = field(default_factory=list)
    stroke: Stroke | None = None
    fill: Fill | None = None
    corner_radius_pt: float = 0.0  # rect only


@dataclass(slots=True)
class GroupFrame(Frame):
    """Pure container: groups other frames for transform / selection.

    Children reference the group via their ``parent_group_id``; the group keeps
    a parallel ``child_ids`` list so the relationship is bidirectional and
    serializable. :func:`validate_group_membership` enforces consistency.
    """

    KIND: ClassVar[FrameKind] = "group"

    child_ids: list[str] = field(default_factory=list)


# --- (de)serialization helpers ----------------------------------------------


_KIND_REGISTRY: dict[FrameKind, type[Frame]] = {
    "text": TextFrame,
    "image": ImageFrame,
    "shape": ShapeFrame,
    "group": GroupFrame,
}


def _frame_to_dict(frame: Frame) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": frame.KIND}
    for f in fields(frame):
        out[f.name] = _encode_value(getattr(frame, f.name))
    return out


def _encode_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (Padding, Margins, Bleeds, Rect, ColumnRule, Stroke, Fill)):
        return {f.name: _encode_value(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, list):
        return [_encode_value(v) for v in value]
    if isinstance(value, tuple):
        return [_encode_value(v) for v in value]
    return value


def _decode_fields(cls: type[Frame], data: dict[str, Any]) -> dict[str, Any]:
    """Project ``data`` onto ``cls``'s field names, decoding nested dataclasses."""
    known = {f.name for f in fields(cls)}
    return {
        name: _decode_field(name, raw)
        for name, raw in data.items()
        if name != "kind" and name in known
    }


_VALUE_TYPES: dict[str, type] = {
    "padding": Padding,
    "crop": Rect,
    "column_rule": ColumnRule,
    "stroke": Stroke,
    "fill": Fill,
}


def _decode_field(name: str, raw: Any) -> Any:
    if raw is None:
        return None
    target = _VALUE_TYPES.get(name)
    if target is not None and isinstance(raw, dict):
        return _decode_dataclass(target, raw)
    if name == "points" and isinstance(raw, list):
        return [tuple(p) for p in raw]
    return raw


def _decode_dataclass(cls: type, raw: dict[str, Any]) -> Any:
    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        if f.name not in raw:
            continue
        value = raw[f.name]
        if f.name == "dash_pattern" and isinstance(value, list):
            value = tuple(value)
        kwargs[f.name] = value
    return cls(**kwargs)


# --- group invariants --------------------------------------------------------


def validate_group_membership(frame: Frame, parent: Frame | None) -> None:
    """Ensure ``frame.parent_group_id`` points to an actual :class:`GroupFrame`.

    Pass ``parent=None`` to validate that the frame has no parent. Otherwise,
    ``parent`` must be the frame referenced by ``frame.parent_group_id`` and it
    must be a :class:`GroupFrame`. A ``ValueError`` is raised on mismatch.
    """
    if frame.parent_group_id is None:
        if parent is not None:
            raise ValueError(
                f"frame {frame.id!r} has no parent_group_id but a parent was supplied"
            )
        return
    if parent is None:
        raise ValueError(
            f"frame {frame.id!r} declares parent_group_id={frame.parent_group_id!r} "
            "but no parent was supplied"
        )
    if parent.id != frame.parent_group_id:
        raise ValueError(
            f"frame {frame.id!r} parent_group_id={frame.parent_group_id!r} "
            f"does not match supplied parent id {parent.id!r}"
        )
    if not isinstance(parent, GroupFrame):
        raise ValueError(
            f"parent of frame {frame.id!r} must be a GroupFrame, got {type(parent).__name__}"
        )


__all__ = [
    "Bleeds",
    "ColumnRule",
    "Fill",
    "Frame",
    "FrameKind",
    "GroupFrame",
    "ImageFit",
    "ImageFrame",
    "Margins",
    "Padding",
    "Rect",
    "ShapeFrame",
    "ShapeKind",
    "Story",
    "Stroke",
    "TextDirection",
    "TextFrame",
    "TextWrap",
    "VerticalAlign",
    "validate_group_membership",
]
