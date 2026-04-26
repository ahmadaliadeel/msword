"""Slash-command popup for the block editor.

Triggered when the user types ``/`` at the start of (or anywhere inside) a
block. Shows a transient ``QListView`` popup at the caret. Fuzzy filter on the
type label as the user keeps typing. Arrow keys navigate, Enter inserts,
Escape closes, focus loss closes. Emits ``command_chosen(Command)`` with a
``TransformBlockCommand`` for the chosen block kind.

See spec §9 ("block-editor affordances") and §12 unit #29.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QPoint, QSortFilterProxyModel, Qt, Signal
from PySide6.QtGui import QFocusEvent, QKeyEvent, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QListView, QWidget

from msword.commands import Command, TransformBlockCommand


@dataclass(frozen=True)
class SlashItem:
    """One row in the slash menu."""

    label: str
    kind: str
    params: dict[str, Any]

    def to_command(self) -> TransformBlockCommand:
        return TransformBlockCommand(kind=self.kind, params=dict(self.params))


# Order matches spec: H1..H4, Bullet List, Numbered List, Todo List, Quote,
# Code Block, Divider, Image, Callout (Info), Callout (Warn), Callout (Tip),
# Table.
SLASH_ITEMS: tuple[SlashItem, ...] = (
    SlashItem("Heading 1", "heading", {"level": 1}),
    SlashItem("Heading 2", "heading", {"level": 2}),
    SlashItem("Heading 3", "heading", {"level": 3}),
    SlashItem("Heading 4", "heading", {"level": 4}),
    SlashItem("Bullet List", "list", {"kind": "bullet"}),
    SlashItem("Numbered List", "list", {"kind": "ordered"}),
    SlashItem("Todo List", "list", {"kind": "todo"}),
    SlashItem("Quote", "quote", {}),
    SlashItem("Code Block", "code", {}),
    SlashItem("Divider", "divider", {}),
    SlashItem("Image", "image", {}),
    SlashItem("Callout (Info)", "callout", {"kind": "info"}),
    SlashItem("Callout (Warn)", "callout", {"kind": "warn"}),
    SlashItem("Callout (Tip)", "callout", {"kind": "tip"}),
    SlashItem("Table", "table", {}),
)


_ROLE_ITEM = Qt.ItemDataRole.UserRole + 1


def _fuzzy_match(query: str, label: str) -> bool:
    """Subsequence fuzzy match: each char of ``query`` must appear in
    ``label`` in order, case-insensitive. Empty query matches everything."""
    if not query:
        return True
    q = query.lower()
    s = label.lower()
    i = 0
    for ch in s:
        if ch == q[i]:
            i += 1
            if i == len(q):
                return True
    return False


class _FuzzyProxy(QSortFilterProxyModel):
    """Proxy model implementing subsequence fuzzy filter on row label."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._query: str = ""

    def set_query(self, query: str) -> None:
        self._query = query
        # `invalidate()` is the non-deprecated public hook in PySide6 6.11;
        # `invalidateFilter` / `invalidateRowsFilter` are flagged deprecated
        # by the binding (the underlying Qt APIs aren't).
        self.invalidate()

    def filterAcceptsRow(self, source_row: int, source_parent: Any) -> bool:
        model = self.sourceModel()
        if model is None:
            return True
        idx = model.index(source_row, 0, source_parent)
        label = str(model.data(idx, Qt.ItemDataRole.DisplayRole) or "")
        return _fuzzy_match(self._query, label)


class SlashMenu(QListView):
    """Slash-command popup. Emits ``command_chosen(Command)`` when an item
    is activated (Enter / double-click)."""

    command_chosen = Signal(object)  # Command (stubbed in unit-29)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Popup window: floats, dismisses on focus loss, no taskbar entry.
        self.setWindowFlags(Qt.WindowType.Popup)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setUniformItemSizes(True)
        self.setMinimumWidth(220)
        self.setMinimumHeight(40)

        self._source = QStandardItemModel(self)
        for it in SLASH_ITEMS:
            row = QStandardItem(it.label)
            row.setEditable(False)
            row.setData(it, _ROLE_ITEM)
            self._source.appendRow(row)

        self._proxy = _FuzzyProxy(self)
        self._proxy.setSourceModel(self._source)
        self.setModel(self._proxy)

        self._query: str = ""
        self.activated.connect(self._on_activated)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def show_at(self, global_pos: QPoint) -> None:
        """Pop the menu open at ``global_pos`` (the caret position in screen
        coordinates). Selects the first row by default."""
        self._set_query("")
        self.move(global_pos)
        self._size_to_contents()
        self.show()
        self.setFocus(Qt.FocusReason.PopupFocusReason)

    def items(self) -> tuple[SlashItem, ...]:
        """All registered items (unfiltered). Useful for tests."""
        return SLASH_ITEMS

    def visible_items(self) -> list[SlashItem]:
        """Items currently passing the fuzzy filter, in display order."""
        out: list[SlashItem] = []
        for row in range(self._proxy.rowCount()):
            src_idx = self._proxy.mapToSource(self._proxy.index(row, 0))
            data = self._source.data(src_idx, _ROLE_ITEM)
            if isinstance(data, SlashItem):
                out.append(data)
        return out

    def set_query(self, query: str) -> None:
        """Public hook: update the fuzzy filter to ``query``."""
        self._set_query(query)

    @property
    def query(self) -> str:
        return self._query

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _set_query(self, query: str) -> None:
        self._query = query
        self._proxy.set_query(query)
        self._select_first()

    def _select_first(self) -> None:
        if self._proxy.rowCount() > 0:
            self.setCurrentIndex(self._proxy.index(0, 0))

    def _size_to_contents(self) -> None:
        n = max(1, min(8, self._proxy.rowCount()))
        row_h = self.sizeHintForRow(0) if self._proxy.rowCount() else 22
        self.resize(self.width() or self.minimumWidth(), n * row_h + 4)

    # ------------------------------------------------------------------ #
    # Activation
    # ------------------------------------------------------------------ #

    def _on_activated(self, index: Any) -> None:
        if not index.isValid():
            return
        src_idx = self._proxy.mapToSource(index)
        data = self._source.data(src_idx, _ROLE_ITEM)
        if isinstance(data, SlashItem):
            cmd: Command = data.to_command()
            self.command_chosen.emit(cmd)
            self.close()

    def _activate_current(self) -> None:
        idx = self.currentIndex()
        if idx.isValid():
            self._on_activated(idx)

    # ------------------------------------------------------------------ #
    # Keyboard / focus
    # ------------------------------------------------------------------ #

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._activate_current()
            return
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            super().keyPressEvent(event)
            return
        if key == Qt.Key.Key_Backspace:
            if self._query:
                self._set_query(self._query[:-1])
            return
        text = event.text()
        if text and text.isprintable() and text != "/":
            self._set_query(self._query + text)
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        # Qt.Popup already dismisses on focus loss; this is belt-and-braces
        # for environments where the popup is shown without focus stealing.
        self.close()


__all__ = ["SLASH_ITEMS", "SlashItem", "SlashMenu"]
