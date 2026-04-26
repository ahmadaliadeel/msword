"""Concrete block types. Importing this package registers them with the registry."""

from __future__ import annotations

from msword.model.blocks.callout import CalloutBlock
from msword.model.blocks.code import CodeBlock
from msword.model.blocks.divider import DividerBlock
from msword.model.blocks.embed import EmbedBlock
from msword.model.blocks.heading import HeadingBlock
from msword.model.blocks.image import ImageBlock
from msword.model.blocks.list import ListBlock, ListItem
from msword.model.blocks.paragraph import ParagraphBlock
from msword.model.blocks.quote import QuoteBlock
from msword.model.blocks.table import BlockCell, BlockCol, BlockRow, TableBlock

__all__ = [
    "BlockCell",
    "BlockCol",
    "BlockRow",
    "CalloutBlock",
    "CodeBlock",
    "DividerBlock",
    "EmbedBlock",
    "HeadingBlock",
    "ImageBlock",
    "ListBlock",
    "ListItem",
    "ParagraphBlock",
    "QuoteBlock",
    "TableBlock",
]
