"""Integration tests for the selection bubble formatting toolbar."""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor

from msword.commands import (
    SetLinkCommand,
    SetRunColorCommand,
    ToggleMarkCommand,
)
from msword.ui.block_editor.bubble_menu import TOGGLE_MARKS, BubbleMenu


def _make_bubble(qtbot: Any) -> BubbleMenu:
    bubble = BubbleMenu()
    qtbot.addWidget(bubble)
    bubble.show_above(QRect(200, 300, 120, 20))
    qtbot.waitExposed(bubble)
    return bubble


def test_show_above_renders_all_toggle_buttons(qtbot: Any) -> None:
    bubble = _make_bubble(qtbot)
    for mark, _label in TOGGLE_MARKS:
        action = bubble.action_for_mark(mark)
        assert action is not None, f"missing action for {mark}"
        assert action.isCheckable()
    assert bubble.link_button() is not None
    assert bubble.color_button() is not None
    assert bubble.highlight_button() is not None


def test_bold_click_emits_mark_toggled_and_command(qtbot: Any) -> None:
    bubble = _make_bubble(qtbot)

    toggled: list[str] = []
    cmds: list[Any] = []
    bubble.mark_toggled.connect(lambda m: toggled.append(m))
    bubble.command_chosen.connect(lambda c: cmds.append(c))

    btn = bubble.button_for_mark("bold")
    assert btn is not None
    btn.click()

    assert toggled == ["bold"]
    assert len(cmds) == 1
    assert isinstance(cmds[0], ToggleMarkCommand)
    assert cmds[0].mark == "bold"


def test_each_mark_button_emits_its_mark(qtbot: Any) -> None:
    bubble = _make_bubble(qtbot)
    seen: list[str] = []
    bubble.mark_toggled.connect(lambda m: seen.append(m))
    for mark, _label in TOGGLE_MARKS:
        btn = bubble.button_for_mark(mark)
        assert btn is not None
        btn.click()
    assert seen == [m for m, _ in TOGGLE_MARKS]


def test_link_click_opens_line_edit_and_enter_emits_command(qtbot: Any) -> None:
    bubble = _make_bubble(qtbot)

    cmds: list[Any] = []
    bubble.command_chosen.connect(lambda c: cmds.append(c))

    link_btn = bubble.link_button()
    assert link_btn is not None
    link_btn.click()

    editor = bubble.link_editor
    assert editor.isVisible()
    qtbot.waitExposed(editor)

    line_edit = editor.line_edit
    line_edit.setFocus(Qt.FocusReason.OtherFocusReason)
    qtbot.keyClicks(line_edit, "https://example.com")
    qtbot.keyClick(line_edit, Qt.Key.Key_Return)

    assert not editor.isVisible()
    assert len(cmds) == 1
    cmd = cmds[0]
    assert isinstance(cmd, SetLinkCommand)
    assert cmd.url == "https://example.com"


def test_link_escape_cancels_without_emitting(qtbot: Any) -> None:
    bubble = _make_bubble(qtbot)

    cmds: list[Any] = []
    bubble.command_chosen.connect(lambda c: cmds.append(c))

    link_btn = bubble.link_button()
    assert link_btn is not None
    link_btn.click()
    editor = bubble.link_editor
    assert editor.isVisible()

    qtbot.keyClick(editor.line_edit, Qt.Key.Key_Escape)
    assert not editor.isVisible()
    # No SetLinkCommand should have been emitted.
    assert not any(isinstance(c, SetLinkCommand) for c in cmds)


def test_color_click_emits_set_run_color_command(
    qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    bubble = _make_bubble(qtbot)

    # Stub QColorDialog.getColor to return red without opening a dialog.
    from PySide6.QtWidgets import QColorDialog

    monkeypatch.setattr(
        QColorDialog,
        "getColor",
        staticmethod(lambda *_a, **_kw: QColor("#ff0000")),
    )

    cmds: list[Any] = []
    bubble.command_chosen.connect(lambda c: cmds.append(c))

    color_btn = bubble.color_button()
    assert color_btn is not None
    color_btn.click()

    assert len(cmds) == 1
    cmd = cmds[0]
    assert isinstance(cmd, SetRunColorCommand)
    assert cmd.color == "#ff0000"
    assert cmd.role == "color"


def test_highlight_click_emits_set_run_color_command_with_highlight_role(
    qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    bubble = _make_bubble(qtbot)

    from PySide6.QtWidgets import QColorDialog

    monkeypatch.setattr(
        QColorDialog,
        "getColor",
        staticmethod(lambda *_a, **_kw: QColor("#ffff00")),
    )

    cmds: list[Any] = []
    bubble.command_chosen.connect(lambda c: cmds.append(c))

    btn = bubble.highlight_button()
    assert btn is not None
    btn.click()

    assert len(cmds) == 1
    cmd = cmds[0]
    assert isinstance(cmd, SetRunColorCommand)
    assert cmd.color == "#ffff00"
    assert cmd.role == "highlight"


def test_color_dialog_cancelled_emits_no_command(
    qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    bubble = _make_bubble(qtbot)

    from PySide6.QtWidgets import QColorDialog

    # Invalid color = user cancelled.
    monkeypatch.setattr(
        QColorDialog, "getColor", staticmethod(lambda *_a, **_kw: QColor())
    )

    cmds: list[Any] = []
    bubble.command_chosen.connect(lambda c: cmds.append(c))

    color_btn = bubble.color_button()
    assert color_btn is not None
    color_btn.click()
    assert cmds == []
