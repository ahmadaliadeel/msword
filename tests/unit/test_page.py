"""Unit tests for `msword.model.page` — see spec §4."""

from __future__ import annotations

from msword.model.page import (
    A4_HEIGHT_PT,
    A4_WIDTH_PT,
    Bleeds,
    Margins,
    Page,
)


def test_page_defaults() -> None:
    """Default Page is A4 with zero margins/bleeds and no master."""
    page = Page(id="p1")
    assert page.id == "p1"
    assert page.master_id is None
    assert page.width_pt == A4_WIDTH_PT
    assert page.height_pt == A4_HEIGHT_PT
    assert page.margins == Margins()
    assert page.bleeds == Bleeds()
    assert page.background_color_ref is None
    assert page.frames == []


def test_margins_bleeds_roundtrip() -> None:
    m = Margins(top=10, right=20, bottom=30, left=40)
    assert Margins.from_dict(m.to_dict()) == m
    b = Bleeds(top=3, right=3, bottom=3, left=3)
    assert Bleeds.from_dict(b.to_dict()) == b


def test_page_to_dict_from_dict_roundtrip() -> None:
    page = Page(
        id="p1",
        master_id="A",
        width_pt=612.0,
        height_pt=792.0,
        margins=Margins(top=72, right=72, bottom=72, left=72),
        bleeds=Bleeds(top=9, right=9, bottom=9, left=9),
        background_color_ref="swatch:white",
    )
    d = page.to_dict()
    restored = Page.from_dict(d)

    assert restored.id == page.id
    assert restored.master_id == page.master_id
    assert restored.width_pt == page.width_pt
    assert restored.height_pt == page.height_pt
    assert restored.margins == page.margins
    assert restored.bleeds == page.bleeds
    assert restored.background_color_ref == page.background_color_ref
    # Frames are opaque at this layer (unit-3 owns Frame); from_dict yields []
    assert restored.frames == []


def test_page_to_dict_serializes_frames_via_to_dict() -> None:
    """A frame-like object on `Page.frames` is serialized through its to_dict."""

    class _StubFrame:
        id = "f1"

        def to_dict(self) -> dict[str, str]:
            return {"id": self.id, "kind": "stub"}

    page = Page(id="p", frames=[_StubFrame()])
    d = page.to_dict()
    assert d["frames"] == [{"id": "f1", "kind": "stub"}]
