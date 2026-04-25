"""Concrete block types. Importing this package registers them with the registry."""

from __future__ import annotations

from msword.model.blocks.divider import DividerBlock
from msword.model.blocks.embed import EmbedBlock
from msword.model.blocks.heading import HeadingBlock
from msword.model.blocks.paragraph import ParagraphBlock

__all__ = ["DividerBlock", "EmbedBlock", "HeadingBlock", "ParagraphBlock"]
