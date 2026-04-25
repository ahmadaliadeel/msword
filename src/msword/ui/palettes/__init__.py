"""Right-side dockable palettes (Quark-style, per spec §9).

Public surface for unit #23 (Pages + Outline). Other palettes (Layers,
StyleSheets, Colors, Glyphs) land in their own units and will register here.
"""

from __future__ import annotations

from ._dock import PagesOutlineDock, make_pages_outline_dock
from .outline import OutlinePalette
from .pages import PageThumbnailRenderer, PagesPalette

__all__ = [
    "OutlinePalette",
    "PageThumbnailRenderer",
    "PagesOutlineDock",
    "PagesPalette",
    "make_pages_outline_dock",
]
