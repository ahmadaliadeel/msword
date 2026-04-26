"""Local stub of the Block base + BlockRegistry.

Owned by unit-5 (`model-blocks-schema`). This stub keeps just enough of the
public surface for sibling units to register their block types, walk
paragraphs, and roundtrip JSON. When unit-5 lands, this file is replaced;
the public seams — ``Block.kind``, ``Block.iter_paragraphs``,
``BlockRegistry.register`` / ``.get`` / ``.from_json`` — must remain stable.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from msword.layout.paragraph_spec import ParagraphSpec


class Block:
    """Base class for every block type in a Story tree."""

    #: Discriminator used in JSON and for registry lookup. Subclasses set this.
    kind: ClassVar[str] = ""

    def iter_paragraphs(self) -> Iterator[ParagraphSpec]:
        """Yield the paragraphs this block contributes to the main flow.

        The default implementation yields nothing, which is the right answer
        for blocks that contribute no inline paragraphs (dividers, footnotes
        whose body lives in the per-page area, …).
        """
        return iter(())

    # ---- Serialization seams. Subclasses override. ----

    def to_json(self) -> dict[str, Any]:
        return {"kind": self.kind}

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Block:  # pragma: no cover - stub
        raise NotImplementedError


class BlockRegistry:
    """Discriminator → block-class registry. Process-global by design."""

    _types: ClassVar[dict[str, type[Block]]] = {}

    @classmethod
    def register(cls, block_cls: type[Block]) -> type[Block]:
        """Register a block class. Idempotent: re-registering the *same*
        class for the same ``kind`` is a no-op; a *different* class wins
        (last write wins) — useful for tests that monkey-patch a kind.
        """
        if not block_cls.kind:
            raise ValueError(f"{block_cls.__name__} must set a non-empty 'kind'")
        cls._types[block_cls.kind] = block_cls
        return block_cls

    @classmethod
    def get(cls, kind: str) -> type[Block]:
        return cls._types[kind]

    @classmethod
    def known_kinds(cls) -> frozenset[str]:
        return frozenset(cls._types)

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Block:
        kind = payload["kind"]
        return cls.get(kind).from_json(payload)
