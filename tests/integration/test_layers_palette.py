"""Integration tests for the Layers palette (unit #24).

These tests exercise the palette with a minimal in-test stand-in for a
document / page. The palette accesses its dependencies via the
``_DocumentLike`` Protocol declared in ``msword.ui.palettes.layers``;
anything that quacks the same shape works.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from PySide6.QtCore import QObject, QPoint, Qt, Signal
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QAbstractItemView

from msword.model.layer import Layer
from msword.ui.palettes.layers import (
    COL_LOCK,
    COL_VISIBLE,
    LayersPalette,
    ReorderLayersCommand,
    SetLayerLockCommand,
    SetLayerVisibilityCommand,
    _compute_reorder,
)

# ---------------------------------------------------------------------------
# In-test stand-ins for Document/Page/UndoStack
# ---------------------------------------------------------------------------


@dataclass
class _Page:
    layers: list[Layer] = field(default_factory=list)


class _UndoStack:
    def __init__(self) -> None:
        self.pushed: list[Any] = []

    def push(self, command: object) -> None:
        self.pushed.append(command)
        # Match QUndoStack: pushing a command calls redo() once.
        redo = getattr(command, "redo", None)
        if callable(redo):
            redo()


class _Document(QObject):
    current_page_changed = Signal()
    layers_changed = Signal()

    def __init__(self, page: _Page) -> None:
        super().__init__()
        self._page = page
        self._undo_stack = _UndoStack()

    @property
    def current_page(self) -> _Page:
        return self._page

    @property
    def undo_stack(self) -> _UndoStack:
        return self._undo_stack


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def page_with_two_layers() -> _Page:
    return _Page(
        layers=[
            Layer(id="L-top", name="Top", z_order=1),
            Layer(id="L-bot", name="Bottom", z_order=0),
        ]
    )


@pytest.fixture
def doc(page_with_two_layers: _Page) -> _Document:
    return _Document(page_with_two_layers)


@pytest.fixture
def palette(qtbot, doc: _Document) -> LayersPalette:  # type: ignore[no-untyped-def]
    pal = LayersPalette(document=doc)
    qtbot.addWidget(pal)
    return pal


# ---------------------------------------------------------------------------
# Layer dataclass
# ---------------------------------------------------------------------------


def test_layer_defaults() -> None:
    layer = Layer(id="X", name="X")
    assert layer.visible is True
    assert layer.locked is False
    assert layer.color == (200, 200, 200)
    assert layer.z_order == 0


def test_layer_uses_slots() -> None:
    layer = Layer(id="X", name="X")
    with pytest.raises(AttributeError):
        layer.something_new = 1  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Palette: rows reflect the current page
# ---------------------------------------------------------------------------


def test_two_layers_in_page_render_two_rows(palette: LayersPalette) -> None:
    model = palette.model()
    assert model.rowCount() == 2
    # Names match.
    names = [model.layer_at(row).name for row in range(model.rowCount())]  # type: ignore[union-attr]
    assert names == ["Top", "Bottom"]


def test_palette_refreshes_on_current_page_changed(
    qtbot,  # type: ignore[no-untyped-def]
    doc: _Document,
    palette: LayersPalette,
) -> None:
    # Replace the page in-place via the same `_Document` and emit the
    # signal — palette should re-bind the model.
    new_page = _Page(layers=[Layer(id="A", name="A")])
    doc._page = new_page
    doc.current_page_changed.emit()
    assert palette.model().rowCount() == 1


# ---------------------------------------------------------------------------
# Visibility / lock toggles push commands
# ---------------------------------------------------------------------------


def test_click_visibility_pushes_set_visibility_false(
    palette: LayersPalette, doc: _Document
) -> None:
    tree = palette.tree_view()
    model = palette.model()
    index = model.index(0, COL_VISIBLE)
    rect = tree.visualRect(index)
    assert rect.isValid()
    # Simulate the click via the view's mousePressEvent path used by the
    # palette (we call the public toggle to keep the test deterministic
    # across Qt styles, but the click path is wired by the view — see
    # `test_visibility_click_event` below for the event-level coverage).
    palette._toggle_visibility("L-top")

    pushed = doc.undo_stack.pushed
    assert len(pushed) == 1
    cmd = pushed[0]
    assert isinstance(cmd, SetLayerVisibilityCommand)
    assert cmd.layer_id == "L-top"
    assert cmd.visible is False
    # Effect applied:
    assert doc.current_page.layers[0].visible is False


def test_visibility_click_event_pushes_command(
    qtbot,  # type: ignore[no-untyped-def]
    palette: LayersPalette,
    doc: _Document,
) -> None:
    tree = palette.tree_view()
    model = palette.model()
    index = model.index(0, COL_VISIBLE)
    rect = tree.visualRect(index)
    if not rect.isValid():
        pytest.skip("layout not realized")
    qtbot.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    pushed = doc.undo_stack.pushed
    assert any(isinstance(cmd, SetLayerVisibilityCommand) for cmd in pushed)


def test_click_lock_pushes_set_lock_command(
    palette: LayersPalette, doc: _Document
) -> None:
    palette._toggle_lock("L-bot")
    pushed = doc.undo_stack.pushed
    assert len(pushed) == 1
    cmd = pushed[0]
    assert isinstance(cmd, SetLayerLockCommand)
    assert cmd.layer_id == "L-bot"
    assert cmd.locked is True
    assert doc.current_page.layers[1].locked is True


def test_lock_click_event_pushes_command(
    qtbot,  # type: ignore[no-untyped-def]
    palette: LayersPalette,
    doc: _Document,
) -> None:
    tree = palette.tree_view()
    model = palette.model()
    index = model.index(1, COL_LOCK)
    rect = tree.visualRect(index)
    if not rect.isValid():
        pytest.skip("layout not realized")
    qtbot.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    pushed = doc.undo_stack.pushed
    assert any(isinstance(cmd, SetLayerLockCommand) for cmd in pushed)


# ---------------------------------------------------------------------------
# Drag-reorder pushes ReorderLayersCommand
# ---------------------------------------------------------------------------


def test_reorder_pushes_reorder_command_via_callback(
    palette: LayersPalette, doc: _Document
) -> None:
    # Bottom moves above Top.
    palette._reorder(["L-bot", "L-top"])
    pushed = doc.undo_stack.pushed
    assert len(pushed) == 1
    cmd = pushed[0]
    assert isinstance(cmd, ReorderLayersCommand)
    assert cmd.order == ["L-bot", "L-top"]
    # Page applied:
    page_ids = [layer.id for layer in doc.current_page.layers]
    assert page_ids == ["L-bot", "L-top"]
    # z_order reflects palette order (top of palette = highest z_order).
    assert doc.current_page.layers[0].z_order == 1
    assert doc.current_page.layers[1].z_order == 0


def test_reorder_drop_event_pushes_command(
    qtbot,  # type: ignore[no-untyped-def]
    palette: LayersPalette,
    doc: _Document,
) -> None:
    tree = palette.tree_view()
    model = palette.model()
    # Drag the top layer (row 0) and drop it below the bottom layer (row 1).
    src_index = model.index(0, 0)
    indexes = [src_index]
    mime = model.mimeData(indexes)
    assert mime is not None
    target_rect = tree.visualRect(model.index(1, 0))
    if not target_rect.isValid():
        pytest.skip("layout not realized")
    drop_pos = target_rect.bottomLeft() + QPoint(2, -1)
    drop_event = QDropEvent(
        drop_pos,
        Qt.DropAction.MoveAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QDropEvent.Type.Drop,
    )
    drop_event.setDropAction(Qt.DropAction.MoveAction)
    # Force the indicator position so the view's calculation is deterministic.
    tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
    tree.dropEvent(drop_event)

    pushed = doc.undo_stack.pushed
    assert any(isinstance(cmd, ReorderLayersCommand) for cmd in pushed)


# ---------------------------------------------------------------------------
# _compute_reorder unit tests (covers the drop-target math)
# ---------------------------------------------------------------------------


def test_compute_reorder_move_top_to_bottom() -> None:
    assert _compute_reorder(["A", "B", "C"], ["A"], 3) == ["B", "C", "A"]


def test_compute_reorder_move_bottom_to_top() -> None:
    assert _compute_reorder(["A", "B", "C"], ["C"], 0) == ["C", "A", "B"]


def test_compute_reorder_no_op_when_dropped_on_self() -> None:
    assert _compute_reorder(["A", "B"], ["A"], 0) == ["A", "B"]


# ---------------------------------------------------------------------------
# Commands round-trip
# ---------------------------------------------------------------------------


def test_visibility_command_undo_restores_previous(
    page_with_two_layers: _Page,
) -> None:
    cmd = SetLayerVisibilityCommand(
        page=page_with_two_layers, layer_id="L-top", visible=False
    )
    cmd.redo()
    assert page_with_two_layers.layers[0].visible is False
    cmd.undo()
    assert page_with_two_layers.layers[0].visible is True


def test_lock_command_undo_restores_previous(page_with_two_layers: _Page) -> None:
    cmd = SetLayerLockCommand(
        page=page_with_two_layers, layer_id="L-bot", locked=True
    )
    cmd.redo()
    assert page_with_two_layers.layers[1].locked is True
    cmd.undo()
    assert page_with_two_layers.layers[1].locked is False


def test_reorder_command_undo_restores_previous_order(
    page_with_two_layers: _Page,
) -> None:
    original = [layer.id for layer in page_with_two_layers.layers]
    cmd = ReorderLayersCommand(
        page=page_with_two_layers, order=["L-bot", "L-top"]
    )
    cmd.redo()
    assert [layer.id for layer in page_with_two_layers.layers] == ["L-bot", "L-top"]
    cmd.undo()
    assert [layer.id for layer in page_with_two_layers.layers] == original
