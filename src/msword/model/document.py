"""Stub :mod:`msword.model.document` — replaced by unit-2 (`model-document-core`).

Unit-26 (colors palette) only consumes:

* :attr:`Document.color_profiles` — registry of :class:`ColorProfile` by name.
* :attr:`Document.color_swatches` — registry of :class:`ColorSwatch` by name.
* :attr:`Document.selected_frame` — a stand-in for "the currently selected
  frame" the SetFrameFill / SetFrameStroke commands target. The real
  selection model lands in unit-2 / the canvas unit; replacing this stub
  with the real Document should be a no-op for the palette.

A minimal :class:`_StubFrame` is used by tests as the selected frame; real
frames (see unit-3) will simply have ``fill`` / ``stroke`` attributes that
match this duck type.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from msword.model.color import SRGB_PROFILE, ColorProfile, ColorSwatch


@dataclass
class _StubFrame:
    """Minimal "selected frame" stand-in for unit-26.

    The real frame model (unit-3) defines ``fill`` / ``stroke`` as
    ``str | None`` — references to a swatch by name. We mirror that here so
    SetFrameFill / SetFrameStroke commands can be tested at the public seam
    without pulling in the full frame model.
    """

    id: str = "stub-frame"
    fill: str | None = None
    stroke: str | None = None


@dataclass
class Document:
    """Minimal Document stub for unit-26.

    Holds the swatch + profile registries the palette manipulates plus a
    "selected frame" the SetFrame* commands target. Replaced wholesale by
    unit-2's real Document.
    """

    color_profiles: dict[str, ColorProfile] = field(default_factory=dict)
    color_swatches: dict[str, ColorSwatch] = field(default_factory=dict)
    selected_frame: _StubFrame | None = None

    def __post_init__(self) -> None:
        # Always have an sRGB profile available so the editor's profile
        # picker is never empty.
        self.color_profiles.setdefault(SRGB_PROFILE.name, SRGB_PROFILE)


__all__ = ["Document", "_StubFrame"]
