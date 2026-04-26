"""Layer model.

Per the design decision in unit #24 (`ui-layers-palette`), a `Layer` is a
first-class model concept on a page. Frames carry a `layer_id`; layers
control z-order, visibility, and locking *as a group* across the frames
that belong to them.

Owned by: unit #24. Other units (frame, page, commands) read this module
as needed; the canonical definitions live here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# RGB color (0-255 per channel) used for the layer's swatch / outline tint
# in the palette. Stored as a plain tuple so dataclass/slots remain trivial
# and the model layer stays free of Qt types.
LayerColor = tuple[int, int, int]


def _default_color() -> LayerColor:
    return (200, 200, 200)


@dataclass(slots=True)
class Layer:
    """A named, ordered stack-band on a page.

    Attributes
    ----------
    id:
        Stable identifier (UUID-like string assigned by the document /
        page when the layer is created). Treated as opaque elsewhere.
    name:
        Human-visible name shown in the layers palette.
    visible:
        When False, frames on this layer are hidden in the canvas and
        excluded from PDF export.
    locked:
        When True, frames on this layer cannot be selected, moved, or
        edited via tools — visibility is unaffected.
    color:
        RGB triple used as the layer swatch and the selection-handle
        tint for frames on this layer (matches QuarkXPress / InDesign
        convention). Defaults to a neutral gray.
    z_order:
        Integer rank within the page. Lower values render below higher
        values. The layers palette renders the list top-down with the
        highest z_order at the top, again matching DTP convention.
    """

    id: str
    name: str
    visible: bool = True
    locked: bool = False
    color: LayerColor = field(default_factory=_default_color)
    z_order: int = 0
