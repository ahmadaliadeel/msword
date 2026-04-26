"""Unit tests for `msword.model.style`."""

from __future__ import annotations

import pytest

from msword.model.style import (
    CharacterStyle,
    ObjectStyle,
    ParagraphStyle,
    StyleCycleError,
    StyleNotFoundError,
    StyleResolver,
)


def test_paragraph_style_resolves_inherited_attribute() -> None:
    body = ParagraphStyle(name="Body", font_family="Minion", font_size_pt=11.0, leading_pt=14.0)
    body_bold = ParagraphStyle(name="BodyBold", based_on="Body")
    body_bold_italic = ParagraphStyle(name="BodyBoldItalic", based_on="BodyBold")

    registry = {s.name: s for s in (body, body_bold, body_bold_italic)}
    resolver = StyleResolver(registry, "BodyBoldItalic")

    assert resolver.resolve_attribute("font_size_pt") == 11.0
    assert resolver.resolve_attribute("font_family") == "Minion"
    assert resolver.resolve_attribute("leading_pt") == 14.0


def test_paragraph_style_local_overrides_parent() -> None:
    body = ParagraphStyle(name="Body", font_size_pt=11.0)
    heading = ParagraphStyle(name="H1", based_on="Body", font_size_pt=24.0)

    resolver = StyleResolver({s.name: s for s in (body, heading)}, "H1")
    assert resolver.resolve_attribute("font_size_pt") == 24.0


def test_resolve_attribute_returns_none_when_unset_anywhere() -> None:
    body = ParagraphStyle(name="Body")
    resolver = StyleResolver({"Body": body}, "Body")
    assert resolver.resolve_attribute("font_size_pt") is None


def test_none_field_skips_during_resolution() -> None:
    """A child whose attribute is None must NOT shadow the parent's value."""
    body = ParagraphStyle(name="Body", alignment="justify")
    child = ParagraphStyle(name="Child", based_on="Body")  # alignment is None
    resolver = StyleResolver({s.name: s for s in (body, child)}, "Child")
    assert resolver.resolve_attribute("alignment") == "justify"


def test_cycle_raises_style_cycle_error() -> None:
    body = ParagraphStyle(name="Body", based_on="A")
    a = ParagraphStyle(name="A", based_on="Body")
    resolver = StyleResolver({s.name: s for s in (body, a)}, "Body")
    with pytest.raises(StyleCycleError):
        resolver.resolve_attribute("font_size_pt")


def test_self_reference_raises_style_cycle_error() -> None:
    body = ParagraphStyle(name="Body", based_on="Body")
    resolver = StyleResolver({"Body": body}, "Body")
    with pytest.raises(StyleCycleError):
        resolver.resolve_attribute("font_family")


def test_missing_parent_raises_style_not_found_error() -> None:
    orphan = ParagraphStyle(name="Orphan", based_on="DoesNotExist")
    resolver = StyleResolver({"Orphan": orphan}, "Orphan")
    with pytest.raises(StyleNotFoundError):
        resolver.resolve_attribute("font_size_pt")


def test_missing_start_raises_style_not_found_error() -> None:
    with pytest.raises(StyleNotFoundError):
        StyleResolver({}, "Nope")


def test_character_style_resolution() -> None:
    base = CharacterStyle(name="Base", font_family="Inter", color_ref="black")
    emph = CharacterStyle(name="Emph", based_on="Base", italic=True)
    strong_emph = CharacterStyle(name="StrongEmph", based_on="Emph", bold=True)

    registry = {s.name: s for s in (base, emph, strong_emph)}
    resolver = StyleResolver(registry, "StrongEmph")

    assert resolver.resolve_attribute("bold") is True
    assert resolver.resolve_attribute("italic") is True
    assert resolver.resolve_attribute("font_family") == "Inter"
    assert resolver.resolve_attribute("color_ref") == "black"
    assert resolver.resolve_attribute("underline") is None


def test_object_style_resolution() -> None:
    base = ObjectStyle(name="Frame", columns=1, gutter_pt=12.0, text_inset_pt=4.0)
    two_col = ObjectStyle(name="TwoCol", based_on="Frame", columns=2)

    resolver = StyleResolver({s.name: s for s in (base, two_col)}, "TwoCol")
    assert resolver.resolve_attribute("columns") == 2
    assert resolver.resolve_attribute("gutter_pt") == 12.0
    assert resolver.resolve_attribute("text_inset_pt") == 4.0


def test_paragraph_style_opentype_features_inherits() -> None:
    body = ParagraphStyle(name="Body", opentype_features=frozenset({"liga", "kern"}))
    heading = ParagraphStyle(name="H1", based_on="Body")
    resolver = StyleResolver({s.name: s for s in (body, heading)}, "H1")
    assert resolver.resolve_attribute("opentype_features") == frozenset({"liga", "kern"})


def test_zero_value_does_not_count_as_unset() -> None:
    """A child setting space_before_pt=0.0 must override the parent's nonzero value."""
    body = ParagraphStyle(name="Body", space_before_pt=12.0)
    flush = ParagraphStyle(name="Flush", based_on="Body", space_before_pt=0.0)
    resolver = StyleResolver({s.name: s for s in (body, flush)}, "Flush")
    assert resolver.resolve_attribute("space_before_pt") == 0.0
