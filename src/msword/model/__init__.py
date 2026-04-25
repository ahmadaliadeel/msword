"""Stub model package for unit-22 (`ui-measurements-palette`).

Real units (`model-document-core`, `model-frame`, `model-styles`, …) will land
their authoritative implementations later. The classes here only provide the
public surface the measurements palette needs to read state and the signals it
needs to subscribe to.
"""

from __future__ import annotations

from msword.model.document import Document
from msword.model.frame import Frame, ImageFrame, ShapeFrame, TextFrame
from msword.model.run import Run
from msword.model.selection import Selection
from msword.model.style import ParagraphStyle

__all__ = [
    "Document",
    "Frame",
    "ImageFrame",
    "ParagraphStyle",
    "Run",
    "Selection",
    "ShapeFrame",
    "TextFrame",
]
