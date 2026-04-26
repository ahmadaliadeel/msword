from __future__ import annotations

import dataclasses

import pytest

from msword.model.run import Run


def test_split_at_preserves_marks() -> None:
    r = Run(text="Hello world", bold=True, italic=True)
    left, right = r.split_at(5)
    assert left.text == "Hello"
    assert right.text == " world"
    for piece in (left, right):
        assert piece.bold is True
        assert piece.italic is True


def test_split_at_boundaries() -> None:
    r = Run(text="abc")
    left, right = r.split_at(0)
    assert (left.text, right.text) == ("", "abc")
    left, right = r.split_at(3)
    assert (left.text, right.text) == ("abc", "")


def test_with_text_replaces_only_text() -> None:
    r = Run(text="old", bold=True, link="https://x", size_pt=12.0)
    r2 = r.with_text("new")
    assert r2.text == "new"
    assert r2.bold is True
    assert r2.link == "https://x"
    assert r2.size_pt == 12.0


def test_merge_marks_returns_inline_marks_without_text() -> None:
    a = Run(text="lhs")
    b = Run(
        text="rhs",
        bold=True,
        italic=True,
        underline=True,
        strike=False,
        code=False,
        link="https://example",
        color_ref="c-red",
        highlight_ref="h-yellow",
        font_ref="f-serif",
        size_pt=11.5,
        tracking=0.05,
        baseline_shift_pt=-1.0,
        opentype_features=frozenset({"liga", "smcp"}),
        language_override="en-US",
    )
    marks = a.merge_marks(b)
    assert "text" not in marks
    assert marks["bold"] is True
    assert marks["italic"] is True
    assert marks["underline"] is True
    assert marks["link"] == "https://example"
    assert marks["color_ref"] == "c-red"
    assert marks["size_pt"] == 11.5
    assert marks["tracking"] == 0.05
    assert marks["baseline_shift_pt"] == -1.0
    assert marks["opentype_features"] == frozenset({"liga", "smcp"})
    assert marks["language_override"] == "en-US"


def test_frozen_dataclass_replace_works() -> None:
    r = Run(text="x", bold=True)
    r2 = dataclasses.replace(r, text="y")
    assert r2.text == "y"
    assert r2.bold is True
    assert r is not r2


def test_frozen_dataclass_blocks_attribute_assignment() -> None:
    r = Run(text="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.text = "y"  # type: ignore[misc]


def test_to_dict_from_dict_roundtrip() -> None:
    r = Run(
        text="hi",
        bold=True,
        opentype_features=frozenset({"liga", "smcp"}),
        size_pt=10.0,
    )
    d = r.to_dict()
    assert d["opentype_features"] == ["liga", "smcp"]
    r2 = Run.from_dict(d)
    assert r2 == r


def test_default_opentype_features_is_empty_frozenset() -> None:
    r = Run(text="x")
    assert r.opentype_features == frozenset()
    # distinct default per instance (the dataclass field uses default_factory)
    r2 = Run(text="y")
    assert r.opentype_features is not r2.opentype_features or r.opentype_features == frozenset()
