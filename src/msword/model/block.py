"""Block base class, registry, and the paragraph-iteration protocol.

Per spec §4.2: blocks are the structural unit inside a story; runs (inline)
live inside paragraph-bearing blocks. Each concrete block type registers
itself in :class:`BlockRegistry` so unknown payloads from disk can be
resolved to the right class without import-time coupling at the call site.

This module deliberately ships a *stub* :class:`Run` and :class:`ParagraphSpec`
shape. They are replaced by unit-4 (`model-story-and-runs`) once that lands.
"""

from __future__ import annotations

import abc
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, ClassVar, NamedTuple

BLOCKS_SCHEMA_VERSION: int = 1


class UnknownBlockKindError(KeyError):
    """Raised when :class:`BlockRegistry` cannot resolve a block ``kind``."""


# Run is the canonical type from unit-4; alias here for callers that historically
# imported it from `msword.model.block`.
from msword.model.run import Run as Run  # noqa: E402


# stub: replaced by unit-4
@dataclass(slots=True)
class StubRun:
    """Concrete minimal :class:`Run` used until unit-4 lands."""

    text: str = ""
    bold: bool = False
    italic: bool = False


# Bridges to the real Run (unit-4 has landed).
from msword.model.run import Run as _RealRun  # noqa: E402


def run_to_dict(run: Run) -> dict[str, Any]:
    """Serialize any :class:`Run`-shaped object via its full inline-mark surface."""
    if isinstance(run, _RealRun):
        return run.to_dict()
    # Fallback for non-Run shapes (test stubs etc.) — minimal surface only.
    return {"text": run.text, "bold": run.bold, "italic": run.italic}


def run_from_dict(d: dict[str, Any]) -> _RealRun:
    """Deserialize into a real :class:`Run` (unit-4)."""
    return _RealRun.from_dict(d)


# stub: replaced by unit-4
class ParagraphSpec(NamedTuple):
    """One paragraph emitted by ``Story.iter_paragraphs`` for the composer.

    Stub shape — unit-4 owns the canonical definition.
    """

    runs: tuple[Run, ...]
    paragraph_style_ref: str | None
    block_id: str


class Block(abc.ABC):
    """Abstract base for every block type stored in a story.

    Concrete subclasses MUST:

    * declare a unique ``kind`` class-var,
    * register themselves with :func:`BlockRegistry.register`,
    * implement :meth:`to_dict` (including ``"kind"`` and ``"id"``),
    * implement :meth:`iter_paragraphs` (yields zero or more
      :class:`ParagraphSpec`, depending on whether the block carries text),
    * implement :meth:`_from_dict_specific` for reconstruction.
    """

    kind: ClassVar[str]
    id: str

    @abc.abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict; MUST include ``kind`` and ``id``."""

    @abc.abstractmethod
    def iter_paragraphs(self) -> Iterable[ParagraphSpec]:
        """Yield the paragraphs this block contributes to the layout pipeline."""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Block:
        """Reconstruct any block from its serialized form via the registry."""
        return BlockRegistry.resolve(d)

    @classmethod
    @abc.abstractmethod
    def _from_dict_specific(cls, d: dict[str, Any]) -> Block:
        """Type-specific reconstruction; called by the registry after lookup."""


class _Registry:
    """Module-level (singleton-ish) mapping of ``kind`` to block class."""

    def __init__(self) -> None:
        self._kinds: dict[str, type[Block]] = {}

    def register(self, cls: type[Block]) -> type[Block]:
        """Decorator: register ``cls`` under its ``kind`` and return it."""
        kind = cls.kind
        existing = self._kinds.get(kind)
        if existing is not None and existing is not cls:
            raise ValueError(
                f"Block kind {kind!r} already registered to {existing.__name__}"
            )
        self._kinds[kind] = cls
        return cls

    def resolve(self, d: dict[str, Any]) -> Block:
        """Look up the class for ``d['kind']`` and reconstruct via it."""
        kind = d.get("kind")
        cls = self._kinds.get(kind) if isinstance(kind, str) else None
        if cls is None:
            raise UnknownBlockKindError(kind)
        return cls._from_dict_specific(d)

    def kinds(self) -> list[str]:
        return sorted(self._kinds)


BlockRegistry = _Registry()
