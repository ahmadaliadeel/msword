"""Integration tests for unit-25 — `ui-style-sheets-palette`.

Exercise the palette at the public seam: it consumes a `Document` whose
paragraph + character style registries are list-backed (master's shape)
and emits mutations exclusively through Commands.
"""

from __future__ import annotations

from typing import Any

import pytest

from msword.commands import (
    AddParagraphStyleCommand,
    ApplyParagraphStyleCommand,
    EditParagraphStyleCommand,
)
from msword.model.document import Document
from msword.model.style import (
    CharacterStyle,
    ParagraphStyle,
    StyleCycleError,
    StyleResolver,
)
from msword.ui.palettes._style_editor_dialog import StyleEditorDialog
from msword.ui.palettes.style_sheets import StyleSheetsPalette


def _build_document() -> Document:
    doc = Document()
    doc.paragraph_styles.append(
        ParagraphStyle(name="Body", font_family="Sans Serif", font_size_pt=11.0)
    )
    doc.paragraph_styles.append(
        ParagraphStyle(name="Heading 1", based_on="Body", font_size_pt=18.0)
    )
    doc.character_styles.append(CharacterStyle(name="Emphasis", italic=True))
    return doc


def test_palette_lists_existing_paragraph_styles(qtbot) -> None:  # type: ignore[no-untyped-def]
    """Two paragraph styles -> palette shows them in the Paragraph tab."""
    doc = _build_document()
    palette = StyleSheetsPalette(doc)
    qtbot.addWidget(palette)

    para_list = palette._paragraph_list
    assert para_list.count() == 2
    names = {para_list.item(i).text() for i in range(para_list.count())}
    assert names == {"Body", "Heading 1"}

    char_list = palette._character_list
    assert char_list.count() == 1
    assert char_list.item(0).text() == "Emphasis"

    assert not para_list.item(0).icon().isNull()


def test_new_paragraph_style_dispatches_add_command(  # type: ignore[no-untyped-def]
    qtbot, monkeypatch
) -> None:
    """Click + -> AddParagraphStyleCommand fires and the registry grows."""
    doc = _build_document()
    palette = StyleSheetsPalette(doc)
    qtbot.addWidget(palette)

    dispatched: list[type] = []
    real_redo = AddParagraphStyleCommand.redo

    def spy_redo(self: AddParagraphStyleCommand) -> None:
        dispatched.append(type(self))
        real_redo(self)

    monkeypatch.setattr(AddParagraphStyleCommand, "redo", spy_redo)

    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *a, **kw: ("Caption", True)),
    )

    palette._tabs.setCurrentWidget(palette._paragraph_list)
    palette._action_new.trigger()

    assert dispatched == [AddParagraphStyleCommand]
    assert doc.find_paragraph_style("Caption") is not None
    para_list = palette._paragraph_list
    names = {para_list.item(i).text() for i in range(para_list.count())}
    assert "Caption" in names


def test_apply_dispatches_apply_paragraph_style_command(  # type: ignore[no-untyped-def]
    qtbot, monkeypatch
) -> None:
    """Selecting "Body" + Apply -> ApplyParagraphStyleCommand("Body")."""
    doc = _build_document()
    palette = StyleSheetsPalette(doc)
    qtbot.addWidget(palette)

    captured: list[tuple[type, str]] = []
    real_redo = ApplyParagraphStyleCommand.redo

    def spy_redo(self: ApplyParagraphStyleCommand) -> None:
        captured.append((type(self), self.name))
        real_redo(self)

    monkeypatch.setattr(ApplyParagraphStyleCommand, "redo", spy_redo)

    palette._tabs.setCurrentWidget(palette._paragraph_list)
    para_list = palette._paragraph_list
    for i in range(para_list.count()):
        if para_list.item(i).text() == "Body":
            para_list.setCurrentRow(i)
            break
    else:  # pragma: no cover - guard
        pytest.fail("Body row not found")

    palette._action_apply.trigger()

    assert captured == [(ApplyParagraphStyleCommand, "Body")]
    assert doc.selection.paragraph_style == "Body"


