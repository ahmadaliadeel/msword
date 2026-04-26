"""Block-editor UI affordances (per spec §9, §4.2).

This package layers Tiptap-equivalent block-editing UX on top of a text frame:

* :class:`BlockHandlesOverlay` — left-margin ``⋮⋮`` overlay providing
  drag-to-reorder, right-click menu (Duplicate / Delete / Convert To…).
* :class:`MarkdownShortcutsHandler` — pure input-rule engine that turns
  Markdown-style prefixes (``# ``, ``- ``, ``> ``, etc.) into block-type
  transforms at the start of an empty paragraph.

Slash menu and bubble menu live in their sibling modules (unit 29).

The overlay and the input-rule handler emit *commands* — they never mutate
the model directly (per the architecture invariant in spec §3).
"""

from __future__ import annotations

from msword.ui.block_editor.handles import BlockHandleHit, BlockHandlesOverlay
from msword.ui.block_editor.markdown_shortcuts import MarkdownShortcutsHandler

__all__ = [
    "BlockHandleHit",
    "BlockHandlesOverlay",
    "MarkdownShortcutsHandler",
]
