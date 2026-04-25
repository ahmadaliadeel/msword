"""Block-type implementations.

Importing this package registers every shipped block type with `BlockRegistry`.
"""

from __future__ import annotations

from msword.model.blocks.image import ImageBlock
from msword.model.blocks.table import BlockCell, BlockCol, BlockRow, TableBlock

__all__ = [
    "BlockCell",
    "BlockCol",
    "BlockRow",
    "ImageBlock",
    "TableBlock",
]
