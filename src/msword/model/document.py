"""Stub `Document`.

Real implementation lives in unit-2 (`model-document-core`). The palette only
needs:

* `selection_changed` and `caret_changed` Qt signals.
* A `selection` property returning a `Selection`.
* A `paragraph_styles` mapping (for the paragraph-style combo).
* A `zoom` property and a `view_mode` property (for the empty-selection mode).
* An `undo_stack` reference so commands can be pushed.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from msword.commands import UndoStack
from msword.model.selection import Selection
from msword.model.style import ParagraphStyle


class Document(QObject):
    """Authoritative-state stub used by unit-22 tests and downstream UI wiring."""

    selection_changed = Signal()
    caret_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._selection = Selection()
        self.paragraph_styles: dict[str, ParagraphStyle] = {
            "Body": ParagraphStyle(name="Body"),
            "Heading 1": ParagraphStyle(name="Heading 1", based_on="Body"),
            "Heading 2": ParagraphStyle(name="Heading 2", based_on="Body"),
        }
        self.zoom: float = 1.0
        self.view_mode: str = "paged"  # paged | flow
        self.undo_stack: UndoStack = UndoStack()

    @property
    def selection(self) -> Selection:
        return self._selection

    def set_selection(self, selection: Selection) -> None:
        """Replace the selection and emit the appropriate signals.

        Test helper: production code will route through commands or controllers.
        """
        prev = self._selection
        self._selection = selection
        self.selection_changed.emit()
        caret_changed = (
            prev.caret_run is not selection.caret_run
            or prev.caret_frame is not selection.caret_frame
        )
        if caret_changed:
            self.caret_changed.emit()
