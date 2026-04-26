"""Colors palette — work unit #26.

Dockable QuarkXPress-style palette listing the document's named colour
swatches as an icon-mode :class:`QListWidget` grid. Each cell is a small
fill-coloured tile; tooltips reveal the swatch's name, profile, and
component values.

Toolbar actions:

* **+** — open :class:`ColorEditor` to add a new swatch (dispatches an
  :class:`AddColorSwatchCommand` on accept).
* **Edit** — open the editor on the selected swatch (dispatches
  :class:`EditColorSwatchCommand`).
* **Delete** — drop the selected swatch
  (:class:`DeleteColorSwatchCommand`).
* **Duplicate** — clone the selected swatch
  (:class:`DuplicateColorSwatchCommand`).

Click semantics with the document's currently selected frame:

* **Click** a swatch → :class:`SetFrameFillCommand` for that frame.
* **Shift-Click** → :class:`SetFrameStrokeCommand`.
* **Drag** a swatch onto a frame → same routing (mime payload carries
  the swatch name; the canvas/frame view is responsible for the drop and
  for choosing fill-vs-stroke based on its own modifier handling — this
  palette only initiates the drag).

All mutations route through Commands; the palette never touches the
model directly.
"""

from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, QSize, Qt
from PySide6.QtGui import (
    QAction,
    QColor,
    QDrag,
    QIcon,
    QMouseEvent,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDockWidget,
    QInputDialog,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from msword.commands import (
    DeleteColorSwatchCommand,
    DuplicateColorSwatchCommand,
    SetFrameFillCommand,
    SetFrameStrokeCommand,
)
from msword.model.color import ColorSwatch
from msword.model.document import Document
from msword.ui.palettes._color_editor import ColorEditor

_SWATCH_MIME = "application/x-msword-swatch-name"
_TILE_SIZE = QSize(40, 40)


def _render_swatch_icon(swatch: ColorSwatch, *, size: QSize = _TILE_SIZE) -> QPixmap:
    """Render a swatch tile (filled rect + border) for display."""
    pix = QPixmap(size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        r, g, b = swatch.to_rgb()
        painter.fillRect(pix.rect(), QColor.fromRgbF(r, g, b))
        # 1-px black border so light swatches are still discernible
        painter.setPen(QColor(0, 0, 0))
        painter.drawRect(0, 0, size.width() - 1, size.height() - 1)
        if swatch.is_spot:
            # mark spot swatches with a small dot in the corner
            painter.fillRect(2, 2, 4, 4, QColor(255, 255, 255))
            painter.setPen(QColor(0, 0, 0))
            painter.drawRect(2, 2, 4, 4)
    finally:
        painter.end()
    return pix


def _swatch_tooltip(swatch: ColorSwatch) -> str:
    comp_text = ", ".join(f"{c:.2f}" for c in swatch.components)
    sep = "spot" if swatch.is_spot else "process"
    return (
        f"{swatch.name}\nProfile: {swatch.profile_name}\n"
        f"Components: ({comp_text})\nSeparation: {sep}"
    )


class _SwatchGrid(QListWidget):
    """A :class:`QListWidget` in icon-mode that emits per-swatch click +
    drag signals to its parent palette.

    We subclass to keep the click-modifier semantics local to the grid
    rather than smearing them across the palette: ``mousePressEvent`` and
    ``mouseMoveEvent`` know how to route a click + how to start a swatch
    drag.
    """

    def __init__(self, palette: ColorsPalette) -> None:
        super().__init__(palette)
        self._palette = palette
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setIconSize(_TILE_SIZE)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setUniformItemSizes(True)
        self.setSpacing(4)
        self.setDragEnabled(True)
        self._drag_start: QPoint | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position().toPoint()
            item = self.itemAt(self._drag_start)
            if item is not None:
                modifiers = event.modifiers()
                shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
                self._palette._on_swatch_clicked(item, shift=shift)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._drag_start is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position().toPoint() - self._drag_start).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            item = self.itemAt(self._drag_start)
            if item is not None:
                self._start_drag(item)
                self._drag_start = None
                return
        super().mouseMoveEvent(event)

    def _start_drag(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(name, str):
            return
        mime = QMimeData()
        mime.setData(_SWATCH_MIME, name.encode("utf-8"))
        mime.setText(name)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(item.icon().pixmap(_TILE_SIZE))
        drag.exec(Qt.DropAction.CopyAction)


class ColorsPalette(QDockWidget):
    """Swatch-grid dock palette."""

    OBJECT_NAME = "ColorsPalette"
    SWATCH_MIME = _SWATCH_MIME

    def __init__(self, document: Document, parent: QWidget | None = None) -> None:
        super().__init__("Colors", parent)
        self.setObjectName(self.OBJECT_NAME)
        self._document = document

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # toolbar — New / Edit / Delete / Duplicate
        self._toolbar = QToolBar("Color swatch actions", container)
        self._toolbar.setIconSize(QSize(16, 16))
        style = self.style()

        def _make_action(label: str, tip: str, icon: QStyle.StandardPixmap) -> QAction:
            act = QAction(style.standardIcon(icon), label, self)
            act.setToolTip(tip)
            self._toolbar.addAction(act)
            return act

        self._action_new = _make_action(
            "+", "New swatch", QStyle.StandardPixmap.SP_FileDialogNewFolder
        )
        self._action_edit = _make_action(
            "Edit", "Edit selected swatch", QStyle.StandardPixmap.SP_FileDialogDetailedView
        )
        self._action_delete = _make_action(
            "Delete", "Delete selected swatch", QStyle.StandardPixmap.SP_TrashIcon
        )
        self._action_duplicate = _make_action(
            "Duplicate", "Duplicate selected swatch", QStyle.StandardPixmap.SP_DialogResetButton
        )
        self._action_new.triggered.connect(self._on_new)
        self._action_edit.triggered.connect(self._on_edit)
        self._action_delete.triggered.connect(self._on_delete)
        self._action_duplicate.triggered.connect(self._on_duplicate)
        layout.addWidget(self._toolbar)

        # grid
        self._grid = _SwatchGrid(self)
        layout.addWidget(self._grid)

        self.setWidget(container)
        self.refresh()

    # ------------------------------------------------------------------
    # population
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._grid.clear()
        for name in sorted(self._document.color_swatches):
            swatch = self._document.color_swatches[name]
            item = QListWidgetItem(QIcon(_render_swatch_icon(swatch)), swatch.name)
            item.setSizeHint(QSize(_TILE_SIZE.width() + 16, _TILE_SIZE.height() + 24))
            item.setData(Qt.ItemDataRole.UserRole, swatch.name)
            item.setToolTip(_swatch_tooltip(swatch))
            self._grid.addItem(item)

    def _selected_name(self) -> str | None:
        items = self._grid.selectedItems()
        if not items:
            return None
        data = items[0].data(Qt.ItemDataRole.UserRole)
        return data if isinstance(data, str) else None

    # ------------------------------------------------------------------
    # toolbar handlers
    # ------------------------------------------------------------------
    def _on_new(self) -> None:
        dialog = ColorEditor(self._document, parent=self)
        if dialog.exec() == ColorEditor.DialogCode.Accepted:
            self.refresh()

    def _on_edit(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        dialog = ColorEditor(self._document, existing_name=name, parent=self)
        if dialog.exec() == ColorEditor.DialogCode.Accepted:
            self.refresh()

    def _on_delete(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        confirm = QMessageBox.question(self, "Delete swatch", f"Delete swatch {name!r}?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        DeleteColorSwatchCommand(self._document, name).redo()
        self.refresh()

    def _on_duplicate(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        new_name, ok = QInputDialog.getText(
            self,
            "Duplicate swatch",
            "New name:",
            text=f"{name} copy",
        )
        if not ok or not new_name:
            return
        if new_name in self._document.color_swatches:
            QMessageBox.warning(self, "Duplicate", f"{new_name!r} already exists.")
            return
        DuplicateColorSwatchCommand(self._document, name, new_name).redo()
        self.refresh()

    # ------------------------------------------------------------------
    # click → fill / stroke
    # ------------------------------------------------------------------
    def _on_swatch_clicked(self, item: QListWidgetItem, *, shift: bool) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(name, str):
            return
        if self._document.selected_frame is None:
            # No frame selected — clicking a swatch is a no-op (the user
            # only selected a row in the palette). Real canvas wiring
            # surfaces frame-selection state; we do not show an error.
            return
        if shift:
            SetFrameStrokeCommand(self._document, name).redo()
        else:
            SetFrameFillCommand(self._document, name).redo()


__all__ = ["ColorsPalette"]
