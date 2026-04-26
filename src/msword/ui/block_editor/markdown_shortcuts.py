r"""Markdown input rules (per spec §9, "Block-editor affordances").

A pure, side-effect-free handler. Given a ``BlockStub`` and the prefix the
user just typed at the start of an empty paragraph, returns a
:class:`TransformBlockCommand` that converts the block to the new kind, or
``None`` if the prefix doesn't match a rule (or the block isn't an empty
paragraph).

Rules (per spec §9):

==========  =================================================================
Prefix      Result
==========  =================================================================
``# ``      heading level 1
``## ``     heading level 2 … through ``###### `` for level 6
``- ``      bullet list
``* ``      bullet list
``1. ``     ordered list
``[ ] ``    todo list (unchecked)
``[x] ``    todo list (checked)  — also accepts ``[X] ``
``> ``      quote
``\`\`\` ``    code block (language attr left empty / set from following text)
``---\n``   divider (the only rule that requires a newline rather than a space)
==========  =================================================================

Notes:

* The handler is intentionally unaware of selection / caret position —
  the *caller* (the editor) decides when to invoke it (typically: right
  after the user types a space at column 0 of an empty paragraph, or after
  Enter following ``---``).
* The handler returns a ``TransformBlockCommand`` that the caller pushes
  onto the undo stack. The caller is also responsible for clearing the
  prefix text from the runs after the transform.
"""

from __future__ import annotations

from typing import Any

from msword.ui.block_editor._stubs import (
    BlockStub,
    TransformBlockCommand,
)

# Static rules: exact-match prefix → (target_kind, attrs).
# Heading rules are generated below since they're parametric in level.
_STATIC_RULES: dict[str, tuple[str, dict[str, Any]]] = {
    "- ": ("list", {"kind": "bullet"}),
    "* ": ("list", {"kind": "bullet"}),
    "1. ": ("list", {"kind": "ordered"}),
    "[ ] ": ("list", {"kind": "todo", "checked": False}),
    "[x] ": ("list", {"kind": "todo", "checked": True}),
    "[X] ": ("list", {"kind": "todo", "checked": True}),
    "> ": ("quote", {}),
    "``` ": ("code", {"language": ""}),
    "---\n": ("divider", {}),
}

# Headings: 1..6 hashes followed by a space.
for _level in range(1, 7):
    _STATIC_RULES["#" * _level + " "] = ("heading", {"level": _level})
del _level


class MarkdownShortcutsHandler:
    """Stateless engine for Markdown-style block-type input rules."""

    def try_transform(
        self,
        block: BlockStub,
        just_typed_prefix: str,
        *,
        story_id: str = "",
    ) -> TransformBlockCommand | None:
        """Return a transform command if the prefix triggers a rule.

        Returns ``None`` if:

        * the block is not an empty paragraph (rules only fire at the
          start of an otherwise-blank paragraph), or
        * no rule matches the prefix.
        """
        if not block.is_empty():
            return None
        match = _STATIC_RULES.get(just_typed_prefix)
        if match is None:
            return None
        kind, attrs = match
        return TransformBlockCommand(
            story_id=story_id,
            block_id=block.id,
            target_kind=kind,
            target_attrs=dict(attrs),
        )
