"""Selection-bubble formatting toolbar.

Floats above the selection rectangle when the user has a non-empty selection
inside a text frame. Each toggle button maps to a ``ToggleMarkCommand``.
Link opens an inline ``QLineEdit``; pressing Enter emits a ``SetLinkCommand``.
Color and Highlight pop a ``QColorDialog``-equivalent swatch and emit a
``SetRunColorCommand``.

See spec §9 ("block-editor affordances") and §12 unit #29.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFocusEvent, QKeyEvent
from PySide6.QtWidgets import (
    QColorDialog,
    QHBoxLayout,
    QLineEdit,
    QToolBar,
    QToolButton,
    QWidget,
)

from msword.commands import (
    Command,
    SetLinkCommand,
    SetRunColorCommand,
    ToggleMarkCommand,
)

# Order: Bold, Italic, Underline, Strike, Code, Link, Highlight, Color.
TOGGLE_MARKS: tuple[tuple[str, str], ...] = (
    ("bold", "B"),
    ("italic", "I"),
    ("underline", "U"),
    ("strike", "S"),
    ("code", "</>"),
)


class _LinkEditor(QWidget):
    """Inline URL editor — appears in place of the toolbar buttons when the
    user clicks the Link tool. ``Enter`` commits, ``Escape`` cancels."""

    committed = Signal(str)  # url
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText("https://…")
        self._edit.setMinimumWidth(220)
        self._edit.returnPressed.connect(self._commit)
        layout.addWidget(self._edit)

    @property
    def line_edit(self) -> QLineEdit:
        return self._edit

    def show_at(self, global_pos: QPoint) -> None:
        self._edit.clear()
        self.move(global_pos)
        self.adjustSize()
        self.show()
        self._edit.setFocus(Qt.FocusReason.PopupFocusReason)

    def _commit(self) -> None:
        url = self._edit.text().strip()
        self.committed.emit(url)
        self.close()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()
            return
        super().keyPressEvent(event)


class BubbleMenu(QToolBar):
    """Selection-bubble mini-toolbar.

    Emits:
      - ``mark_toggled(str)`` — high-level "this mark was clicked" signal.
      - ``command_chosen(Command)`` — a typed Command for the host to apply.
    """

    mark_toggled = Signal(str)
    command_chosen = Signal(object)  # Command

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup)
        self.setMovable(False)
        self.setIconSize(self.iconSize())
        self.setObjectName("BubbleMenu")

        self._actions_by_mark: dict[str, QAction] = {}
        for mark, label in TOGGLE_MARKS:
            self._actions_by_mark[mark] = self._add_toggle_action(mark, label)

        self._link_action: QAction = self._add_button("link", "Link", self._on_link_clicked)
        self._highlight_action: QAction = self._add_button(
            "highlight", "Highlight", self._on_highlight_clicked
        )
        self._color_action: QAction = self._add_button("color", "Color", self._on_color_clicked)

        # Inline link editor — lazily positioned by `_on_link_clicked`.
        self._link_editor: _LinkEditor = _LinkEditor(self)
        self._link_editor.committed.connect(self._on_link_committed)

        self._anchor: QPoint | None = None  # last `show_above` anchor

    # ------------------------------------------------------------------ #
    # Construction helpers
    # ------------------------------------------------------------------ #

    def _add_action(
        self,
        *,
        object_name: str,
        button_name: str,
        label: str,
        tooltip: str,
        on_trigger: Callable[[], None],
        checkable: bool = False,
    ) -> QAction:
        action = QAction(label, self)
        action.setCheckable(checkable)
        action.setObjectName(object_name)
        action.setToolTip(tooltip)
        action.triggered.connect(lambda _checked=False, fn=on_trigger: fn())
        self.addAction(action)
        # Object-name the underlying QToolButton so tests can find it.
        btn = self.widgetForAction(action)
        if isinstance(btn, QToolButton):
            btn.setObjectName(button_name)
            btn.setText(label)
        return action

    def _add_toggle_action(self, mark: str, label: str) -> QAction:
        def fire() -> None:
            self._on_mark_clicked(mark)

        return self._add_action(
            object_name=f"mark-{mark}",
            button_name=f"btn-mark-{mark}",
            label=label,
            tooltip=mark.capitalize(),
            on_trigger=fire,
            checkable=True,
        )

    def _add_button(self, key: str, label: str, slot: Callable[[], None]) -> QAction:
        return self._add_action(
            object_name=f"action-{key}",
            button_name=f"btn-{key}",
            label=label,
            tooltip=label,
            on_trigger=slot,
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def show_above(self, rect: QRect) -> None:
        """Show the bubble centered above ``rect`` (selection bounding box,
        in screen coordinates)."""
        self.adjustSize()
        x = rect.center().x() - self.width() // 2
        y = rect.top() - self.height() - 6
        self._anchor = QPoint(max(0, x), max(0, y))
        self.move(self._anchor)
        self.show()
        self.setFocus(Qt.FocusReason.PopupFocusReason)

    def action_for_mark(self, mark: str) -> QAction | None:
        return self._actions_by_mark.get(mark)

    def button_for_mark(self, mark: str) -> QToolButton | None:
        action = self.action_for_mark(mark)
        if action is None:
            return None
        btn = self.widgetForAction(action)
        return btn if isinstance(btn, QToolButton) else None

    def link_button(self) -> QToolButton | None:
        btn = self.widgetForAction(self._link_action)
        return btn if isinstance(btn, QToolButton) else None

    def color_button(self) -> QToolButton | None:
        btn = self.widgetForAction(self._color_action)
        return btn if isinstance(btn, QToolButton) else None

    def highlight_button(self) -> QToolButton | None:
        btn = self.widgetForAction(self._highlight_action)
        return btn if isinstance(btn, QToolButton) else None

    @property
    def link_editor(self) -> _LinkEditor:
        return self._link_editor

    # ------------------------------------------------------------------ #
    # Slots
    # ------------------------------------------------------------------ #

    def _on_mark_clicked(self, mark: str) -> None:
        self.mark_toggled.emit(mark)
        cmd: Command = ToggleMarkCommand(mark=mark)
        self.command_chosen.emit(cmd)

    def _on_link_clicked(self) -> None:
        # Position the inline editor where the Link button lives so it
        # visually replaces the bubble's right-hand side.
        anchor = self._anchor or self.pos()
        btn = self.link_button()
        if btn is not None:
            anchor = self.mapToGlobal(btn.pos())
        self._link_editor.show_at(anchor)

    def _on_link_committed(self, url: str) -> None:
        cmd: Command = SetLinkCommand(url=url)
        self.command_chosen.emit(cmd)

    def _on_color_clicked(self) -> None:
        self._pick_color(role="color")

    def _on_highlight_clicked(self) -> None:
        self._pick_color(role="highlight")

    def _pick_color(self, role: str) -> None:
        # Use the non-modal getter so tests can stub via monkeypatch.
        color = QColorDialog.getColor(QColor("#000000"), self, f"Pick {role}")
        if color.isValid():
            cmd: Command = SetRunColorCommand(color=color.name(), role=role)
            self.command_chosen.emit(cmd)

    # ------------------------------------------------------------------ #
    # Focus / dismissal
    # ------------------------------------------------------------------ #

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        # Don't dismiss if focus moved to the inline link editor.
        if self._link_editor.isVisible():
            return
        self.close()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)


__all__ = ["TOGGLE_MARKS", "BubbleMenu"]
