"""RTL-aware shell helper.

Extends a :class:`~msword.ui.main_window.MainWindow` *without modifying it*
so that, whenever the bound :class:`Document`'s locale becomes a
right-to-left language (Arabic, Urdu, Hebrew, …), the page-canvas widget
is mirrored — but the menu bar and dockable palettes deliberately stay
left-to-right, matching working print-designers' preference (the document
chooses its own direction; the chrome doesn't follow).

This is the single place in the UI tree that listens for
``Document.meta_changed`` / ``Document.changed`` and pushes the resulting
``Qt.LayoutDirection`` onto the appropriate widgets.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QDockWidget, QMainWindow, QMenuBar, QStatusBar, QWidget

from msword.i18n.locale import is_rtl_locale


class RtlShell(QObject):
    """Bind a :class:`Document` to a :class:`MainWindow`'s layout direction.

    The shell connects to ``document.meta_changed`` if it exists, otherwise
    falls back to ``document.changed`` — both are valid signals on the
    Document model in the spec; we accept whichever a unit has wired up.

    Mirroring is applied immediately on construction so the very first paint
    uses the correct direction.
    """

    def __init__(
        self,
        main_window: QMainWindow,
        document: Any,
        parent: QObject | None = None,
    ) -> None:
        # Default to parenting the shell to the main window so callers don't
        # have to remember to hold a reference; otherwise the QObject would
        # be garbage-collected the moment the constructor returns and the
        # ``meta_changed`` connection would silently die.
        super().__init__(parent if parent is not None else main_window)
        self._window = main_window
        self._document = document

        # Prefer the more specific signal. Both are simple no-arg notifications;
        # we don't care about payloads here — we always re-read the locale.
        # NB: don't use ``a or b`` here — a PySide6 ``SignalInstance`` is
        # falsy in a boolean context, which would skip a perfectly valid
        # ``meta_changed`` signal in favour of a missing ``changed``.
        signal = getattr(document, "meta_changed", None)
        if signal is None:
            signal = getattr(document, "changed", None)
        if signal is not None:
            signal.connect(self._reapply)

        self._reapply()

    # ------------------------------------------------------------------ API

    def apply_now(self) -> None:
        """Force a re-evaluation of the document's locale (test hook)."""
        self._reapply()

    # --------------------------------------------------------------- helpers

    def _document_locale(self) -> str:
        meta = getattr(self._document, "meta", None)
        if meta is None:
            return ""
        return str(getattr(meta, "locale", "") or "")

    @staticmethod
    def _direction_for(locale: str) -> Qt.LayoutDirection:
        if is_rtl_locale(locale):
            return Qt.LayoutDirection.RightToLeft
        return Qt.LayoutDirection.LeftToRight

    def _canvas_widget(self) -> QWidget | None:
        # Canonical seam: the canvas unit (#16) installs its widget as the
        # central widget. Until it lands, MainWindow's placeholder QLabel
        # also sits there and we mirror it too — that's intentional, it
        # exercises the wiring. Palette docks and the menu bar are left
        # untouched (they keep their parent's LtR direction).
        return self._window.centralWidget()

    def _reapply(self) -> None:
        direction = self._direction_for(self._document_locale())

        canvas = self._canvas_widget()
        if canvas is not None:
            canvas.setLayoutDirection(direction)

        # The chrome (menu bar, dock widgets, status bar) is anchored LtR
        # regardless of document language. Pinning it explicitly means an
        # ambient ``QApplication.setLayoutDirection`` from elsewhere can't
        # flip it underneath us. We query via ``findChild`` rather than the
        # ``menuBar()`` / ``statusBar()`` accessors because those methods
        # *create* the bar as a side effect on first call — we only want to
        # pin chrome that already exists.
        for chrome_type in (QMenuBar, QStatusBar, QDockWidget):
            for widget in self._window.findChildren(chrome_type):
                widget.setLayoutDirection(Qt.LayoutDirection.LeftToRight)


__all__ = ["RtlShell"]
