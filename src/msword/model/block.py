"""Block stub — minimal block-tree node for find/replace.

Real implementation lands in `model-blocks-schema` (unit 5). This stub
implements just enough for the find/replace engine to walk the tree, read
run text, and locate positions back to (block, run, char_offset).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from msword.model.run import Run


def _new_id() -> str:
    return uuid4().hex


@dataclass
class Block:
    """Generic block holding either runs (leaf) or child blocks (container).

    The full registry/serialization machinery is the responsibility of the
    `model-blocks-schema` unit. We expose only `id`, `kind`, `runs`, and
    `children` so the find engine can recurse correctly.
    """

    kind: str = "paragraph"
    runs: list[Run] = field(default_factory=list)
    children: list[Block] = field(default_factory=list)
    attrs: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=_new_id)

    def iter_leaf_blocks(self) -> Iterator[Block]:
        """Yield every block whose `runs` participate in find/replace.

        Container blocks (e.g. quote, callout) yield their children
        recursively; leaf blocks yield themselves.
        """
        if self.children:
            for child in self.children:
                yield from child.iter_leaf_blocks()
        else:
            yield self
