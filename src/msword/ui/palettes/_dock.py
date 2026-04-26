"""Right-side dock: tabbed Pages + Outline (per spec §9)."""

from __future__ import annotations

from PySide6.QtWidgets import QDockWidget, QTabWidget, QWidget

from ._stubs import CommandBus, Document
from .outline import OutlinePalette
from .pages import PagesPalette, PageThumbnailRenderer


class PagesOutlineDock(QDockWidget):
    """QDockWidget hosting a QTabWidget with Pages + Outline tabs."""

    def __init__(
        self,
        doc: Document,
        bus: CommandBus | None = None,
        renderer: PageThumbnailRenderer | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Pages", parent)
        self.setObjectName("PagesOutlineDock")

        self._tabs = QTabWidget(self)
        self._pages = PagesPalette(doc, bus=bus, renderer=renderer, parent=self._tabs)
        self._outline = OutlinePalette(doc, parent=self._tabs)
        self._tabs.addTab(self._pages, "Pages")
        self._tabs.addTab(self._outline, "Outline")

        self.setWidget(self._tabs)

    @property
    def pages(self) -> PagesPalette:
        return self._pages

    @property
    def outline(self) -> OutlinePalette:
        return self._outline

    @property
    def tabs(self) -> QTabWidget:
        return self._tabs


def make_pages_outline_dock(
    doc: Document,
    bus: CommandBus | None = None,
    renderer: PageThumbnailRenderer | None = None,
    parent: QWidget | None = None,
) -> PagesOutlineDock:
    """Factory: build the right-side Pages+Outline tabbed dock."""
    return PagesOutlineDock(doc, bus=bus, renderer=renderer, parent=parent)
