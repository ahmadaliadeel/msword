"""Color profiles and swatches.

Pure data — no Qt, no I/O. Mutations are caller-driven and (eventually) routed
through Commands; this module owns only the shapes.

ICC-correct conversion is a unit-18 concern; for v1 unit-8 we provide naive
analytic conversions that are good enough for the model layer / unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ColorKind = Literal["sRGB", "CMYK", "spot", "gray", "Lab"]


@dataclass(slots=True, frozen=True)
class ColorProfile:
    """An ICC color profile, identified by name + kind.

    `icc_data` carries the raw profile bytes; built-in sRGB uses an empty
    bytestring and lets the renderer assume the standard profile. Equality
    deliberately ignores `icc_data` — two profiles are "the same" iff they
    have the same name and kind. This lets a model loaded from disk compare
    equal to a freshly-constructed in-memory one even if a profile blob was
    embedded vs. referenced.
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

    Component count depends on `profile_name`'s kind:
      sRGB → (r, g, b)         in [0, 1]
      CMYK → (c, m, y, k)      in [0, 1]
      gray → (k,)              in [0, 1]
      Lab  → (L, a, b)         L in [0, 100], a/b in [-128, 127]
      spot → (tint,)           in [0, 1]; spot color identified by `name`

    `is_spot=True` flags a separation that the PDF/X exporter must keep as
    its own ink (DeviceN) rather than converting to process color.
    """

    name: str
    profile_name: str
    components: tuple[float, ...]
    is_spot: bool = False

    def to_rgb(self) -> tuple[float, float, float]:
        """Return naive sRGB-floats in [0, 1].

        Not colorimetrically correct — unit-18 will route this through
        LittleCMS for ICC-aware conversion. Kept here so model-layer code
        and previews work without a render dependency.
        """
        comps = self.components
        kind = _kind_from_profile_name(self.profile_name, is_spot=self.is_spot)

        if kind == "sRGB":
            r, g, b = comps
            return (_clamp01(r), _clamp01(g), _clamp01(b))
        if kind == "CMYK":
            c, m, y, k = comps
            inv_k = 1.0 - _clamp01(k)
            r = (1.0 - _clamp01(c)) * inv_k
            g = (1.0 - _clamp01(m)) * inv_k
            b = (1.0 - _clamp01(y)) * inv_k
            return (r, g, b)
        if kind == "gray":
            (level,) = comps
            v = _clamp01(level)
            return (v, v, v)
        if kind == "spot":
            # Tinted black stand-in until the PDF/X path handles spot separations.
            (tint,) = comps
            v = 1.0 - _clamp01(tint)
            return (v, v, v)
        if kind == "Lab":
            # TODO: LittleCMS in unit-18.
            return (0.5, 0.5, 0.5)
        # Unreachable — kept for exhaustiveness.
        raise ValueError(f"unknown color kind: {kind}")


# A tiny built-in profile registry default. Real registries live on Document.
SRGB_PROFILE: ColorProfile = ColorProfile(name="sRGB", kind="sRGB")


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _kind_from_profile_name(profile_name: str, *, is_spot: bool) -> ColorKind:
    """Best-effort kind-inference from a profile name.

    The model-layer `ColorSwatch` doesn't carry a back-reference to its
    `ColorProfile` (profiles live in the Document registry), so for the
    unit-8 self-contained conversion we infer kind from the name. Document-
    level code that has the registry in hand should resolve the profile
    directly and not call `to_rgb` blindly on unknown names.
    """
    if is_spot:
        return "spot"
    name = profile_name.lower()
    if "cmyk" in name:
        return "CMYK"
    if name == "gray" or "grayscale" in name or name == "k":
        return "gray"
    if "lab" in name:
        return "Lab"
    return "sRGB"


__all__ = [
    "SRGB_PROFILE",
    "ColorKind",
    "ColorProfile",
    "ColorSwatch",
]
