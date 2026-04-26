"""Paragraph, character, and object styles.

Styles are declarative: every attribute may be `None`, meaning *inherit from
the `based_on` parent*. `StyleResolver` walks the chain and returns the first
non-None value.

Object-style references to `Stroke` / `Fill` / `Padding` are typed as
Protocols here so this unit can land before the frame-styling unit (unit-3)
finalizes their concrete shapes.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeVar, runtime_checkable

# ---------------------------------------------------------------------------
# Protocol stubs for cross-unit references (concretized in unit-3).
# ---------------------------------------------------------------------------


@runtime_checkable
class Stroke(Protocol):
    """Frame stroke. Concrete shape lands in unit-3."""

    @property
    def width_pt(self) -> float: ...


@runtime_checkable
class Fill(Protocol):
    """Frame fill. Concrete shape lands in unit-3."""

    @property
    def color_ref(self) -> str | None: ...


@runtime_checkable
class Padding(Protocol):
    """Frame padding (top/right/bottom/left in points). Concrete in unit-3."""

    @property
    def top_pt(self) -> float: ...

    @property
    def right_pt(self) -> float: ...

    @property
    def bottom_pt(self) -> float: ...

    @property
    def left_pt(self) -> float: ...


# ---------------------------------------------------------------------------
# Literal aliases.
# ---------------------------------------------------------------------------


Alignment = Literal["left", "right", "center", "justify", "start", "end"]
JustifyMethod = Literal["greedy", "knuth-plass"]


# ---------------------------------------------------------------------------
# Style dataclasses.
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ParagraphStyle:
    """Paragraph-level style. Every attribute except `name` is inheritable."""

    name: str
    based_on: str | None = None
    font_family: str | None = None
    font_size_pt: float | None = None
    leading_pt: float | None = None
    alignment: Alignment | None = None
    first_indent_pt: float | None = None
    left_indent_pt: float | None = None
    right_indent_pt: float | None = None
    space_before_pt: float | None = None
    space_after_pt: float | None = None
    hyphenate: bool | None = None
    justify_method: JustifyMethod | None = None
    opentype_features: frozenset[str] | None = None
    align_to_baseline_grid: bool | None = None
    keep_with_next: bool | None = None
    keep_lines_together: bool | None = None


@dataclass(slots=True)
class CharacterStyle:
    """Character-level style. Every attribute except `name` is inheritable."""

    name: str
    based_on: str | None = None
    font_family: str | None = None
    font_size_pt: float | None = None
    color_ref: str | None = None
    tracking: float | None = None
    baseline_shift_pt: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    strike: bool | None = None
    opentype_features: frozenset[str] | None = None
    language_override: str | None = None


@dataclass(slots=True)
class ObjectStyle:
    """Frame defaults. Every attribute except `name` is inheritable."""

    name: str
    based_on: str | None = None
    stroke: Stroke | None = None
    fill: Fill | None = None
    padding: Padding | None = None
    columns: int | None = None
    gutter_pt: float | None = None
    text_inset_pt: float | None = None


# A common upper bound for the resolver — all three styles share `name` +
# `based_on`. We don't constrain to a Protocol because dataclass attribute
# access already gives us a structural check via `getattr`.
Style = ParagraphStyle | CharacterStyle | ObjectStyle


# ---------------------------------------------------------------------------
# Resolver.
# ---------------------------------------------------------------------------


class StyleCycleError(ValueError):
    """Raised when the based-on chain forms a cycle."""


class StyleNotFoundError(KeyError):
    """Raised when the based-on chain references an unknown style name."""


_S = TypeVar("_S", ParagraphStyle, CharacterStyle, ObjectStyle)


class StyleResolver(Generic[_S]):
    """Resolves attribute values along a style's `based_on` chain.

    Constructed with a registry (`name -> Style`) and a starting style name.
    `resolve_attribute("font_size_pt")` returns the first non-None value
    encountered as we walk based_on links. Returns `None` if no ancestor
    sets the attribute.

    Cycles raise `StyleCycleError`. Missing parents raise
    `StyleNotFoundError` — fail-fast is preferred over silently truncating
    inheritance.
    """

    __slots__ = ("_registry", "_start_name")

    _registry: dict[str, _S]
    _start_name: str

    def __init__(self, registry: dict[str, _S], start_name: str) -> None:
        if start_name not in registry:
            raise StyleNotFoundError(start_name)
        self._registry = registry
        self._start_name = start_name

    def resolve_attribute(self, attr_name: str) -> object:
        for style in self._walk():
            value = getattr(style, attr_name, None)
            if value is not None:
                return value
        return None

    def _walk(self) -> Iterator[_S]:
        # `seen` is a list (not a set) so the cycle error message reports the
        # chain in walk order; membership checks are still O(1) amortized via
        # the parallel `seen_names` set.
        seen: list[str] = []
        seen_names: set[str] = set()
        name: str | None = self._start_name
        while name is not None:
            if name in seen_names:
                raise StyleCycleError(
                    f"cycle in based_on chain: {' -> '.join([*seen, name])}"
                )
            seen.append(name)
            seen_names.add(name)
            try:
                style = self._registry[name]
            except KeyError as exc:
                raise StyleNotFoundError(name) from exc
            yield style
            name = style.based_on


__all__ = [
    "Alignment",
    "CharacterStyle",
    "Fill",
    "JustifyMethod",
    "ObjectStyle",
    "Padding",
    "ParagraphStyle",
    "Stroke",
    "Style",
    "StyleCycleError",
    "StyleNotFoundError",
    "StyleResolver",
]
