"""Integration tests for the Outline palette (unit #23)."""

from __future__ import annotations

from msword.ui.palettes import OutlinePalette
from msword.ui.palettes._stubs import (
    Document,
    HeadingBlock,
    ParagraphBlock,
)


def _doc_with_sample_outline() -> Document:
    """H1 'Intro' → H2 'Sub' → P → H1 'Next'."""
    doc = Document()
    doc.blocks.append(HeadingBlock(id="h1a", level=1, text="Intro"))
    doc.blocks.append(HeadingBlock(id="h2a", level=2, text="Sub"))
    doc.blocks.append(ParagraphBlock(id="p1", text="body"))
    doc.blocks.append(HeadingBlock(id="h1b", level=1, text="Next"))
    return doc


def test_outline_two_root_items_with_nested_child(qtbot) -> None:  # type: ignore[no-untyped-def]
    doc = _doc_with_sample_outline()
    palette = OutlinePalette(doc)
    qtbot.addWidget(palette)

    model = palette._model
    assert model.rowCount() == 2  # two H1 root items

    intro = model.item(0)
    assert intro is not None
    assert intro.text() == "Intro"
    assert intro.rowCount() == 1  # 'Sub' is its only child
    assert intro.child(0).text() == "Sub"

    nxt = model.item(1)
    assert nxt is not None
    assert nxt.text() == "Next"
    assert nxt.rowCount() == 0


def test_outline_double_click_emits_heading_selected(qtbot) -> None:  # type: ignore[no-untyped-def]
    doc = _doc_with_sample_outline()
    palette = OutlinePalette(doc)
    qtbot.addWidget(palette)

    received: list[str] = []
    palette.heading_selected.connect(received.append)

    # locate the 'Sub' child item under 'Intro'
    intro_index = palette._model.index(0, 0)
    sub_index = palette._model.index(0, 0, intro_index)
    palette._view.doubleClicked.emit(sub_index)

    assert received == ["h2a"]


def test_outline_refreshes_after_block_added(qtbot) -> None:  # type: ignore[no-untyped-def]
    doc = Document()
    doc.blocks.append(HeadingBlock(id="h1", level=1, text="One"))
    palette = OutlinePalette(doc)
    qtbot.addWidget(palette)

    assert palette._model.rowCount() == 1

    doc.add_block(HeadingBlock(id="h2", level=1, text="Two"))
    qtbot.wait(250)  # past the 200 ms debounce

    assert palette._model.rowCount() == 2
    assert palette._model.item(1).text() == "Two"


def test_outline_ignores_non_heading_blocks(qtbot) -> None:  # type: ignore[no-untyped-def]
    doc = Document()
    doc.blocks.append(ParagraphBlock(id="p1", text="just a para"))
    doc.blocks.append(HeadingBlock(id="h1", level=1, text="Heading"))
    doc.blocks.append(ParagraphBlock(id="p2"))

    palette = OutlinePalette(doc)
    qtbot.addWidget(palette)

    assert palette._model.rowCount() == 1
    assert palette._model.item(0).text() == "Heading"


def test_outline_h3_under_h2_under_h1(qtbot) -> None:  # type: ignore[no-untyped-def]
    doc = Document()
    doc.blocks.extend(
        [
            HeadingBlock(id="a", level=1, text="A"),
            HeadingBlock(id="b", level=2, text="B"),
            HeadingBlock(id="c", level=3, text="C"),
        ]
    )
    palette = OutlinePalette(doc)
    qtbot.addWidget(palette)

    a = palette._model.item(0)
    assert a is not None and a.rowCount() == 1
    b = a.child(0)
    assert b is not None and b.text() == "B"
    assert b.rowCount() == 1
    c = b.child(0)
    assert c is not None and c.text() == "C"
