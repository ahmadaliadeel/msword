"""Local stub of the Run model.

The full Run model is owned by unit-4 (`model-story-and-runs`). Until that
unit lands, sibling units that need to construct paragraph content stub a
minimal Run here so they can keep their tests local. When unit-4 merges,
this file is replaced wholesale by the canonical implementation; the public
shape — ``text``, ``marks`` — must match.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Run:
    """Inline-styled text fragment inside a paragraph.

    Stub kept intentionally minimal: only the attributes the footnote unit
    needs to round-trip. Marks is a frozenset of string tags so equality
    works for tests.
    """

    text: str
    marks: frozenset[str] = field(default_factory=frozenset)
