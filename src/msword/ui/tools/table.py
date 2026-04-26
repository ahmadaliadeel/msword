"""Table tool: drag a rectangle, prompt for rows x cols, insert a TableFrame.

Per spec §9 / §12 (unit 21): the Table tool is modal — the user drags out a
rectangle on the canvas, releases, and is prompted with a tiny dialog for the
row and column count (default 3 x 3). On accept, an ``AddFrameCommand`` of
kind ``"table"`` is pushed onto the canvas's undo stack, carrying the rows
and cols as ``extra`` kwargs so the model layer (unit 7) can build the
``TableFrame`` accordingly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsView,
    QSpinBox,
)

from msword.ui.tools._stubs import AddFrameCommand, Tool

if TYPE_CHECKING:
    from PySide6.QtGui import QMouseEvent


_DEFAULT_ROWS = 3
_DEFAULT_COLS = 3
_MIN_DIMENSION = 1
_MAX_DIMENSION = 999


class TableSizeDialog(QDialog):
    """Tiny modal dialog asking the user for rows x columns.

    Kept as a public class so tests (and any future right-click "Insert table"
    flow) can construct it directly.
    """

    def __init__(self, parent: Any | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Insert Table")

        self._rows_spin = QSpinBox(self)
        self._rows_spin.setRange(_MIN_DIMENSION, _MAX_DIMENSION)
        self._rows_spin.setValue(_DEFAULT_ROWS)

        self._cols_spin = QSpinBox(self)
        self._cols_spin.setRange(_MIN_DIMENSION, _MAX_DIMENSION)
        self._cols_spin.setValue(_DEFAULT_COLS)

        form = QFormLayout(self)
        form.addRow("Rows:", self._rows_spin)
        form.addRow("Columns:", self._cols_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def rows(self) -> int:
        return int(self._rows_spin.value())

    def cols(self) -> int:
        return int(self._cols_spin.value())


class TableTool(Tool):  # type: ignore[misc]
    """Drag a rect → prompt for rows x cols → ``AddFrameCommand`` of kind ``"table"``."""

    name = "Table"
    icon_name = "tool-table"
    cursor = Qt.CursorShape.CrossCursor

    def __init__(self) -> None:
        super().__init__()
        self._start: QPointF | None = None
        self._end: QPointF | None = None

    def activate(self, canvas: Any) -> None:
        super().activate(canvas)
        if hasattr(canvas, "viewport_drag_mode"):
            canvas.viewport_drag_mode(QGraphicsView.DragMode.NoDrag)

    def on_mouse_press(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        self._start = QPointF(scene_pos)
        self._end = QPointF(scene_pos)

    def on_mouse_move(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if self._start is None:
            return
        self._end = QPointF(scene_pos)

    def on_mouse_release(self, event: QMouseEvent, scene_pos: QPointF) -> None:
        if self._start is None:
            return
        rect = QRectF(self._start, scene_pos).normalized()
        self._start = None
        self._end = None
        if rect.width() <= 0 or rect.height() <= 0:
            return
        rows, cols = self._prompt_for_size()
        if rows is None or cols is None:
            return
        self._push_add_table(rect, rows=rows, cols=cols)

    def _prompt_for_size(self) -> tuple[int | None, int | None]:
        """Open the table-size dialog. Overridable in tests."""
        dialog = TableSizeDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None, None
        return dialog.rows(), dialog.cols()

    def _push_add_table(self, rect: QRectF, *, rows: int, cols: int) -> None:
        canvas = self.canvas
        if canvas is None:
            return
        document = getattr(canvas, "document", None)
        page = getattr(canvas, "current_page", None)
        if document is None or page is None:
            return
        command = AddFrameCommand(document, page, rect, "table", rows=rows, cols=cols)
        canvas.push_command(command)


__all__ = ["TableSizeDialog", "TableTool"]
