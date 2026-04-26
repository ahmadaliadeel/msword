"""Integration tests for the Table tool (unit 21)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from msword.ui.tools._stubs import (
    StubCanvas,
    _StubAddFrameCommand,
    _StubTableFrame,
)
from msword.ui.tools.table import TableTool

if TYPE_CHECKING:
    pass


_NoMod = Qt.KeyboardModifier.NoModifier


def _mouse_event(
    event_type: QEvent.Type,
    scene_pos: tuple[float, float],
    *,
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
    buttons: Qt.MouseButton = Qt.MouseButton.LeftButton,
    modifiers: Qt.KeyboardModifier = _NoMod,
) -> QMouseEvent:
    return QMouseEvent(event_type, QPointF(*scene_pos), button, buttons, modifiers)


def _press(scene_pos: tuple[float, float]) -> QMouseEvent:
    return _mouse_event(QEvent.Type.MouseButtonPress, scene_pos)


def _move(scene_pos: tuple[float, float]) -> QMouseEvent:
    return _mouse_event(QEvent.Type.MouseMove, scene_pos)


def _release(scene_pos: tuple[float, float]) -> QMouseEvent:
    return _mouse_event(
        QEvent.Type.MouseButtonRelease,
        scene_pos,
        buttons=Qt.MouseButton.NoButton,
    )


def _drive(tool: TableTool, *, start: tuple[float, float], end: tuple[float, float]) -> None:
    tool.on_mouse_press(_press(start), QPointF(*start))
    tool.on_mouse_move(_move(end), QPointF(*end))
    tool.on_mouse_release(_release(end), QPointF(*end))


@pytest.fixture
def canvas() -> StubCanvas:
    return StubCanvas()


def test_drag_then_dialog_pushes_add_frame_with_table_kind(
    canvas: StubCanvas, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drag a rect → mock dialog returns rows=2 cols=3 → AddFrameCommand TableFrame(2,3)."""
    tool = TableTool()
    canvas.set_tool(tool)

    # Mock the dialog: rows=2, cols=3.
    monkeypatch.setattr(tool, "_prompt_for_size", lambda: (2, 3))

    _drive(tool, start=(20, 30), end=(220, 130))

    assert len(canvas.executed_commands) == 1
    command = canvas.executed_commands[0]
    assert isinstance(command, _StubAddFrameCommand)
    assert command.kind == "table"
    assert command.extra == {"rows": 2, "cols": 3}
    assert command.rect.x() == pytest.approx(20)
    assert command.rect.y() == pytest.approx(30)
    assert command.rect.width() == pytest.approx(200)
    assert command.rect.height() == pytest.approx(100)

    # The redo() ran inside push_command → a TableFrame should be on the page.
    assert len(canvas.current_page.frames) == 1
    frame = canvas.current_page.frames[0]
    assert isinstance(frame, _StubTableFrame)
    assert frame.rows == 2
    assert frame.cols == 3
    assert frame.kind == "table"


def test_dialog_cancel_pushes_nothing(
    canvas: StubCanvas, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the user cancels the dialog, no command is pushed and no frame appears."""
    tool = TableTool()
    canvas.set_tool(tool)

    monkeypatch.setattr(tool, "_prompt_for_size", lambda: (None, None))

    _drive(tool, start=(0, 0), end=(100, 100))

    assert canvas.executed_commands == []
    assert canvas.current_page.frames == []


def test_zero_area_drag_skips_dialog(
    canvas: StubCanvas, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A zero-size drag (just a click) must not even open the dialog."""
    tool = TableTool()
    canvas.set_tool(tool)

    called = {"n": 0}

    def _prompt() -> tuple[int | None, int | None]:
        called["n"] += 1
        return (3, 3)

    monkeypatch.setattr(tool, "_prompt_for_size", _prompt)

    _drive(tool, start=(50, 50), end=(50, 50))

    assert called["n"] == 0
    assert canvas.executed_commands == []


def test_table_size_dialog_default_three_by_three(qtbot) -> None:  # type: ignore[no-untyped-def]
    """Default dialog values per spec are 3 x 3."""
    from msword.ui.tools.table import TableSizeDialog

    dialog = TableSizeDialog()
    qtbot.addWidget(dialog)
    assert dialog.rows() == 3
    assert dialog.cols() == 3
