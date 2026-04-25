"""Story container: a sequence of blocks that flow across linked text frames.

Per spec §4.2 a story holds a tree of blocks; this unit defines the container
plus the `ParagraphSpec` value type that the layout composer (unit-13) consumes.
The block protocol is stubbed here and replaced by unit-5.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from PySide6.QtCore import QObject, Signal

from msword.model.run import Run


@dataclass(slots=True, frozen=True)
class ParagraphSpec:
    """A paragraph as the layout composer sees it: runs + style + source block."""

    runs: tuple[Run, ...]
    paragraph_style_ref: str | None
    block_id: str


@runtime_checkable
class BlockProto(Protocol):  # stub: replaced by unit-5
    kind: str

    def to_dict(self) -> dict[str, Any]: ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BlockProto: ...

    def iter_paragraphs(self) -> Iterable[ParagraphSpec]: ...


class Story(QObject):
    """A flowable text container made of blocks.

    Pure data + Qt change-bus only: no rendering, no I/O. Mutations should go
    through Commands (unit-9); the direct add/remove methods exist so commands
    have something to call.
    """

    changed = Signal()
    block_added = Signal(int)
    block_removed = Signal(int)
    block_changed = Signal(int)

    def __init__(
        self,
        id: str,
        blocks: list[BlockProto] | None = None,
        default_paragraph_style_ref: str | None = None,
        default_character_style_ref: str | None = None,
        language: str = "en-US",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.id = id
        self.blocks: list[BlockProto] = list(blocks) if blocks is not None else []
        self.default_paragraph_style_ref = default_paragraph_style_ref
        self.default_character_style_ref = default_character_style_ref
        self.language = language

    def add_block(self, block: BlockProto, index: int | None = None) -> int:
        if index is None:
            index = len(self.blocks)
        self.blocks.insert(index, block)
        self.block_added.emit(index)
        self.changed.emit()
        return index

    def remove_block(self, index: int) -> BlockProto:
        block = self.blocks.pop(index)
        self.block_removed.emit(index)
        self.changed.emit()
        return block

    def iter_paragraphs(self) -> Iterator[ParagraphSpec]:
        for block in self.blocks:
            yield from block.iter_paragraphs()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "language": self.language,
            "default_paragraph_style_ref": self.default_paragraph_style_ref,
            "default_character_style_ref": self.default_character_style_ref,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        block_factory: Callable[[dict[str, Any]], BlockProto],
        parent: QObject | None = None,
    ) -> Story:
        """Reconstruct a Story. `block_factory` builds a block from its dict.

        The factory is injected because the concrete `BlockRegistry` lives in
        unit-5; the model package can't depend on it.
        """
        return cls(
            id=data["id"],
            blocks=[block_factory(b) for b in data.get("blocks", [])],
            default_paragraph_style_ref=data.get("default_paragraph_style_ref"),
            default_character_style_ref=data.get("default_character_style_ref"),
            language=data.get("language", "en-US"),
            parent=parent,
        )
