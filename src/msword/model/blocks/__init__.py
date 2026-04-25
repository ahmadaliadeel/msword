"""Block-type implementations.

Importing this package registers every shipped block type with `BlockRegistry`.
"""

from __future__ import annotations

from msword.model.blocks.callout import CalloutBlock
from msword.model.blocks.code import CodeBlock
from msword.model.blocks.list import ListBlock, ListItem
from msword.model.blocks.quote import QuoteBlock

__all__ = [
    "CalloutBlock",
    "CodeBlock",
    "ListBlock",
    "ListItem",
    "QuoteBlock",
]
