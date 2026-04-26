"""Tests for the frame model (unit-3, ``model-frame``)."""

from __future__ import annotations

import dataclasses
import itertools
from typing import Any

import pytest

from msword.model.frame import (
    ColumnRule,
    Fill,
    Frame,
    GroupFrame,
    ImageFrame,
    Padding,
    Rect,
    ShapeFrame,
    Stroke,
    TextFrame,
    validate_group_membership,
)

# --- helpers ----------------------------------------------------------------


def _base_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        id="frame-1",
        page_id="page-1",
        x_pt=10.0,
        y_pt=20.0,
        w_pt=300.0,
        h_pt=400.0,
        rotation_deg=15.0,
        skew_deg=2.0,
        z_order=3,
        locked=True,
        visible=False,
        object_style_ref="object-style-A",
        text_wrap="box",
        padding=Padding(1.0, 2.0, 3.0, 4.0),
        parent_group_id=None,
    )
    base.update(overrides)
    return base


def _normalize(value: Any) -> Any:
    """Convert tuples to lists so ``asdict`` and roundtrip dicts compare equal."""
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(v) for v in value]
    return value


# --- bbox -------------------------------------------------------------------


def test_bbox_ignores_rotation_and_skew() -> None:
    frame = ShapeFrame(**_base_kwargs(), shape_kind="rect")
    bbox = frame.bbox()
    assert bbox == Rect(10.0, 20.0, 300.0, 400.0)


# --- TextFrame --------------------------------------------------------------


def test_text_frame_roundtrip_preserves_all_fields() -> None:
    frame = TextFrame(
        **_base_kwargs(id="text-1"),
        story_ref="story-A",
        story_index=2,
        columns=3,
        gutter_pt=12.0,
        column_rule=ColumnRule(color_ref="black", width_pt=0.75, dash_pattern=(2.0, 1.0)),
        text_direction="rtl",
        vertical_align="justify",
    )
    data = frame.to_dict()
    assert data["kind"] == "text"
    rebuilt = Frame.from_dict(data)
    assert isinstance(rebuilt, TextFrame)
    assert _normalize(dataclasses.asdict(rebuilt)) == _normalize(dataclasses.asdict(frame))


def test_text_frame_column_rects_three_columns_with_gutter() -> None:
    frame = TextFrame(
        id="t",
        page_id="p",
        x_pt=0.0,
        y_pt=0.0,
        w_pt=300.0,
        h_pt=400.0,
        story_ref="s",
        columns=3,
        gutter_pt=12.0,
    )
    rects = frame.column_rects()
    assert len(rects) == 3
    # Three equal-width columns separated by two 12pt gutters: (300 - 24) / 3 = 92.
    expected_w = (300.0 - 2 * 12.0) / 3
    for i, rect in enumerate(rects):
        assert rect.w == pytest.approx(expected_w)
        assert rect.h == pytest.approx(400.0)
        assert rect.x == pytest.approx(i * (expected_w + 12.0))
        assert rect.y == pytest.approx(0.0)
    # Gaps are exactly 12pt.
    for left, right in itertools.pairwise(rects):
        gap = right.x - (left.x + left.w)
        assert gap == pytest.approx(12.0)


def test_text_frame_column_rects_honors_padding() -> None:
    frame = TextFrame(
        id="t",
        page_id="p",
        x_pt=10.0,
        y_pt=20.0,
        w_pt=300.0,
        h_pt=400.0,
        padding=Padding(top=5.0, right=5.0, bottom=5.0, left=5.0),
        story_ref="s",
        columns=2,
        gutter_pt=10.0,
    )
    rects = frame.column_rects()
    inner_w = 300.0 - 10.0
    inner_h = 400.0 - 10.0
    expected_w = (inner_w - 10.0) / 2
    assert rects[0].x == pytest.approx(15.0)
    assert rects[0].y == pytest.approx(25.0)
    assert rects[0].w == pytest.approx(expected_w)
    assert rects[0].h == pytest.approx(inner_h)
    assert rects[1].x == pytest.approx(15.0 + expected_w + 10.0)


def test_text_frame_column_rects_rejects_zero_columns() -> None:
    frame = TextFrame(
        id="t", page_id="p", x_pt=0, y_pt=0, w_pt=100, h_pt=100, story_ref="s", columns=0
    )
    with pytest.raises(ValueError):
        frame.column_rects()


