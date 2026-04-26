"""Command package — stubs for unit-29 (slash + bubble menus).

Real Command base + UndoStack live in unit-9 (`commands-and-undo`). This unit
needs only minimal command *stubs* so that menus can emit `command_chosen`
signals carrying a typed payload. These stubs are intentionally tiny dataclasses
with no behaviour; unit-9 will replace this module with the real implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Command:
    """Stub base. Real `Command` (unit-9) will define `do/undo/redo`."""

    name: str = "command"


# --------------------------------------------------------------------------- #
# Block-level commands (slash menu)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TransformBlockCommand(Command):
    """Replace the current block at the caret with one of the given kind.

    `kind` is the BlockRegistry key (e.g. "heading", "paragraph", "list",
    "code", "quote", "callout", "image", "divider", "table"). `params` carries
    type-specific config (heading level, list kind, callout kind, …).
    """

    kind: str = "paragraph"
    params: dict[str, Any] = field(default_factory=dict)
    name: str = "transform-block"


# --------------------------------------------------------------------------- #
# Inline-mark commands (bubble menu)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ToggleMarkCommand(Command):
    """Toggle an inline mark on the current selection."""

    mark: str = "bold"
    name: str = "toggle-mark"


@dataclass(frozen=True)
class SetLinkCommand(Command):
    """Set / clear a link mark on the current selection.

    `url=""` clears the link.
    """

    url: str = ""
    name: str = "set-link"


@dataclass(frozen=True)
class SetRunColorCommand(Command):
    """Set the foreground (`role="color"`) or highlight (`role="highlight"`)
    color on the current selection. `color` is a hex string like ``"#ff0000"``;
    empty string clears the mark.
    """

    color: str = ""
    role: str = "color"
    name: str = "set-run-color"


__all__ = [
    "Command",
    "SetLinkCommand",
    "SetRunColorCommand",
    "ToggleMarkCommand",
    "TransformBlockCommand",
]
