"""ImageBlock — an image placed inline within a story.

Per spec §4.2: distinct from :class:`msword.model.frame.ImageFrame` (a page-level
container). An ``ImageBlock`` is a *block* — it lives inside a story's block
tree and flows with surrounding text. ``layout`` chooses how it interacts with
that flow: ``inline`` participates in line-breaking; ``float-left`` /
``float-right`` are exclusion floats; ``full-width`` breaks out to the column
or frame width.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

from msword.model.block import Block, BlockRegistry, ParagraphSpec

ImageLayout = Literal["inline", "float-left", "float-right", "full-width"]


@dataclass
class ImageBlock(Block):
    """An image referenced by asset hash, placed in a story's block flow."""

    kind: ClassVar[str] = "image"

    id: str
    asset_ref: str
    caption: str | None = None
    layout: ImageLayout = "inline"
    alt_text: str = ""

    def iter_paragraphs(self) -> Iterator[ParagraphSpec]:
        """Images contribute no text paragraphs to the layout pipeline."""
        return iter(())

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind,
            "id": self.id,
            "asset_ref": self.asset_ref,
            "layout": self.layout,
            "alt_text": self.alt_text,
        }
        if self.caption is not None:
            out["caption"] = self.caption
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageBlock:
        return cls(
            id=data["id"],
            asset_ref=data["asset_ref"],
            caption=data.get("caption"),
            layout=data.get("layout", "inline"),
            alt_text=data.get("alt_text", ""),
        )


BlockRegistry.register(ImageBlock)
