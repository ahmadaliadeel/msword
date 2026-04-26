"""Unit tests for `msword.model.color`."""

from __future__ import annotations

import dataclasses
import math

import pytest

from msword.model.color import (
    SRGB_PROFILE,
    ColorProfile,
    ColorSwatch,
)


def _approx(actual: tuple[float, float, float], expected: tuple[float, float, float]) -> bool:
    return all(math.isclose(a, e, abs_tol=1e-9) for a, e in zip(actual, expected, strict=True))


def test_srgb_swatch_to_rgb_is_identity() -> None:
    red = ColorSwatch(name="Red", profile_name="sRGB", components=(1.0, 0.0, 0.0))
    assert _approx(red.to_rgb(), (1.0, 0.0, 0.0))


def test_srgb_swatch_clamps_out_of_range_components() -> None:
    swatch = ColorSwatch(name="Hot", profile_name="sRGB", components=(1.5, -0.2, 0.5))
    assert _approx(swatch.to_rgb(), (1.0, 0.0, 0.5))


def test_cmyk_naive_conversion_pure_cyan() -> None:
    swatch = ColorSwatch(
        name="Cyan", profile_name="CMYK Coated", components=(1.0, 0.0, 0.0, 0.0)
    )
    assert _approx(swatch.to_rgb(), (0.0, 1.0, 1.0))


def test_cmyk_naive_conversion_with_black() -> None:
    # Pure key (k=1) → black regardless of cmy.
    swatch = ColorSwatch(
        name="Key", profile_name="CMYK Coated", components=(0.0, 0.0, 0.0, 1.0)
    )
    assert _approx(swatch.to_rgb(), (0.0, 0.0, 0.0))


def test_gray_swatch_to_rgb() -> None:
    swatch = ColorSwatch(name="Mid", profile_name="Gray", components=(0.5,))
    r, g, b = swatch.to_rgb()
    assert math.isclose(r, 0.5) and math.isclose(g, 0.5) and math.isclose(b, 0.5)


def test_spot_swatch_to_rgb_uses_tint() -> None:
    swatch = ColorSwatch(
        name="PMS 185", profile_name="Spot", components=(0.5,), is_spot=True
    )
    # Naive stand-in: tint=0.5 → mid-gray.
    r, g, b = swatch.to_rgb()
    assert math.isclose(r, 0.5)
    assert math.isclose(g, 0.5)
    assert math.isclose(b, 0.5)


def test_swatch_roundtrip_dataclass_replace() -> None:
    """Mutability roundtrip: ColorSwatch is a non-frozen dataclass."""
    s = ColorSwatch(name="Red", profile_name="sRGB", components=(1.0, 0.0, 0.0))
    s.components = (0.0, 1.0, 0.0)
    s.name = "Green"
    assert s.name == "Green"
    assert s.components == (0.0, 1.0, 0.0)


def test_color_profile_equality_ignores_icc_data() -> None:
    a = ColorProfile(name="sRGB", kind="sRGB", icc_data=b"")
    b = ColorProfile(name="sRGB", kind="sRGB", icc_data=b"\x00" * 3000)
    assert a == b
    assert hash(a) == hash(b)


def test_color_profile_equality_distinct_on_kind() -> None:
    a = ColorProfile(name="house-coated", kind="sRGB")
    b = ColorProfile(name="house-coated", kind="CMYK")
    assert a != b


def test_color_profile_is_frozen() -> None:
    p = ColorProfile(name="sRGB", kind="sRGB")
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.name = "other"  # type: ignore[misc]


def test_builtin_srgb_profile_constant() -> None:
    assert SRGB_PROFILE.name == "sRGB"
    assert SRGB_PROFILE.kind == "sRGB"
    assert SRGB_PROFILE.icc_data == b""
