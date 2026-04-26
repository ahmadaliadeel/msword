"""Tests for Markdown input rules (unit-28, spec §9).

These are pure-logic tests — no Qt event loop needed — but they live
under ``tests/integration`` because the spec lists them alongside the
block-handle tests for unit 28.
"""

from __future__ import annotations

import pytest

from msword.ui.block_editor import MarkdownShortcutsHandler
from msword.ui.block_editor._stubs import BlockStub, TransformBlockCommand


def _empty_paragraph(block_id: str = "p1") -> BlockStub:
    return BlockStub(id=block_id, kind="paragraph")


def _non_empty_paragraph() -> BlockStub:
    from msword.ui.block_editor._stubs import _RunStub

    return BlockStub(id="p1", kind="paragraph", runs=[_RunStub(text="hello")])


def test_hash_space_transforms_to_h1() -> None:
    handler = MarkdownShortcutsHandler()
    cmd = handler.try_transform(_empty_paragraph(), "# ", story_id="s")
    assert isinstance(cmd, TransformBlockCommand)
    assert cmd.target_kind == "heading"
    assert cmd.target_attrs == {"level": 1}
    assert cmd.story_id == "s"
    assert cmd.block_id == "p1"


@pytest.mark.parametrize(
    ("prefix", "expected_level"),
    [
        ("# ", 1),
        ("## ", 2),
        ("### ", 3),
        ("#### ", 4),
        ("##### ", 5),
        ("###### ", 6),
    ],
)
def test_heading_levels_one_through_six(prefix: str, expected_level: int) -> None:
    handler = MarkdownShortcutsHandler()
    cmd = handler.try_transform(_empty_paragraph(), prefix)
    assert cmd is not None
    assert cmd.target_kind == "heading"
    assert cmd.target_attrs == {"level": expected_level}


def test_seven_hashes_is_not_a_heading() -> None:
    handler = MarkdownShortcutsHandler()
    assert handler.try_transform(_empty_paragraph(), "####### ") is None


@pytest.mark.parametrize("prefix", ["- ", "* "])
def test_dash_or_asterisk_makes_bullet_list(prefix: str) -> None:
    handler = MarkdownShortcutsHandler()
    cmd = handler.try_transform(_empty_paragraph(), prefix)
    assert cmd is not None
    assert cmd.target_kind == "list"
    assert cmd.target_attrs == {"kind": "bullet"}


def test_one_dot_space_makes_ordered_list() -> None:
    handler = MarkdownShortcutsHandler()
    cmd = handler.try_transform(_empty_paragraph(), "1. ")
    assert cmd is not None
    assert cmd.target_kind == "list"
    assert cmd.target_attrs == {"kind": "ordered"}


def test_unchecked_todo() -> None:
    handler = MarkdownShortcutsHandler()
    cmd = handler.try_transform(_empty_paragraph(), "[ ] ")
    assert cmd is not None
    assert cmd.target_kind == "list"
    assert cmd.target_attrs == {"kind": "todo", "checked": False}


@pytest.mark.parametrize("prefix", ["[x] ", "[X] "])
def test_checked_todo(prefix: str) -> None:
    handler = MarkdownShortcutsHandler()
    cmd = handler.try_transform(_empty_paragraph(), prefix)
    assert cmd is not None
    assert cmd.target_kind == "list"
    assert cmd.target_attrs == {"kind": "todo", "checked": True}


def test_quote_prefix() -> None:
    handler = MarkdownShortcutsHandler()
    cmd = handler.try_transform(_empty_paragraph(), "> ")
    assert cmd is not None
    assert cmd.target_kind == "quote"


def test_code_fence_prefix() -> None:
    handler = MarkdownShortcutsHandler()
    cmd = handler.try_transform(_empty_paragraph(), "``` ")
    assert cmd is not None
    assert cmd.target_kind == "code"
    assert cmd.target_attrs == {"language": ""}


def test_divider_prefix_requires_newline() -> None:
    handler = MarkdownShortcutsHandler()
    cmd = handler.try_transform(_empty_paragraph(), "---\n")
    assert cmd is not None
    assert cmd.target_kind == "divider"
    # Without the newline, "---" alone shouldn't trigger.
    assert handler.try_transform(_empty_paragraph(), "---") is None


def test_non_empty_paragraph_returns_none() -> None:
    handler = MarkdownShortcutsHandler()
    assert handler.try_transform(_non_empty_paragraph(), "# ") is None


def test_non_paragraph_block_returns_none() -> None:
    handler = MarkdownShortcutsHandler()
    heading = BlockStub(id="h1", kind="heading", attrs={"level": 1})
    assert handler.try_transform(heading, "# ") is None


def test_unmatched_prefix_returns_none() -> None:
    handler = MarkdownShortcutsHandler()
    assert handler.try_transform(_empty_paragraph(), "?? ") is None
    assert handler.try_transform(_empty_paragraph(), "") is None
    assert handler.try_transform(_empty_paragraph(), "## no-trailing-space") is None
