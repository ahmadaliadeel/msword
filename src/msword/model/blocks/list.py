"""ListBlock — bullet, ordered, todo lists with nestable item content."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

from msword.model.block import Block, BlockRegistry, ParagraphSpec

ListKind = Literal["bullet", "ordered", "todo"]


@dataclass
class ListItem:
    """One item in a list. `blocks` may contain any block type — lists nest freely."""

    id: str
    blocks: list[Block] = field(default_factory=list)
    checked: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "blocks": [b.to_dict() for b in self.blocks],
        }
        if self.checked is not None:
            out["checked"] = self.checked
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ListItem:
        return cls(
            id=data["id"],
            blocks=[BlockRegistry.from_dict(b) for b in data.get("blocks", [])],
            checked=data.get("checked"),
        )


@dataclass
class ListBlock(Block):
    kind: ClassVar[str] = "list"

    id: str
    list_kind: ListKind = "bullet"
    items: list[ListItem] = field(default_factory=list)

    def iter_paragraphs(self) -> Iterator[ParagraphSpec]:
        for item in self.items:
            for child in item.blocks:
                yield from child.iter_paragraphs()

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "list_kind": self.list_kind,
            "items": [it.to_dict() for it in self.items],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ListBlock:
        return cls(
            id=data["id"],
            list_kind=data.get("list_kind", "bullet"),
            items=[ListItem.from_dict(it) for it in data.get("items", [])],
        )


BlockRegistry.register(ListBlock)
