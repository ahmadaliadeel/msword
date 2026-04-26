"""Stub Document — will be replaced by unit-2 (`model-document-core`).

Unit-25 (style sheets palette) only consumes the document via its style
registries (paragraph_styles, character_styles) and a "selection"
abstraction the Apply* commands target. The real Document will be a
superset of this; replacing the stub should be a no-op for unit-25.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from msword.model.style import CharacterStyle, ParagraphStyle


@dataclass
class _Selection:
    """Stand-in for a real document selection.

    Unit-25's apply commands only need a place to record which paragraph /
    character style is currently applied to the selection. The smoke test
    for "apply on selection" just asserts that the apply command ran with
    the right name; we don't need real text-range plumbing here.
    """

    paragraph_style: str | None = None
    character_style: str | None = None


@dataclass
class Document:
    """Minimal document stub for unit-25.

    Holds the paragraph + character style registries the palette
    manipulates, plus a one-paragraph "selection" the Apply* commands
    target. Real implementation lands in unit-2 / unit-8.
    """

    paragraph_styles: dict[str, ParagraphStyle] = field(default_factory=dict)
    character_styles: dict[str, CharacterStyle] = field(default_factory=dict)
    selection: _Selection = field(default_factory=_Selection)
