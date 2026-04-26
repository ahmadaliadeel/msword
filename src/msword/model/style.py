"""Stub paragraph + character style model — will be replaced by unit-8.

Per spec §4 and §12 worker policy: the style sheets palette unit (#25)
needs minimal, replaceable stubs of `ParagraphStyle`, `CharacterStyle`,
and `StyleResolver` so it can be implemented and tested before unit-8
("model-styles") lands.

The real model will live in this same module — these dataclasses define
the small public surface unit-25 actually consumes (name, based_on,
basic typographic fields, hierarchical resolve). Replacing them with the
unit-8 implementation should be a drop-in superset.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


class StyleCycleError(ValueError):
    """Raised when a "based-on" relationship would form a cycle."""


@dataclass
class ParagraphStyle:
    """A named paragraph style with a hierarchical 'based on' parent.

    Stub: only carries the fields unit-25 needs for the palette + editor
    dialog (basic, indents & spacing, tabs, hyphenation, OpenType,
    paragraph rules). All fields are optional/empty by default — child
    styles inherit from parents via :class:`StyleResolver`.
    """

    name: str
    based_on: str | None = None
    # Basic
    font_family: str | None = None
    font_size: float | None = None
    leading: float | None = None
    alignment: str | None = None  # left | right | center | justify
    # Indents & spacing
    space_before: float | None = None
    space_after: float | None = None
    first_line_indent: float | None = None
    left_indent: float | None = None
    right_indent: float | None = None
    # Tabs (list of (position_pt, alignment))
    tabs: list[tuple[float, str]] = field(default_factory=list)
    # Hyphenation
    hyphenate: bool | None = None
    hyphenation_zone: float | None = None
    # OpenType features (set of feature tags, e.g. {"liga", "smcp"})
    opentype_features: set[str] = field(default_factory=set)
    # Paragraph rules (above/below) — minimal: thickness, color
    rule_above_thickness: float | None = None
    rule_below_thickness: float | None = None

    def clone(self, *, name: str) -> ParagraphStyle:
        """Return a deep-enough copy with a new name (used by Duplicate)."""
        return replace(
            self,
            name=name,
            tabs=list(self.tabs),
            opentype_features=set(self.opentype_features),
        )


@dataclass
class CharacterStyle:
    """A named character style with a hierarchical 'based on' parent.

    Stub: only fields needed by the palette + editor dialog.
    """

    name: str
    based_on: str | None = None
    font_family: str | None = None
    font_size: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strike: bool | None = None
    tracking: float | None = None
    baseline_shift: float | None = None
    color_ref: str | None = None
    opentype_features: set[str] = field(default_factory=set)

    def clone(self, *, name: str) -> CharacterStyle:
        return replace(
            self,
            name=name,
            opentype_features=set(self.opentype_features),
        )


class StyleResolver:
    """Resolves "based on" chains, with cycle detection.

    Used by both the palette (to validate user-picked parents in the
    editor dialog) and — eventually — the layout pipeline.
    """

    @staticmethod
    def detect_cycle(
        styles: dict[str, ParagraphStyle] | dict[str, CharacterStyle],
        name: str,
        proposed_based_on: str | None,
    ) -> bool:
        """Return True if setting ``styles[name].based_on = proposed_based_on``
        would introduce a cycle.

        - Self-reference is a cycle.
        - Walking the parent chain back to ``name`` is a cycle.
        - Unknown parent names are *not* a cycle (just unresolved).
        """
        if proposed_based_on is None:
            return False
        if proposed_based_on == name:
            return True
        seen: set[str] = {name}
        current: str | None = proposed_based_on
        while current is not None:
            if current in seen:
                return True
            seen.add(current)
            parent = styles.get(current)
            if parent is None:
                return False
            current = parent.based_on
        return False

    @staticmethod
    def chain(
        styles: dict[str, ParagraphStyle] | dict[str, CharacterStyle],
        name: str,
    ) -> list[str]:
        """Return [name, parent, grandparent, ...] until the chain ends or
        a cycle is detected (in which case the cycle node is excluded)."""
        out: list[str] = []
        seen: set[str] = set()
        current: str | None = name
        while current is not None and current not in seen:
            if current not in styles:
                break
            out.append(current)
            seen.add(current)
            current = styles[current].based_on
        return out

    @staticmethod
    def resolve(
        styles: dict[str, Any],
        name: str,
        attr: str,
    ) -> Any:
        """Walk the based-on chain and return the first non-None value of
        ``attr``, or None if every ancestor leaves it unset.
        """
        for ancestor in StyleResolver.chain(styles, name):
            value = getattr(styles[ancestor], attr, None)
            if value is not None:
                return value
        return None
