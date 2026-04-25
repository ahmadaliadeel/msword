"""Block base class, BlockRegistry, and ParagraphSpec.

# stub: replaced by unit-5

Unit-5 (`model-blocks-schema`) owns the canonical `Block` ABC, `BlockRegistry`,
schema-version handling, and the paragraph-iter protocol. Unit-7 only needs the
shape of those interfaces so its block types (image, table) can register at
import and round-trip through the registry. Field names and method signatures
here are chosen to match what unit-5 will land, so the unit-5 file simply
replaces this stub without forcing changes in unit-7.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from msword.model.run import Run


@dataclass(frozen=True)
class ParagraphSpec:
    """One paragraph of shaped text — what the §5 layout composer consumes."""

    runs: tuple[Run, ...]
    paragraph_style_ref: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)


class Block(ABC):
    """Abstract base for every block type in a story."""

    kind: ClassVar[str] = ""

    @abstractmethod
    def iter_paragraphs(self) -> Iterator[ParagraphSpec]:
        """Yield the paragraphs this block contributes to the layout pipeline."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict. Must include ``"kind": cls.kind``."""

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> Block:
        """Deserialize from a dict produced by :meth:`to_dict`."""


class BlockRegistry:
    """Central registry of block types, keyed by ``kind``."""

    _types: ClassVar[dict[str, type[Block]]] = {}

    @classmethod
    def register(cls, block_cls: type[Block]) -> type[Block]:
        kind = block_cls.kind
        if not kind:
            raise ValueError(f"{block_cls.__name__} must set a non-empty `kind`")
        existing = cls._types.get(kind)
        if existing is not None and existing is not block_cls:
            raise ValueError(f"Block kind {kind!r} already registered to {existing.__name__}")
        cls._types[kind] = block_cls
        return block_cls

    @classmethod
    def get(cls, kind: str) -> type[Block]:
        try:
            return cls._types[kind]
        except KeyError as e:
            raise KeyError(f"No block registered for kind {kind!r}") from e

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Block:
        return cls.get(data["kind"]).from_dict(data)


@dataclass
class ParagraphBlock(Block):
    """Stub paragraph block used by unit-7 tests for nested-block roundtrips.

    # stub: replaced by unit-5
    """

    kind: ClassVar[str] = "paragraph"

    id: str
    runs: list[Run] = field(default_factory=list)
    paragraph_style_ref: str | None = None

    def iter_paragraphs(self) -> Iterator[ParagraphSpec]:
        yield ParagraphSpec(
            runs=tuple(self.runs),
            paragraph_style_ref=self.paragraph_style_ref,
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind,
            "id": self.id,
            "runs": [r.to_dict() for r in self.runs],
        }
        if self.paragraph_style_ref is not None:
            out["paragraph_style_ref"] = self.paragraph_style_ref
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParagraphBlock:
        from msword.model.run import Run as _Run

        return cls(
            id=data["id"],
            runs=[_Run.from_dict(r) for r in data.get("runs", [])],
            paragraph_style_ref=data.get("paragraph_style_ref"),
        )


BlockRegistry.register(ParagraphBlock)
