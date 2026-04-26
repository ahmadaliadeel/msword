"""Integration tests for unit #19 — Quark-style main window + menu bar.

Asserts the spec §9 menu structure, action labels, shortcuts, command-stack
wiring, status bar contents, and the File → New + Edit → Undo flows.
"""

from __future__ import annotations

import pytest

# Spec §9 — top-level menu titles and exact ordering.
EXPECTED_TOP_LEVEL_MENUS: list[str] = [
    "File",
    "Edit",
    "Style",
    "Item",
    "Page",
    "Layout",
    "View",
    "Utilities",
    "Window",
    "Help",
]


# Spec §9 — action labels under each menu (order asserted).
EXPECTED_ACTIONS: dict[str, list[str]] = {
    "File": [
        "New",
        "Open…",
        "Open Recent",
        "Save",
        "Save As…",
        "Close",
        "Export PDF…",
        "Export PDF/X…",
        "Import DOCX…",
        "Export DOCX…",
        "Quit",
    ],
    "Edit": [
        "Undo",
        "Redo",
        "Cut",
        "Copy",
        "Paste",
        "Paste in Place",
        "Select All",
        "Deselect",
        "Find…",
        "Replace…",
        "Preferences…",
    ],
    "Style": [
        "Paragraph Styles",
        "Character Styles",
        "Object Styles",
        "Edit Style Sheets…",
        "Apply Style…",
    ],
    "Item": [
        "Frame Type",
        "Lock/Unlock",
        "Send to Front",
        "Bring Forward",
        "Send Backward",
        "Send to Back",
        "Group",
        "Ungroup",
        "Linker tools",
        "Step and Repeat…",
    ],
    "Page": [
        "Insert…",
        "Duplicate",
        "Delete",
        "Move…",
        "Page Properties…",
        "Master Page Apply…",
        "Manage Master Pages…",
    ],
    "Layout": [
        "Layout Setup…",
        "Page Setup…",
        "Margins & Columns…",
        "Baseline Grid…",
        "Bleed and Slug…",
    ],
    "View": [
        "Paged",
        "Flow",
        "Zoom",
        "Show Guides",
        "Show Baseline Grid",
        "Show Invisibles",
        "Show Linker",
    ],
    "Utilities": [
        "Spell-check…",
        "Hyphenation…",
        "Glyphs Palette",
        "Suitcase…",
        "Color Profiles…",
    ],
    "Window": [
        "Document tabs",
        "Palette toggles",
    ],
    "Help": [
        "About msword",
        "Documentation",
    ],
}


# Spec §9 — required shortcuts.
EXPECTED_SHORTCUTS: dict[str, str] = {
    "Save": "Ctrl+S",
    "Save As…": "Ctrl+Shift+S",
    "Export PDF…": "Ctrl+Shift+P",
    "Quit": "Ctrl+Q",
    "Undo": "Ctrl+Z",
    "Redo": "Ctrl+Shift+Z",
    "Find…": "Ctrl+F",
    "Replace…": "Ctrl+H",
}


@pytest.fixture
def main_window(qtbot):  # type: ignore[no-untyped-def]
    from msword.ui.main_window import MainWindow

    window = MainWindow()
    qtbot.addWidget(window)
    return window


def test_window_title_uses_msword_dash_title_format(main_window) -> None:  # type: ignore[no-untyped-def]
    assert main_window.windowTitle() == "msword — Untitled"


def test_top_level_menus_match_spec(main_window) -> None:  # type: ignore[no-untyped-def]
    bar = main_window.menu_bar
    titles = [a.text() for a in bar.actions()]
    assert titles == EXPECTED_TOP_LEVEL_MENUS


def test_menu_action_labels_match_spec(main_window) -> None:  # type: ignore[no-untyped-def]
    bar = main_window.menu_bar
    for menu_title, expected_labels in EXPECTED_ACTIONS.items():
        menu = bar.menus_by_title[menu_title]
        actual = [a.text() for a in menu.actions() if not a.isSeparator()]
        assert actual == expected_labels, (
            f"{menu_title}: expected {expected_labels}, got {actual}"
        )


@pytest.mark.parametrize(("label", "shortcut"), list(EXPECTED_SHORTCUTS.items()))
def test_action_shortcuts(main_window, label, shortcut) -> None:  # type: ignore[no-untyped-def]
    action = main_window.menu_bar.actions_by_label[label]
    assert action.shortcut().toString() == shortcut


