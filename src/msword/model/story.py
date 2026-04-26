"""Story stub — flat list of blocks for find/replace.

Real implementation in `model-story-and-runs` (unit 4) adds linked-frame
chains, story metadata, and serialization. This stub exposes the block
list and a stable id.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from uuid import uuid4

from msword.model.block import Block


def _new_id() -> str:
    return uuid4().hex


@dataclass
class Story:
    blocks: list[Block] = field(default_factory=list)
    id: str = field(default_factory=_new_id)

    def iter_leaf_blocks(self) -> Iterator[Block]:
        for block in self.blocks:
            yield from block.iter_leaf_blocks()
