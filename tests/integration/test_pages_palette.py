"""Integration tests for the Pages palette (unit #23)."""

from __future__ import annotations

from PySide6.QtCore import QSize

from msword.ui.palettes import PagesPalette, make_pages_outline_dock
from msword.ui.palettes._stubs import (
    CommandBus,
    Document,
    MovePageCommand,
    Page,
)


def _doc_with_pages(n: int) -> Document:
    doc = Document()
    for i in range(n):
        doc.pages.append(Page(id=f"p{i}", master_id="m-A"))
    return doc


def test_three_pages_shows_three_thumbnails(qtbot) -> None:  # type: ignore[no-untyped-def]
    doc = _doc_with_pages(3)
    palette = PagesPalette(doc)
    qtbot.addWidget(palette)

    assert palette.view.model().rowCount() == 3
    # decoration role yields a non-null icon for each row
    for row in range(3):
        idx = palette.view.model().index(row, 0)
        deco = palette.view.model().data(idx, role=1)  # DecorationRole
        assert deco is not None


def test_click_emits_page_selected(qtbot) -> None:  # type: ignore[no-untyped-def]
    doc = _doc_with_pages(3)
    palette = PagesPalette(doc)
    qtbot.addWidget(palette)

    received: list[int] = []
    palette.page_selected.connect(received.append)

    idx = palette.view.model().index(2, 0)
    palette.view.clicked.emit(idx)

    assert received == [2]


def test_drag_reorder_dispatches_move_page_command(qtbot) -> None:  # type: ignore[no-untyped-def]
    doc = _doc_with_pages(3)
    bus = CommandBus()
    palette = PagesPalette(doc, bus=bus)
    qtbot.addWidget(palette)

    seen_moves: list[MovePageCommand] = []

    def _on_dispatch(record) -> None:  # type: ignore[no-untyped-def]
        for arg in record.args:
            if isinstance(arg, MovePageCommand):
                seen_moves.append(arg)

    bus.dispatched.connect(_on_dispatch)

    # Use the public Move Down button as a deterministic stand-in for the
    # drag interaction — both routes funnel through MovePageCommand.
    palette.view.setCurrentIndex(palette.view.model().index(0, 0))
    palette._on_move_down()

    assert len(seen_moves) == 1
    assert seen_moves[0].src == 0
    assert seen_moves[0].dst == 1


def test_drag_via_model_rows_moved_signal(qtbot) -> None:  # type: ignore[no-untyped-def]
    """Simulate Qt's internal-move drag by emitting rowsMoved on the model."""
    doc = _doc_with_pages(4)
    bus = CommandBus()
    palette = PagesPalette(doc, bus=bus)
    qtbot.addWidget(palette)

    seen_moves: list[MovePageCommand] = []
    bus.dispatched.connect(
        lambda r: seen_moves.extend(a for a in r.args if isinstance(a, MovePageCommand))
    )

    model = palette.view.model()
    # Pretend Qt moved row 0 down to position 3 (= insert before "row 3", which
    # after removal becomes index 2).
    from PySide6.QtCore import QModelIndex

    model.rowsMoved.emit(QModelIndex(), 0, 0, QModelIndex(), 3)

    assert seen_moves and seen_moves[0].src == 0
    assert seen_moves[0].dst == 2


def test_add_page_refreshes_thumbnails_after_debounce(qtbot) -> None:  # type: ignore[no-untyped-def]
    doc = _doc_with_pages(3)
    palette = PagesPalette(doc)
    qtbot.addWidget(palette)

    assert palette.view.model().rowCount() == 3

    doc.add_page(Page(id="p3", master_id="m-A"))

    # debounced (200 ms) — wait 250 ms
    qtbot.wait(250)

    assert palette.view.model().rowCount() == 4


def test_thumbnail_renderer_default_paints_white_with_number(qtbot) -> None:  # type: ignore[no-untyped-def]
    from msword.ui.palettes.pages import _DefaultThumbnailRenderer

    renderer = _DefaultThumbnailRenderer()
    pix = renderer.render(Page(id="p0"), 0, QSize(48, 64))

    assert not pix.isNull()
    assert pix.size() == QSize(48, 64)
    img = pix.toImage()
    # corner pixel should be white (border may be dark, so probe the middle).
    mid = img.pixelColor(img.width() // 2, img.height() // 2)
    assert mid.red() == 255 and mid.green() == 255 and mid.blue() == 255


def test_dock_factory_has_two_tabs(qtbot) -> None:  # type: ignore[no-untyped-def]
    doc = _doc_with_pages(2)
    dock = make_pages_outline_dock(doc)
    qtbot.addWidget(dock)

    assert dock.tabs.count() == 2
    assert dock.tabs.tabText(0) == "Pages"
    assert dock.tabs.tabText(1) == "Outline"


def test_master_pages_section_lists_masters(qtbot) -> None:  # type: ignore[no-untyped-def]
    doc = _doc_with_pages(1)
    palette = PagesPalette(doc)
    qtbot.addWidget(palette)

    assert palette._master_list.count() == 1
    assert palette._master_list.item(0).text() == "A-Master"
