"""msword main window — Quark-style application shell (unit #19).

Per spec §9 / §10, the main window owns:

* The active :class:`Document`,
* The application :class:`UndoStack` (stub — real one lands with unit #9),
* The Quark-style :class:`~msword.ui.menus.MenuBar`,
* A status bar showing ``Page X of Y``, zoom, view-mode, and selection info,
* A central placeholder widget (real canvas lands with unit #16).

The window title format is ``msword — {title}`` where ``{title}`` is the
current document's display title. The placeholder central widget is a stable
seam: unit #16 (`render-canvas`) replaces it with the page canvas.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar, QWidget

from msword.ui.menus import Document, MenuBar, UndoStack


class MainWindow(QMainWindow):
    """Top-level application window.

    The default constructor creates an empty ``Document`` titled "Untitled"
    and a fresh ``UndoStack``. Tests and unit #2 may pass their own
    ``Document`` / ``UndoStack`` instances.
    """

    def __init__(
        self,
        document: Document | None = None,
        undo_stack: UndoStack | None = None,
    ) -> None:
        super().__init__()
        self._document: Document = document if document is not None else Document()
        self.undo_stack: UndoStack = undo_stack if undo_stack is not None else UndoStack()

        self.resize(1400, 900)

        # Central placeholder — replaced by the canvas in unit #16.
        self._placeholder = self._build_placeholder()
        self.setCentralWidget(self._placeholder)

        # Menu bar — full Quark structure.
        self.menu_bar = MenuBar(
            self.undo_stack,
            new_document_callback=self.on_new_document,
            parent=self,
        )
        self.setMenuBar(self.menu_bar)

        # Status bar — page X of Y, zoom, view mode, selection info.
        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)

        self._page_label = QLabel("Page 1 of 1", self._status_bar)
        self._zoom_label = QLabel("100%", self._status_bar)
        self._view_mode_label = QLabel("Paged", self._status_bar)
        self._selection_label = QLabel("No selection", self._status_bar)
        self._status_bar.addWidget(self._page_label)
        self._status_bar.addPermanentWidget(self._zoom_label)
        self._status_bar.addPermanentWidget(self._view_mode_label)
        self._status_bar.addPermanentWidget(self._selection_label)

        self._refresh_window_title()

    # ------------------------------------------------------------------
    # Document lifecycle
    # ------------------------------------------------------------------

    @property
    def document(self) -> Document:
        return self._document

    def set_document(self, doc: Document) -> None:
        """Swap the active document. Updates the window title."""
        self._document = doc
        self._refresh_window_title()
        # When unit #2's real Document arrives, this is also where we'd
        # rewire view/canvas subscriptions to the new document.

    def on_new_document(self) -> None:
        """Slot for the File → New menu action."""
        self.set_document(Document(title="Untitled"))

    def _refresh_window_title(self) -> None:
        self.setWindowTitle(f"msword — {self._document.display_title()}")

    # ------------------------------------------------------------------
    # Status bar helpers
    # ------------------------------------------------------------------

    def set_page_indicator(self, current: int, total: int) -> None:
        self._page_label.setText(f"Page {current} of {total}")

    def set_zoom_indicator(self, percent: int) -> None:
        self._zoom_label.setText(f"{percent}%")

    def set_view_mode_indicator(self, mode: str) -> None:
        self._view_mode_label.setText(mode)

    def set_selection_indicator(self, text: str) -> None:
        self._selection_label.setText(text)

    @property
    def page_label(self) -> QLabel:
        return self._page_label

    @property
    def zoom_label(self) -> QLabel:
        return self._zoom_label

    @property
    def view_mode_label(self) -> QLabel:
        return self._view_mode_label

    @property
    def selection_label(self) -> QLabel:
        return self._selection_label

    # ------------------------------------------------------------------
    # Central widget
    # ------------------------------------------------------------------

    def _build_placeholder(self) -> QWidget:
        placeholder = QLabel(
            "msword bootstrap.\n\n"
            "Tools palette, measurements palette, page canvas, and dockable\n"
            "palettes will be wired in by their respective work units.",
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return placeholder
