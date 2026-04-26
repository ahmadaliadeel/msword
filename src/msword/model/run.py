"""Run stub — minimal model for inline runs.

Replaced fully by unit `model-story-and-runs`. This stub exposes only the
attributes the find/replace engine needs: a writable `text` field and an
identity for tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Run:
    """An inline text run carrying styling marks (stub).

    Only `text` and `marks` are needed by `feat.find_engine`. The full mark
    set (bold, italic, font_ref, language_override, …) is filled in by the
    `model-story-and-runs` work unit.
    """

    text: str = ""
    marks: dict[str, Any] = field(default_factory=dict)