def test_double_click_applies_paragraph_style(qtbot, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Double-click on a row -> Apply command (per spec)."""
    doc = _build_document()
    palette = StyleSheetsPalette(doc)
    qtbot.addWidget(palette)

    captured: list[str] = []
    real_redo = ApplyParagraphStyleCommand.redo

    def spy_redo(self: ApplyParagraphStyleCommand) -> None:
        captured.append(self.name)
        real_redo(self)

    monkeypatch.setattr(ApplyParagraphStyleCommand, "redo", spy_redo)

    para_list = palette._paragraph_list
    item = None
    for i in range(para_list.count()):
        if para_list.item(i).text() == "Heading 1":
            item = para_list.item(i)
            break
    assert item is not None
    para_list.itemDoubleClicked.emit(item)

    assert captured == ["Heading 1"]
    assert doc.selection.paragraph_style == "Heading 1"


def test_edit_dialog_size_change_dispatches_edit_command(  # type: ignore[no-untyped-def]
    qtbot, monkeypatch
) -> None:
    """Open the editor, change the size, accept -> EditParagraphStyleCommand."""
    doc = _build_document()

    captured: list[ParagraphStyle] = []
    real_redo = EditParagraphStyleCommand.redo

    def spy_redo(self: EditParagraphStyleCommand) -> None:
        captured.append(self.new_style)
        real_redo(self)

    monkeypatch.setattr(EditParagraphStyleCommand, "redo", spy_redo)

    body = doc.find_paragraph_style("Body")
    assert body is not None
    dialog = StyleEditorDialog(doc, kind="paragraph", style=body)
    qtbot.addWidget(dialog)

    dialog._font_size.setValue(14.0)
    dialog._on_accept()

    assert len(captured) == 1
    edited = captured[0]
    assert edited.name == "Body"
    assert edited.font_size_pt == 14.0
    body_after = doc.find_paragraph_style("Body")
    assert body_after is not None
    assert body_after.font_size_pt == 14.0


def test_cycle_detection_in_based_on_raises(qtbot) -> None:  # type: ignore[no-untyped-def]
    """A based-on chain that loops back must raise StyleCycleError."""
    doc = _build_document()
    new_body = ParagraphStyle(
        name="Body",
        based_on="Heading 1",
        font_family="Sans Serif",
        font_size_pt=11.0,
    )
    cmd = EditParagraphStyleCommand(
        document=doc,
        name="Body",
        new_style=new_body,
    )
    with pytest.raises(StyleCycleError):
        cmd.redo()


def test_cycle_detection_helper_directly() -> None:
    """`StyleResolver.detect_cycle` recognises self-loops + transitive loops."""
    doc = _build_document()
    assert StyleResolver.detect_cycle(doc.paragraph_styles, "Body", "Body") is True
    assert (
        StyleResolver.detect_cycle(doc.paragraph_styles, "Body", "Heading 1") is True
    )
    assert (
        StyleResolver.detect_cycle(doc.paragraph_styles, "Heading 1", "Body") is False
    )
    assert StyleResolver.detect_cycle(doc.paragraph_styles, "Body", "Nope") is False


def test_cycle_detection_in_dialog_blocks_accept(  # type: ignore[no-untyped-def]
    qtbot, monkeypatch
) -> None:
    """If a user lands on a cycling parent, accept must error out
    instead of corrupting the registry."""
    doc = _build_document()
    body = doc.find_paragraph_style("Body")
    assert body is not None
    dialog = StyleEditorDialog(doc, kind="paragraph", style=body)
    qtbot.addWidget(dialog)

    dialog._based_on.addItem("Heading 1", userData="Heading 1")
    idx = dialog._based_on.findData("Heading 1")
    dialog._based_on.setCurrentIndex(idx)

    shown: list[Any] = []
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox,
        "critical",
        staticmethod(lambda *a, **kw: shown.append(a) or QMessageBox.StandardButton.Ok),
    )

    dialog._on_accept()

    body_after = doc.find_paragraph_style("Body")
    assert body_after is not None
    assert body_after.based_on is None
    assert shown, "expected an error popup for the cycle"
