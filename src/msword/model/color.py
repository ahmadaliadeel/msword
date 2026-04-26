"""Stub :mod:`msword.model.color` — replaced by unit-8 (`model-styles`).

Unit-26 (colors palette) only consumes:

* :class:`ColorProfile` — name + kind ("sRGB", "CMYK", "spot"); deduplicated
  by ``(name, kind)`` so an in-memory profile compares equal to a saved one.
* :class:`ColorSwatch` — a named color value (components per profile kind),
  optionally a spot color.
* :data:`SRGB_PROFILE` — a built-in sRGB default.

The unit-8 implementation is a strict superset (it adds Lab, gray, and
ICC-aware ``to_rgb``); the palette code never touches those, so dropping in
the real module should be a no-op for this unit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ColorKind = Literal["sRGB", "CMYK", "spot", "gray", "Lab"]


@dataclass(slots=True, frozen=True)
class ColorProfile:
    """An ICC color profile, identified by name + kind.

    Equality ignores :attr:`icc_data` — two profiles are equal iff name and
    kind match. Lets a profile loaded from disk compare equal to one built
    in memory.
    """

    name: str
    kind: ColorKind
    icc_data: bytes = b""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ColorProfile):
            return NotImplemented
        return self.name == other.name and self.kind == other.kind

    def __hash__(self) -> int:
        return hash((self.name, self.kind))


@dataclass(slots=True)
class ColorSwatch:
    """A named color value defined against a profile.

    Component count depends on the profile kind:

    ====== ================================
    kind    components
    ====== ================================
    sRGB    (r, g, b) in [0, 1]
    CMYK    (c, m, y, k) in [0, 1]
    spot    (tint,) in [0, 1]
    ====== ================================
    """

    name: str
    profile_name: str
    components: tuple[float, ...]
    is_spot: bool = False

    def to_rgb(self) -> tuple[float, float, float]:
        """Naive sRGB-floats in [0, 1] — preview-grade, not colorimetric."""
        comps = self.components
        if self.is_spot:
            (tint,) = comps
            v = 1.0 - _clamp01(tint)
            return (v, v, v)
        name = self.profile_name.lower()
        if "cmyk" in name:
            c, m, y, k = comps
            inv_k = 1.0 - _clamp01(k)
            r = (1.0 - _clamp01(c)) * inv_k
            g = (1.0 - _clamp01(m)) * inv_k
            b = (1.0 - _clamp01(y)) * inv_k
            return (r, g, b)
        # default: sRGB
        r, g, b = comps
        return (_clamp01(r), _clamp01(g), _clamp01(b))


SRGB_PROFILE: ColorProfile = ColorProfile(name="sRGB", kind="sRGB")


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


__all__ = [
    "SRGB_PROFILE",
    "ColorKind",
    "ColorProfile",
    "ColorSwatch",
]
