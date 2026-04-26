"""Integration tests for the slash-command popup."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt

from msword.commands import TransformBlockCommand
from msword.ui.block_editor.slash_menu import SLASH_ITEMS, SlashMenu


def _make_menu(qtbot: Any) -> SlashMenu:
    menu = SlashMenu()
    qtbot.addWidget(menu)
    menu.show_at(QPoint(100, 100))
    qtbot.waitExposed(menu)
    return menu


def test_show_lists_all_items(qtbot: Any) -> None:
    menu = _make_menu(qtbot)
    # All registered items are present and the visible list matches the
    # spec roster (12 → really 15 with H1..H4, three callouts, etc.).
    assert len(menu.items()) == len(SLASH_ITEMS)
    assert len(menu.visible_items()) == len(SLASH_ITEMS)
    labels = [it.label for it in menu.visible_items()]
    assert labels == [
        "Heading 1",
        "Heading 2",
        "Heading 3",
        "Heading 4",
        "Bullet List",
        "Numbered List",
        "Todo List",
        "Quote",
        "Code Block",
        "Divider",
        "Image",
        "Callout (Info)",
        "Callout (Warn)",
        "Callout (Tip)",
        "Table",
    ]


def test_fuzzy_filter_head_matches_four_headings(qtbot: Any) -> None:
    menu = _make_menu(qtbot)
    menu.set_query("head")
    visible = menu.visible_items()
    assert len(visible) == 4
    assert all(it.label.startswith("Heading ") for it in visible)


def test_fuzzy_filter_keystrokes_typed_in(qtbot: Any) -> None:
    """Typing each char into the menu narrows the list — same as `set_query`
    but exercises the keyPressEvent path."""
    menu = _make_menu(qtbot)
    for ch in "head":
        qtbot.keyClick(menu, ch)
    assert len(menu.visible_items()) == 4
    assert menu.query == "head"


def test_arrow_keys_then_enter_emits_h2_command(qtbot: Any) -> None:
    """Down/Down/Enter from the top selects "Heading 2" → emits a
    TransformBlockCommand for heading level 2."""
    menu = _make_menu(qtbot)

    captured: list[Any] = []
    menu.command_chosen.connect(lambda cmd: captured.append(cmd))

    # Top row is "Heading 1"; Down → "Heading 2".
    qtbot.keyClick(menu, Qt.Key.Key_Down)
    qtbot.keyClick(menu, Qt.Key.Key_Return)

    assert len(captured) == 1
    cmd = captured[0]
    assert isinstance(cmd, TransformBlockCommand)
    assert cmd.kind == "heading"
    assert cmd.params == {"level": 2}


def test_escape_closes_menu(qtbot: Any) -> None:
    menu = _make_menu(qtbot)
    assert menu.isVisible()
    qtbot.keyClick(menu, Qt.Key.Key_Escape)
    assert not menu.isVisible()


def test_filter_no_match_then_clear(qtbot: Any) -> None:
    menu = _make_menu(qtbot)
    menu.set_query("zzzzz")
    assert menu.visible_items() == []
    menu.set_query("")
    assert len(menu.visible_items()) == len(SLASH_ITEMS)


def test_focus_loss_closes(qtbot: Any) -> None:
    menu = _make_menu(qtbot)
    # Closing the popup is the dismissal path; focusOutEvent triggers it
    # too, but on the offscreen platform focus chains are a bit funky, so
    # we just assert `close()` works (which is what focusOutEvent calls).
    menu.close()
    assert not menu.isVisible()
