"""Shared text-frame hit-testing for the linker / unlinker tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from msword.ui.tools._stubs import TextFrame

if TYPE_CHECKING:
    from PySide6.QtCore import QPointF


def hit_test_text_frame(page: Any, scene_pos: QPointF) -> Any | None:
    """Return the topmost TextFrame under ``scene_pos`` or ``None``.

    Frames are walked top-to-bottom (reverse z-order) and non-text frames are
    skipped so the link/unlink tools never target e.g. a picture frame. Be
    permissive about typing: real ``TextFrame`` (unit 7) may not equal the
    local stub class, so accept either the resolved type *or* a
    ``kind == "text"`` tag.
    """
    if page is None:
        return None
    x, y = scene_pos.x(), scene_pos.y()
    for frame in reversed(getattr(page, "frames", [])):
        is_text = isinstance(frame, TextFrame) or getattr(frame, "kind", None) == "text"
        if not is_text:
            continue
        if frame.x <= x <= frame.x + frame.w and frame.y <= y <= frame.y + frame.h:
            return frame
    return None


__all__ = ["hit_test_text_frame"]
