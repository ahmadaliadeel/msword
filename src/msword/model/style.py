"""Stub `ParagraphStyle`.

Real implementation lives in unit-8 (`model-styles`). Only `name` is needed by
the measurements palette's paragraph-style picker.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParagraphStyle:
    """Named paragraph style stub."""

    name: str = "Body"
    based_on: str | None = None
