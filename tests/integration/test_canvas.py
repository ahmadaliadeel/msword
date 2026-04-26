"""Integration tests for `msword.ui.canvas` (unit 16, spec §6).

Run under `pytest-qt` with `QT_QPA_PLATFORM=offscreen` (set by `conftest.py`).
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsSceneMouseEvent

from msword.ui.canvas import (
    CanvasView,
    Document,
    ImageFrame,
    Page,
    ShapeFrame,
    ShapeKind,
    Story,
    TableFrame,
    TextFrame,
    ViewMode,
)
from msword.ui.canvas._stubs import (
    A4_HEIGHT,
    A4_WIDTH,
    FrameKind,
    MoveFrameCommand,
    ResizeFrameCommand,
)


def _make_scene_mouse_event(
    event_type: QEvent.Type,
    item: QGraphicsItem,
    scene_pos: QPointF,
    *,
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
    buttons: Qt.MouseButton = Qt.MouseButton.LeftButton,
) -> QGraphicsSceneMouseEvent:
    event = QGraphicsSceneMouseEvent(event_type)
    event.setScenePos(scene_pos)
    event.setPos(item.mapFromScene(scene_pos))
    event.setButton(button)
    event.setButtons(buttons)
    return event


def _build_document() -> Document:
    """A two-page doc with one of each frame type on page 1."""
    text = TextFrame(
        id="t1",
        kind=FrameKind.TEXT,
        x=72.0,
        y=72.0,
        w=300.0,
        h=200.0,
        story=Story(text="Hello world. " * 30),
        columns=2,
        gutter=12.0,
        column_rule=True,
    )
    image = ImageFrame(
        id="i1",
        kind=FrameKind.IMAGE,
        x=72.0,
        y=300.0,
        w=160.0,
        h=120.0,
        asset_path=None,  # exercises placeholder path
    )
    shape = ShapeFrame(
        id="s1",
        kind=FrameKind.SHAPE,
        x=300.0,
        y=300.0,
        w=80.0,
        h=80.0,
        shape_kind=ShapeKind.OVAL,
    )
    table = TableFrame(
        id="tb1",
        kind=FrameKind.TABLE,
        x=72.0,
        y=460.0,
        w=200.0,
        h=120.0,
        rows=2,
        cols=2,
        cells=[["a", "b"], ["c", "d"]],
    )
    page1 = Page(id="p1", frames=[text, image, shape, table])
    page2 = Page(id="p2", frames=[])
    return Document(pages=[page1, page2])


@pytest.fixture
def view(qtbot) -> CanvasView:  # type: ignore[no-untyped-def]
    canvas = CanvasView()
    qtbot.addWidget(canvas)
    canvas.resize(800, 1000)
    canvas.set_document(_build_document())
    return canvas


def _send_mouse(item, kind: str, scene_pos: QPointF) -> None:  # type: ignore[no-untyped-def]
    """Dispatch a synthetic mouse event of *kind* (press/move/release) to *item*."""
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent

    type_map = {
        "press": QEvent.Type.GraphicsSceneMousePress,
        "move": QEvent.Type.GraphicsSceneMouseMove,
        "release": QEvent.Type.GraphicsSceneMouseRelease,
    }
    ev = QGraphicsSceneMouseEvent(type_map[kind])
    ev.setScenePos(scene_pos)
    ev.setPos(item.mapFromScene(scene_pos))
    ev.setButton(Qt.MouseButton.LeftButton)
    ev.setButtons(Qt.MouseButton.LeftButton)
    if kind == "press":
        item.mousePressEvent(ev)
    elif kind == "move":
        item.mouseMoveEvent(ev)
    else:
        item.mouseReleaseEvent(ev)


# -- 1. Build scene, render to QImage, assert non-empty -------------------


def test_renders_non_empty(view: CanvasView) -> None:
    scene = view.scene()
    assert scene is not None
    image = QImage(640, 800, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        scene.render(painter, QRectF(0, 0, 640, 800), scene.sceneRect())
    finally:
        painter.end()
    # Find any non-transparent pixel.
    found = False
    for y in range(0, 800, 16):
        for x in range(0, 640, 16):
            if image.pixelColor(x, y).alpha() > 0:
                found = True
                break
        if found:
            break
    assert found, "scene rendered no visible pixels"


def test_scene_has_page_and_frame_items(view: CanvasView) -> None:
    assert len(view.page_items) == 2
    # Page 1 has 4 frames; page 2 has 0.
    assert len(view.frame_items) == 4


# -- 2. Click frame → selected --------------------------------------------


def test_click_frame_selects_it(view: CanvasView, qtbot) -> None:  # type: ignore[no-untyped-def]
    text_item = view.frame_items[0]
    centre_scene = text_item.mapToScene(text_item.frame.w / 2, text_item.frame.h / 2)
    _send_mouse(text_item, "press", centre_scene)
    _send_mouse(text_item, "release", centre_scene)
    assert text_item.isSelected()


# -- 3. zoom_to(2.0) → transform.m11 == 2.0 --------------------------------


def test_zoom_to_sets_transform(view: CanvasView) -> None:
    view.zoom_to(2.0)
    transform = view.transform()
    assert transform.m11() == 2.0
    assert transform.m22() == 2.0


def test_zoom_clamps(view: CanvasView) -> None:
    view.zoom_to(50.0)
    assert view.zoom == 8.0  # MAX_ZOOM
    view.zoom_to(0.001)
    assert view.zoom == 0.10  # MIN_ZOOM


# -- 4. Mode toggle flow ↔ paged updates page positions -------------------


def test_mode_toggle_updates_page_positions(view: CanvasView) -> None:
    view.set_mode(ViewMode.PAGED)
    paged_y = view.page_items[1].pos().y()
    view.set_mode(ViewMode.FLOW)
    flow_y = view.page_items[1].pos().y()
    # In paged mode there's a 24pt gap between pages; flow has none.
    assert paged_y == pytest.approx(A4_HEIGHT + 24.0)
    assert flow_y == pytest.approx(A4_HEIGHT)
    assert flow_y < paged_y


def test_toggle_mode_round_trip(view: CanvasView) -> None:
    assert view.mode is ViewMode.PAGED
    view.toggle_mode()
    assert view.mode is ViewMode.FLOW
    view.toggle_mode()
    assert view.mode is ViewMode.PAGED


# -- 5. Frame mouse drag emits a Move command ------------------------------


def test_drag_frame_emits_move_command(view: CanvasView, qtbot) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtCore import QEvent

    captured: list[object] = []
    view.set_command_sink(captured.append)

    text_item = view.frame_items[0]
    start = text_item.mapToScene(20.0, 20.0)
    end = QPointF(start.x() + 50.0, start.y() + 30.0)
    text_item.mousePressEvent(
        _make_scene_mouse_event(QEvent.Type.GraphicsSceneMousePress, text_item, start)  # type: ignore[arg-type]
    )
    text_item.mouseMoveEvent(
        _make_scene_mouse_event(QEvent.Type.GraphicsSceneMouseMove, text_item, end)  # type: ignore[arg-type]
    )
    text_item.mouseReleaseEvent(
        _make_scene_mouse_event(QEvent.Type.GraphicsSceneMouseRelease, text_item, end)  # type: ignore[arg-type]
    )

    moves = [c for c in captured if isinstance(c, MoveFrameCommand)]
    assert len(moves) == 1
    assert moves[0].frame_id == "t1"
    assert moves[0].new_x == pytest.approx(text_item.frame.x + 50.0)
    assert moves[0].new_y == pytest.approx(text_item.frame.y + 30.0)


# -- 6. Resize handle drag emits a Resize command --------------------------


def test_resize_handle_emits_resize_command(view: CanvasView) -> None:
    from PySide6.QtCore import QEvent

    captured: list[object] = []
    view.set_command_sink(captured.append)

    text_item = view.frame_items[0]
    text_item.setSelected(True)

    # Hit the SE handle (bottom-right corner of the local rect).
    se_local = QPointF(text_item.frame.w, text_item.frame.h)
    start_scene = text_item.mapToScene(se_local)
    end_scene = QPointF(start_scene.x() + 40.0, start_scene.y() + 20.0)
    text_item.mousePressEvent(
        _make_scene_mouse_event(QEvent.Type.GraphicsSceneMousePress, text_item, start_scene)  # type: ignore[arg-type]
    )
    text_item.mouseMoveEvent(
        _make_scene_mouse_event(QEvent.Type.GraphicsSceneMouseMove, text_item, end_scene)  # type: ignore[arg-type]
    )
    text_item.mouseReleaseEvent(
        _make_scene_mouse_event(QEvent.Type.GraphicsSceneMouseRelease, text_item, end_scene)  # type: ignore[arg-type]
    )

    resizes = [c for c in captured if isinstance(c, ResizeFrameCommand)]
    assert len(resizes) == 1
    assert resizes[0].frame_id == "t1"
    assert resizes[0].new_w == pytest.approx(text_item.frame.w + 40.0)
    assert resizes[0].new_h == pytest.approx(text_item.frame.h + 20.0)


# -- 7. Fit-page sets a reasonable zoom -----------------------------------


def test_fit_page_sets_zoom(view: CanvasView) -> None:
    view.fit_page(0)
    # The fitted zoom should be > 0 and < MAX_ZOOM, scaled to viewport.
    assert 0 < view.zoom <= 8.0


def test_fit_width_uses_viewport_width(view: CanvasView) -> None:
    view.fit_width()
    # The zoom must stay in the clamp range and match the formula derived
    # from the live viewport width.
    viewport_w = max(1, view.viewport().width())
    expected = max(0.10, min(8.0, viewport_w / A4_WIDTH))
    assert view.zoom == pytest.approx(expected)


# -- 8. Hand-tool toggling -------------------------------------------------


def test_hand_tool_toggle(view: CanvasView) -> None:
    view.set_hand_tool(True)
    # The hand tool puts the view into pan mode — no exception should fire,
    # and a follow-up disable should restore the default cursor.
    view.set_hand_tool(False)


# -- 9. Overflow surfaces in composer output for short frames -------------


def test_text_overflow_indicator(qtbot) -> None:  # type: ignore[no-untyped-def]
    canvas = CanvasView()
    qtbot.addWidget(canvas)
    canvas.resize(800, 800)
    long_text = "Lorem ipsum dolor sit amet. " * 200
    cramped = TextFrame(
        id="cramped",
        kind=FrameKind.TEXT,
        x=10.0,
        y=10.0,
        w=80.0,
        h=40.0,
        story=Story(text=long_text),
        columns=1,
    )
    page = Page(id="overflow_page", frames=[cramped])
    canvas.set_document(Document(pages=[page]))
    text_item = canvas.frame_items[0]
    # Render to image and assert success.
    from msword.ui.canvas.text_frame_item import TextFrameItem

    assert isinstance(text_item, TextFrameItem)
    result = text_item._composer.compose(cramped)
    assert result.overflowed is True


# -- 10. Empty document does not crash ------------------------------------


def test_empty_document(qtbot) -> None:  # type: ignore[no-untyped-def]
    canvas = CanvasView()
    qtbot.addWidget(canvas)
    canvas.set_document(Document(pages=[]))
    assert canvas.page_items == []
    canvas.fit_page(0)  # no-op, must not raise
    canvas.fit_width()  # no-op
    canvas.set_mode(ViewMode.FLOW)  # no pages to lay out
