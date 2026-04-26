"""Outline palette — heading-block tree.

Builds a QTreeView of the document's HeadingBlocks, nesting them by level.
Double-click on a heading emits ``heading_selected(block_id)``.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QTreeView, QVBoxLayout, QWidget

from ._stubs import Block, Document, HeadingBlock

DEBOUNCE_MS = 200
_BLOCK_ID_ROLE = Qt.ItemDataRole.UserRole + 1


class OutlinePalette(QWidget):
    """Outline palette: tree of heading blocks."""

    heading_selected = Signal(str)

    def __init__(self, doc: Document, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._doc = doc

        self._model = QStandardItemModel(self)
        self._model.setHorizontalHeaderLabels(["Outline"])

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(DEBOUNCE_MS)
        self._refresh_timer.timeout.connect(self._do_refresh)

        self._build_ui()
        self._wire_signals()
        self._do_refresh()

    # --------------------------------------------------------------- layout
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        self._view = QTreeView(self)
        self._view.setModel(self._model)
        self._view.setHeaderHidden(True)
        self._view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self._view.setExpandsOnDoubleClick(False)
        self._view.doubleClicked.connect(self._on_double_clicked)
        outer.addWidget(self._view, 1)

    # ------------------------------------------------------------ wiring
    def _wire_signals(self) -> None:
        self._doc.story_changed.connect(self._schedule_refresh)
        self._doc.changed.connect(self._schedule_refresh)

    def _schedule_refresh(self) -> None:
        self._refresh_timer.start()

    # ------------------------------------------------------------ refresh
    def _do_refresh(self) -> None:
        self._model.clear()
        self._model.setHorizontalHeaderLabels(["Outline"])
        root = self._model.invisibleRootItem()
        # stack of (level, item) for parent lookup
        stack: list[tuple[int, QStandardItem]] = []
        for block in self._doc.blocks:
            if not isinstance(block, HeadingBlock):
                continue
            item = self._make_item(block)
            while stack and stack[-1][0] >= block.level:
                stack.pop()
            parent = stack[-1][1] if stack else root
            parent.appendRow(item)
            stack.append((block.level, item))
        self._view.expandAll()

    def _make_item(self, block: HeadingBlock) -> QStandardItem:
        item = QStandardItem(block.text or f"H{block.level}")
        item.setEditable(False)
        item.setData(block.id, _BLOCK_ID_ROLE)
        return item

    # ------------------------------------------------------------ slots
    def _on_double_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        item = self._model.itemFromIndex(index)
        if item is None:
            return
        block_id = item.data(_BLOCK_ID_ROLE)
        if isinstance(block_id, str):
            self.heading_selected.emit(block_id)


def collect_headings(blocks: list[Block]) -> list[HeadingBlock]:
    """Helper: filter a block list down to HeadingBlocks (used by tests)."""
    return [b for b in blocks if isinstance(b, HeadingBlock)]
