"""Stub `Selection`.

Real implementation lives alongside the document/canvas units. The palette
needs to know:

* Whether the caret is in text (text mode).
* Which frames are selected (geometry / columns mode).
* Whether the selection is empty (zoom + view-mode only).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from msword.model.frame import Frame, TextFrame
from msword.model.run import Run


@dataclass
class Selection:
    """A snapshot of the current selection / caret state."""

    frames: list[Frame] = field(default_factory=list)
    caret_run: Run | None = None
    caret_frame: TextFrame | None = None

    @property
    def is_empty(self) -> bool:
        return not self.frames and self.caret_run is None

    @property
    def has_caret(self) -> bool:
        return self.caret_run is not None

    @property
    def is_multi_frame(self) -> bool:
        return len(self.frames) > 1

    @property
    def single_frame(self) -> Frame | None:
        if len(self.frames) == 1:
            return self.frames[0]
        return None

    @property
    def single_text_frame(self) -> TextFrame | None:
        f = self.single_frame
        if isinstance(f, TextFrame):
            return f
        return None
