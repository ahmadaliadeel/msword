"""Integration tests for the tools palette and basic tools (unit 20)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QGraphicsView

from msword.ui.tools import (
    HandTool,
    ItemMoverTool,
    LineTool,
    OvalTool,
    PenTool,
    PictureFrameTool,
    PolygonTool,
    RectTool,
    SelectionTool,
    TextFrameTool,
    ZoomTool,
)
from msword.ui.tools._stubs import StubCanvas
from msword.ui.tools_palette import DEFAULT_TOOL_TYPES, ToolsPalette

if TYPE_CHECKING:
    from msword.ui.tools.base import Tool


_NoMod = Qt.KeyboardModifier.NoModifier


def _mouse_event(
    event_type: QEvent.Type,
    scene_pos: tuple[float, float],
    *,
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
    buttons: Qt.MouseButton = Qt.MouseButton.LeftButton,
    modifiers: Qt.KeyboardModifier = _NoMod,
) -> QMouseEvent:
    return QMouseEvent(
        event_type,
        QPointF(*scene_pos),
        button,
        buttons,
        modifiers,
    )


def _press(
    scene_pos: tuple[float, float],
    modifiers: Qt.KeyboardModifier = _NoMod,
) -> QMouseEvent:
    return _mouse_event(QEvent.Type.MouseButtonPress, scene_pos, modifiers=modifiers)


def _move(scene_pos: tuple[float, float]) -> QMouseEvent:
    return _mouse_event(QEvent.Type.MouseMove, scene_pos)


def _release(
    scene_pos: tuple[float, float],
    modifiers: Qt.KeyboardModifier = _NoMod,
) -> QMouseEvent:
    return _mouse_event(
        QEvent.Type.MouseButtonRelease,
        scene_pos,
        buttons=Qt.MouseButton.NoButton,
        modifiers=modifiers,
    )


def _drive(tool: Tool, *, start: tuple[float, float], end: tuple[float, float]) -> None:
    """Drive a tool through a single press/move/release gesture."""
    tool.on_mouse_press(_press(start), QPointF(*start))
    tool.on_mouse_move(_move(end), QPointF(*end))
    tool.on_mouse_release(_release(end), QPointF(*end))


# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------


@pytest.fixture
def palette(qtbot, canvas):  # type: ignore[no-untyped-def]
    p = ToolsPalette(canvas=canvas)
    qtbot.addWidget(p)
    return p


@pytest.fixture
def canvas() -> StubCanvas:
    return StubCanvas()


def test_palette_has_eleven_actions_in_order(palette: ToolsPalette) -> None:
    expected_order: tuple[type[Tool], ...] = (
        SelectionTool,
        ItemMoverTool,
        TextFrameTool,
        PictureFrameTool,
        RectTool,
        OvalTool,
        PolygonTool,
        PenTool,
        LineTool,
        HandTool,
        ZoomTool,
    )
    assert expected_order == DEFAULT_TOOL_TYPES
    assert len(palette.actions_in_order) == 11
    actual = [type(a.data()) for a in palette.actions_in_order]
    assert actual == list(expected_order)


def test_palette_orientation_and_dock_area(palette: ToolsPalette) -> None:
    assert palette.orientation() == Qt.Orientation.Vertical
    assert palette.allowedAreas() == Qt.ToolBarArea.LeftToolBarArea


def test_palette_actions_are_exclusive_and_checkable(palette: ToolsPalette) -> None:
    actions = palette.actions_in_order
    assert all(a.isCheckable() for a in actions)
    # First tool starts checked.
    assert actions[0].isChecked()
    # Trigger the third action (TextFrameTool).
    actions[2].setChecked(True)
    actions[2].trigger()
    checked = [a for a in actions if a.isChecked()]
    assert len(checked) == 1
    assert checked[0] is actions[2]


def test_palette_initial_tool_is_selection(palette: ToolsPalette, canvas: StubCanvas) -> None:
    assert isinstance(canvas.active_tool, SelectionTool)


def test_palette_toggle_calls_set_tool(palette: ToolsPalette, canvas: StubCanvas) -> None:
    actions = palette.actions_in_order
    actions[2].setChecked(True)  # TextFrameTool
    actions[2].trigger()
    assert isinstance(canvas.active_tool, TextFrameTool)


# ---------------------------------------------------------------------------
# TextFrameTool drag → AddFrameCommand
# ---------------------------------------------------------------------------


def test_text_frame_tool_drag_creates_text_frame(canvas: StubCanvas) -> None:
    tool = TextFrameTool()
    canvas.set_tool(tool)
    _drive(tool, start=(50.0, 50.0), end=(150.0, 150.0))

    assert len(canvas.executed_commands) == 1
    command = canvas.executed_commands[0]
    assert command.kind == "text"
    assert command.rect.x() == pytest.approx(50.0)
    assert command.rect.y() == pytest.approx(50.0)
    assert command.rect.width() == pytest.approx(100.0)
    assert command.rect.height() == pytest.approx(100.0)
    # The command was redo()'d → page has the new frame.
    assert len(canvas.current_page.frames) == 1
    frame = canvas.current_page.frames[0]
    assert (frame.x, frame.y, frame.w, frame.h) == (50.0, 50.0, 100.0, 100.0)
    assert frame.kind == "text"


def test_text_frame_tool_zero_drag_does_nothing(canvas: StubCanvas) -> None:
    tool = TextFrameTool()
    canvas.set_tool(tool)
    _drive(tool, start=(50.0, 50.0), end=(50.0, 50.0))
    assert canvas.executed_commands == []


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def test_selection_tool_click_selects_frame_under_cursor(canvas: StubCanvas) -> None:
    # Seed the page with a frame via a TextFrameTool drag.
    text_tool = TextFrameTool()
    canvas.set_tool(text_tool)
    _drive(text_tool, start=(20.0, 20.0), end=(120.0, 120.0))

    # Switch to selection and click inside the frame.
    sel = SelectionTool()
    canvas.set_tool(sel)
    sel.on_mouse_press(_press((50.0, 50.0)), QPointF(50.0, 50.0))
    sel.on_mouse_release(_release((50.0, 50.0)), QPointF(50.0, 50.0))

    assert len(canvas.selected) == 1
    assert canvas.selected[0] is canvas.current_page.frames[0]


def test_selection_tool_click_outside_clears_selection(canvas: StubCanvas) -> None:
    text_tool = TextFrameTool()
    canvas.set_tool(text_tool)
    _drive(text_tool, start=(20.0, 20.0), end=(120.0, 120.0))

    sel = SelectionTool()
    canvas.set_tool(sel)
    canvas.selected.append(canvas.current_page.frames[0])
    sel.on_mouse_press(_press((500.0, 500.0)), QPointF(500.0, 500.0))
    sel.on_mouse_release(_release((500.0, 500.0)), QPointF(500.0, 500.0))

    assert canvas.selected == []


def test_selection_tool_sets_rubber_band_drag_mode(canvas: StubCanvas) -> None:
    sel = SelectionTool()
    canvas.set_tool(sel)
    assert canvas.drag_mode == QGraphicsView.DragMode.RubberBandDrag


# ---------------------------------------------------------------------------
# Hand tool
# ---------------------------------------------------------------------------


def test_hand_tool_press_sets_scroll_hand_drag(canvas: StubCanvas) -> None:
    hand = HandTool()
    canvas.set_tool(hand)
    assert canvas.drag_mode == QGraphicsView.DragMode.ScrollHandDrag

    # Press also asserts the mode (defensive against a canvas reset between
    # activate and press).
    canvas.drag_mode = QGraphicsView.DragMode.NoDrag
    hand.on_mouse_press(_press((10.0, 10.0)), QPointF(10.0, 10.0))
    assert canvas.drag_mode == QGraphicsView.DragMode.ScrollHandDrag


# ---------------------------------------------------------------------------
# Other frame-creation tools
# ---------------------------------------------------------------------------


def test_picture_frame_tool_drag_creates_image_frame(canvas: StubCanvas) -> None:
    tool = PictureFrameTool()
    canvas.set_tool(tool)
    _drive(tool, start=(0.0, 0.0), end=(80.0, 60.0))
    assert canvas.executed_commands[0].kind == "image"


def test_rect_tool_drag_creates_shape_frame_rect(canvas: StubCanvas) -> None:
    tool = RectTool()
    canvas.set_tool(tool)
    _drive(tool, start=(0.0, 0.0), end=(20.0, 20.0))
    cmd = canvas.executed_commands[0]
    assert cmd.kind == "shape"
    assert cmd.extra == {"shape": "rect"}


def test_oval_tool_drag_creates_shape_frame_oval(canvas: StubCanvas) -> None:
    tool = OvalTool()
    canvas.set_tool(tool)
    _drive(tool, start=(0.0, 0.0), end=(20.0, 20.0))
    cmd = canvas.executed_commands[0]
    assert cmd.kind == "shape"
    assert cmd.extra == {"shape": "oval"}


def test_line_tool_drag_creates_line_shape(canvas: StubCanvas) -> None:
    tool = LineTool()
    canvas.set_tool(tool)
    tool.on_mouse_press(_press((10.0, 10.0)), QPointF(10.0, 10.0))
    tool.on_mouse_release(_release((110.0, 60.0)), QPointF(110.0, 60.0))
    cmd = canvas.executed_commands[0]
    assert cmd.kind == "shape"
    assert cmd.extra["shape"] == "line"
    assert cmd.extra["line"] == (10.0, 10.0, 110.0, 60.0)


def test_polygon_tool_double_click_closes(canvas: StubCanvas) -> None:
    tool = PolygonTool()
    canvas.set_tool(tool)
    for x, y in [(0.0, 0.0), (50.0, 0.0), (25.0, 50.0)]:
        tool.on_mouse_press(_press((x, y)), QPointF(x, y))

    # Double click anywhere closes.
    dbl = _mouse_event(QEvent.Type.MouseButtonDblClick, (25.0, 25.0))
    tool.on_mouse_press(dbl, QPointF(25.0, 25.0))

    cmd = canvas.executed_commands[0]
    assert cmd.kind == "shape"
    assert cmd.extra["shape"] == "polygon"
    assert cmd.extra["vertices"] == [(0.0, 0.0), (50.0, 0.0), (25.0, 50.0)]


def test_pen_tool_double_click_finishes(canvas: StubCanvas) -> None:
    tool = PenTool()
    canvas.set_tool(tool)
    for x, y in [(0.0, 0.0), (10.0, 5.0)]:
        tool.on_mouse_press(_press((x, y)), QPointF(x, y))

    dbl = _mouse_event(QEvent.Type.MouseButtonDblClick, (10.0, 5.0))
    tool.on_mouse_press(dbl, QPointF(10.0, 5.0))

    cmd = canvas.executed_commands[0]
    assert cmd.kind == "shape"
    assert cmd.extra["shape"] == "polyline"


# ---------------------------------------------------------------------------
# Item mover
# ---------------------------------------------------------------------------


def test_item_mover_tool_translates_target(canvas: StubCanvas) -> None:
    text_tool = TextFrameTool()
    canvas.set_tool(text_tool)
    _drive(text_tool, start=(20.0, 20.0), end=(60.0, 60.0))
    frame = canvas.current_page.frames[0]
    assert (frame.x, frame.y) == (20.0, 20.0)

    mover = ItemMoverTool()
    canvas.set_tool(mover)
    mover.on_mouse_press(_press((30.0, 30.0)), QPointF(30.0, 30.0))
    mover.on_mouse_move(_move((50.0, 35.0)), QPointF(50.0, 35.0))
    mover.on_mouse_release(_release((50.0, 35.0)), QPointF(50.0, 35.0))

    assert (frame.x, frame.y) == pytest.approx((40.0, 25.0))


# ---------------------------------------------------------------------------
# Zoom
# ---------------------------------------------------------------------------


def test_zoom_tool_click_zooms_in(canvas: StubCanvas) -> None:
    zooms: list[tuple[float, QPointF]] = []
    canvas.zoom_by = lambda factor, at: zooms.append((factor, at))  # type: ignore[attr-defined]

    zoom = ZoomTool()
    canvas.set_tool(zoom)
    zoom.on_mouse_press(_press((50.0, 50.0)), QPointF(50.0, 50.0))
    zoom.on_mouse_release(_release((50.0, 50.0)), QPointF(50.0, 50.0))

    assert len(zooms) == 1
    factor, _at = zooms[0]
    assert factor == pytest.approx(2.0)


def test_zoom_tool_alt_click_zooms_out(canvas: StubCanvas) -> None:
    zooms: list[tuple[float, QPointF]] = []
    canvas.zoom_by = lambda factor, at: zooms.append((factor, at))  # type: ignore[attr-defined]

    zoom = ZoomTool()
    canvas.set_tool(zoom)
    pos = (50.0, 50.0)
    zoom.on_mouse_press(_press(pos, Qt.KeyboardModifier.AltModifier), QPointF(*pos))
    zoom.on_mouse_release(_release(pos, Qt.KeyboardModifier.AltModifier), QPointF(*pos))

    assert zooms[0][0] == pytest.approx(0.5)