# --- ImageFrame -------------------------------------------------------------


def test_image_frame_roundtrip_preserves_all_fields() -> None:
    frame = ImageFrame(
        **_base_kwargs(id="img-1"),
        asset_ref="a" * 64,
        fit="fill",
        crop=Rect(1.0, 2.0, 50.0, 60.0),
        image_rotation_deg=30.0,
    )
    data = frame.to_dict()
    assert data["kind"] == "image"
    rebuilt = Frame.from_dict(data)
    assert isinstance(rebuilt, ImageFrame)
    assert _normalize(dataclasses.asdict(rebuilt)) == _normalize(dataclasses.asdict(frame))


# --- ShapeFrame -------------------------------------------------------------


def test_shape_frame_roundtrip_preserves_all_fields() -> None:
    frame = ShapeFrame(
        **_base_kwargs(id="shape-1"),
        shape_kind="polygon",
        points=[(0.0, 0.0), (10.0, 0.0), (5.0, 8.0)],
        stroke=Stroke(color_ref="ink", width_pt=2.0, dash_pattern=(4.0, 2.0)),
        fill=Fill(color_ref="paper"),
        corner_radius_pt=4.0,
    )
    data = frame.to_dict()
    assert data["kind"] == "shape"
    rebuilt = Frame.from_dict(data)
    assert isinstance(rebuilt, ShapeFrame)
    assert _normalize(dataclasses.asdict(rebuilt)) == _normalize(dataclasses.asdict(frame))
    # Points come back as tuples even though JSON-style lists were used in transit.
    assert all(isinstance(p, tuple) for p in rebuilt.points)


# --- GroupFrame -------------------------------------------------------------


def test_group_frame_roundtrip_preserves_children() -> None:
    frame = GroupFrame(
        **_base_kwargs(id="group-1"),
        child_ids=["a", "b", "c"],
    )
    data = frame.to_dict()
    assert data["kind"] == "group"
    rebuilt = Frame.from_dict(data)
    assert isinstance(rebuilt, GroupFrame)
    assert rebuilt.child_ids == ["a", "b", "c"]
    assert _normalize(dataclasses.asdict(rebuilt)) == _normalize(dataclasses.asdict(frame))


# --- discriminator dispatch -------------------------------------------------


def test_from_dict_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        Frame.from_dict({"kind": "nonsense"})


# --- group membership invariant --------------------------------------------


def test_validate_group_membership_accepts_proper_parent() -> None:
    group = GroupFrame(
        id="g1", page_id="p", x_pt=0, y_pt=0, w_pt=100, h_pt=100, child_ids=["c1"]
    )
    child = ShapeFrame(
        id="c1",
        page_id="p",
        x_pt=10,
        y_pt=10,
        w_pt=20,
        h_pt=20,
        parent_group_id="g1",
        shape_kind="rect",
    )
    validate_group_membership(child, group)


def test_validate_group_membership_rejects_non_group_parent() -> None:
    parent = ShapeFrame(
        id="not-a-group",
        page_id="p",
        x_pt=0,
        y_pt=0,
        w_pt=10,
        h_pt=10,
        shape_kind="rect",
    )
    child = ShapeFrame(
        id="c1",
        page_id="p",
        x_pt=0,
        y_pt=0,
        w_pt=10,
        h_pt=10,
        parent_group_id="not-a-group",
        shape_kind="rect",
    )
    with pytest.raises(ValueError):
        validate_group_membership(child, parent)


def test_validate_group_membership_rejects_id_mismatch() -> None:
    group = GroupFrame(id="g1", page_id="p", x_pt=0, y_pt=0, w_pt=10, h_pt=10)
    child = ShapeFrame(
        id="c1",
        page_id="p",
        x_pt=0,
        y_pt=0,
        w_pt=10,
        h_pt=10,
        parent_group_id="g2",
        shape_kind="rect",
    )
    with pytest.raises(ValueError):
        validate_group_membership(child, group)


def test_validate_group_membership_rejects_dangling_parent_ref() -> None:
    child = ShapeFrame(
        id="c1",
        page_id="p",
        x_pt=0,
        y_pt=0,
        w_pt=10,
        h_pt=10,
        parent_group_id="g1",
        shape_kind="rect",
    )
    with pytest.raises(ValueError):
        validate_group_membership(child, None)
