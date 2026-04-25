"""Pure data model — no Qt widgets, no rendering, no I/O.

`QObject`/`Signal` from `PySide6.QtCore` is allowed strictly for the change
bus on `Document` and `AssetRegistry` (per unit-2 anchor invariants).
"""

from __future__ import annotations

from msword.model.asset import Asset, AssetKind, AssetRegistry
from msword.model.document import Document, DocumentMeta
from msword.model.master_page import MasterPage
from msword.model.page import (
    A4_HEIGHT_PT,
    A4_WIDTH_PT,
    Bleeds,
    FrameLike,
    Margins,
    Page,
)

__all__ = [
    "A4_HEIGHT_PT",
    "A4_WIDTH_PT",
    "Asset",
    "AssetKind",
    "AssetRegistry",
    "Bleeds",
    "Document",
    "DocumentMeta",
    "FrameLike",
    "Margins",
    "MasterPage",
    "Page",
]