def test_every_leaf_action_has_tooltip(main_window) -> None:  # type: ignore[no-untyped-def]
    bar = main_window.menu_bar
    for label, action in bar.actions_by_label.items():
        assert action.toolTip(), f"{label} is missing a tooltip"


def test_view_mode_actions_are_radio(main_window) -> None:  # type: ignore[no-untyped-def]
    paged = main_window.menu_bar.actions_by_label["Paged"]
    flow = main_window.menu_bar.actions_by_label["Flow"]
    assert paged.isCheckable()
    assert flow.isCheckable()
    assert paged.isChecked()
    assert not flow.isChecked()
    assert paged.actionGroup() is flow.actionGroup()
    assert paged.actionGroup().isExclusive()


def test_status_bar_initial_contents(main_window) -> None:  # type: ignore[no-untyped-def]
    assert main_window.page_label.text() == "Page 1 of 1"
    assert main_window.zoom_label.text() == "100%"
    assert main_window.view_mode_label.text() == "Paged"
    assert main_window.selection_label.text() == "No selection"


def test_status_bar_setters(main_window) -> None:  # type: ignore[no-untyped-def]
    main_window.set_page_indicator(3, 12)
    main_window.set_zoom_indicator(150)
    main_window.set_view_mode_indicator("Flow")
    main_window.set_selection_indicator("1 frame")
    assert main_window.page_label.text() == "Page 3 of 12"
    assert main_window.zoom_label.text() == "150%"
    assert main_window.view_mode_label.text() == "Flow"
    assert main_window.selection_label.text() == "1 frame"


def test_set_document_updates_title(main_window) -> None:  # type: ignore[no-untyped-def]
    from msword.ui.menus import Document

    main_window.set_document(Document(title="report.msdoc"))
    assert main_window.windowTitle() == "msword — report.msdoc"


def test_file_new_creates_document_and_updates_title(main_window) -> None:  # type: ignore[no-untyped-def]
    from msword.ui.menus import Document

    main_window.set_document(Document(title="report.msdoc"))
    assert main_window.windowTitle() == "msword — report.msdoc"

    new_action = main_window.menu_bar.actions_by_label["New"]
    new_action.trigger()

    assert main_window.document.display_title() == "Untitled"
    assert main_window.windowTitle() == "msword — Untitled"


def test_save_action_pushes_command_onto_undo_stack(main_window) -> None:  # type: ignore[no-untyped-def]
    save_action = main_window.menu_bar.actions_by_label["Save"]
    before = main_window.undo_stack.count()
    save_action.trigger()
    assert main_window.undo_stack.count() == before + 1


def test_edit_undo_calls_undo_stack_undo(main_window) -> None:  # type: ignore[no-untyped-def]
    # Spy by replacing the bound method (avoids a pytest-mock dependency).
    calls: list[str] = []

    original_undo = main_window.undo_stack.undo

    def fake_undo() -> None:
        calls.append("undo")
        original_undo()

    main_window.undo_stack.undo = fake_undo  # type: ignore[method-assign]

    # Push something so undo has work to do.
    main_window.menu_bar.actions_by_label["Save"].trigger()
    main_window.menu_bar.actions_by_label["Undo"].trigger()

    assert calls == ["undo"]


def test_edit_redo_calls_undo_stack_redo(main_window) -> None:  # type: ignore[no-untyped-def]
    calls: list[str] = []
    original_redo = main_window.undo_stack.redo

    def fake_redo() -> None:
        calls.append("redo")
        original_redo()

    main_window.undo_stack.redo = fake_redo  # type: ignore[method-assign]

    main_window.menu_bar.actions_by_label["Save"].trigger()
    main_window.menu_bar.actions_by_label["Undo"].trigger()
    main_window.menu_bar.actions_by_label["Redo"].trigger()

    assert calls == ["redo"]


def test_undo_stack_round_trip(main_window) -> None:  # type: ignore[no-untyped-def]
    stack = main_window.undo_stack
    assert not stack.can_undo()
    main_window.menu_bar.actions_by_label["Save"].trigger()
    main_window.menu_bar.actions_by_label["Copy"].trigger()
    assert stack.count() == 2
    assert stack.can_undo()
    stack.undo()
    assert stack.can_redo()
    stack.redo()
    assert not stack.can_redo()


def test_central_widget_is_placeholder(main_window) -> None:  # type: ignore[no-untyped-def]
    central = main_window.centralWidget()
    assert central is not None


def test_status_bar_exists(main_window) -> None:  # type: ignore[no-untyped-def]
    assert main_window.statusBar() is not None
