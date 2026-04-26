"""Find/Replace dialog — Quark-style modeless palette over the canvas.

Wires `feat.find_engine` to a `QDialog` with the affordances called out in
spec §12 unit 31: case sensitivity, whole-word, regex, scope, navigate
(Find Next / Find Prev), Replace, Replace All, Close. The dialog owns no
document state; it emits signals that controllers act on.

Signals
-------
- `matches_found(list[Match])` — emitted on every Find Next / Find Prev /
  Replace All so observers (status bar, canvas highlighter) can react.
- `command_pushed(MacroCommand)` — emitted when Replace All builds a macro;
  the host pushes it onto the document's undo stack.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from msword.commands import MacroCommand
from msword.feat.find_engine import Match, Scope, find_all, replace_all

if TYPE_CHECKING:
    from msword.model.document import Document


class FindReplaceDialog(QDialog):
    """Modeless Find/Replace dialog bound to a `Document`."""

    matches_found = Signal(list)  # list[Match]
    command_pushed = Signal(object)  # MacroCommand

    def __init__(self, document: Document, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document = document
        self._matches: list[Match] = []
        self._cursor: int = -1

        self.setWindowTitle("Find and Replace")
        self.setModal(False)

        self._find_input = QLineEdit(self)
        self._find_input.setPlaceholderText("Find…")
        self._replace_input = QLineEdit(self)
        self._replace_input.setPlaceholderText("Replace with…")

        self._case_box = QCheckBox("Match case", self)
        self._whole_word_box = QCheckBox("Whole words", self)
        self._regex_box = QCheckBox("Regex", self)

        self._scope_combo = QComboBox(self)
        # Order matches the spec: selection / story / document.
        self._scope_combo.addItem("Selection", "selection")
        self._scope_combo.addItem("Story", "story")
        self._scope_combo.addItem("Document", "document")
        self._scope_combo.setCurrentIndex(2)

        self._find_next_btn = QPushButton("Find Next", self)
        self._find_prev_btn = QPushButton("Find Prev", self)
        self._replace_btn = QPushButton("Replace", self)
        self._replace_all_btn = QPushButton("Replace All", self)
        self._close_btn = QPushButton("Close", self)

        self._status = QLabel("Ready.", self)

        self._build_layout()
        self._wire()

    # ------------------------------------------------------------------ UI
    def _build_layout(self) -> None:
        form = QFormLayout()
        form.addRow("Find:", self._find_input)
        form.addRow("Replace:", self._replace_input)

        opts = QHBoxLayout()
        opts.addWidget(self._case_box)
        opts.addWidget(self._whole_word_box)
        opts.addWidget(self._regex_box)
        opts.addStretch(1)

        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Scope:", self))
        scope_row.addWidget(self._scope_combo)
        scope_row.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addWidget(self._find_prev_btn)
        buttons.addWidget(self._find_next_btn)
        buttons.addWidget(self._replace_btn)
        buttons.addWidget(self._replace_all_btn)
        buttons.addStretch(1)
        buttons.addWidget(self._close_btn)

        outer = QVBoxLayout(self)
        outer.addLayout(form)
        outer.addLayout(opts)
        outer.addLayout(scope_row)
        outer.addLayout(buttons)
        outer.addWidget(self._status)

    def _wire(self) -> None:
        self._find_next_btn.clicked.connect(self._on_find_next)
        self._find_prev_btn.clicked.connect(self._on_find_prev)
        self._replace_btn.clicked.connect(self._on_replace)
        self._replace_all_btn.clicked.connect(self._on_replace_all)
        self._close_btn.clicked.connect(self.close)

        # Drop cached matches whenever any search input changes.
        self._find_input.textChanged.connect(self._invalidate)
        self._case_box.toggled.connect(self._invalidate)
        self._whole_word_box.toggled.connect(self._invalidate)
        self._regex_box.toggled.connect(self._invalidate)
        self._scope_combo.currentIndexChanged.connect(self._invalidate)

    # --------------------------------------------------------------- state
    def _invalidate(self) -> None:
        self._matches = []
        self._cursor = -1
        self._status.setText("Ready.")

    def _refresh_matches(self) -> bool:
        query = self._find_input.text()
        if not query:
            self._matches = []
            self._cursor = -1
            self._status.setText("Enter a search query.")
            self.matches_found.emit([])
            return False
        try:
            self._matches = find_all(
                self._document,
                query,
                case_sensitive=self._case_box.isChecked(),
                whole_word=self._whole_word_box.isChecked(),
                regex=self._regex_box.isChecked(),
                scope=cast(Scope, self._scope_combo.currentData()),
            )
        except (ValueError, re.error) as exc:
            self._matches = []
            self._cursor = -1
            self._status.setText(f"Invalid query: {exc}")
            self.matches_found.emit([])
            return False
        self._status.setText(f"{len(self._matches)} matches")
        self.matches_found.emit(list(self._matches))
        return True

    # -------------------------------------------------------------- slots
    def _on_find_next(self) -> None:
        if not self._matches and not self._refresh_matches():
            return
        if not self._matches:
            return
        self._cursor = (self._cursor + 1) % len(self._matches)
        self._status.setText(
            f"Match {self._cursor + 1} of {len(self._matches)}"
        )

    def _on_find_prev(self) -> None:
        if not self._matches and not self._refresh_matches():
            return
        if not self._matches:
            return
        self._cursor = (self._cursor - 1) % len(self._matches)
        self._status.setText(
            f"Match {self._cursor + 1} of {len(self._matches)}"
        )

    def _on_replace(self) -> None:
        if not self._matches and not self._refresh_matches():
            return
        if not self._matches or self._cursor < 0:
            return
        match = self._matches[self._cursor]
        macro: MacroCommand = replace_all(
            self._document, [match], self._replace_input.text()
        )
        macro.redo()
        self.command_pushed.emit(macro)
        # Re-scan; offsets shifted.
        self._refresh_matches()

    def _on_replace_all(self) -> None:
        if not self._refresh_matches():
            return
        if not self._matches:
            return
        macro: MacroCommand = replace_all(
            self._document, list(self._matches), self._replace_input.text()
        )
        macro.redo()
        self.command_pushed.emit(macro)
        count = len(self._matches)
        self._matches = []
        self._cursor = -1
        self._status.setText(f"Replaced {count} match(es).")


__all__ = ["FindReplaceDialog"]
