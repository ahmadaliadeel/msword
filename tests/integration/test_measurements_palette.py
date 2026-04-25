"""Integration tests for the context-aware measurements palette (unit-22)."""

from __future__ import annotations

import pytest

from msword.commands import (
    MoveFrameCommand,
    SetBoldCommand,
    SetColumnsCommand,
)
from msword.model.document import Document
from msword.model.frame import Frame, ImageFrame, TextFrame
from msword.model.run import Run
from msword.model.selection import Selection
from msword.ui.measurements_palette import (
    _MODE_COLUMNS,
    _MODE_EMPTY,
    _MODE_GEOMETRY,
    _MODE_TEXT,
    DEBOUNCE_MS,
    MIXED_PLACEHOLDER,
    MeasurementsPalette,
)


@pytest.fixture
def document(qtbot) -> Document:  # type: ignore[no-untyped-def]
    return Document()


@pytest.fixture
def palette(qtbot, document):  # type: ignore[no-untyped-def]
    p = MeasurementsPalette(document)
    qtbot.addWidget(p)
    p.show()
    qtbot.waitExposed(p)
    return p


def _wait_for_debounce(qtbot) -> None:  # type: ignore[no-untyped-def]
    # Enough margin around the 250ms debounce for a CI-loaded event loop.
    qtbot.wait(DEBOUNCE_MS + 80)


def test_empty_selection_shows_only_zoom_and_view_mode(qtbot, document, palette) -> None:  # type: ignore[no-untyped-def]
    """No selection → only zoom + view-mode pickers visible."""
    assert document.selection.is_empty
    assert palette.current_mode() == _MODE_EMPTY
    assert palette.zoom_spin.isVisible()
    assert palette.view_mode_combo.isVisible()
    # Geometry / text / columns widgets are inside the other stack pages and
    # therefore not visible.
    assert not palette.x_spin.isVisible()
    assert not palette.font_combo.isVisible()
    assert not palette.columns_spin.isVisible()


def test_selecting_frame_switches_to_geometry_and_populates(qtbot, document, palette) -> None:  # type: ignore[no-untyped-def]
    """Select a frame → geometry mode visible and populated from the frame."""
    frame = ImageFrame(id="img-1", x=12.0, y=34.0, w=200.0, h=150.0, rotation=10.0, skew=2.0)
    document.set_selection(Selection(frames=[frame]))

    assert palette.current_mode() == _MODE_GEOMETRY
    assert palette.x_spin.isVisible()
    assert palette.x_spin.value() == pytest.approx(12.0)
    assert palette.y_spin.value() == pytest.approx(34.0)
    assert palette.w_spin.value() == pytest.approx(200.0)
    assert palette.h_spin.value() == pytest.approx(150.0)
    assert palette.rotation_spin.value() == pytest.approx(10.0)
    assert palette.skew_spin.value() == pytest.approx(2.0)


def test_editing_x_pushes_move_frame_command_after_debounce(qtbot, document, palette) -> None:  # type: ignore[no-untyped-def]
    """Edit X → 100, wait > debounce, expect MoveFrameCommand(X=100) on stack."""
    frame = Frame(id="frame-A", x=10.0, y=20.0, w=100.0, h=80.0)
    document.set_selection(Selection(frames=[frame]))

    palette.x_spin.setValue(100.0)
    # Before the debounce fires, nothing has been pushed.
    assert document.undo_stack.last is None

    _wait_for_debounce(qtbot)

    last = document.undo_stack.last
    assert isinstance(last, MoveFrameCommand)
    assert last.frame_id == "frame-A"
    assert last.x == pytest.approx(100.0)
    assert last.y == pytest.approx(20.0)


def test_caret_in_text_shows_text_widgets_and_bold_pushes_command(qtbot, document, palette) -> None:  # type: ignore[no-untyped-def]
    """Caret in text → text widgets visible; click Bold → SetBoldCommand pushed."""
    text_frame = TextFrame(id="tf-1", x=0.0, y=0.0, w=300.0, h=400.0)
    run = Run(text="hello", font_family="Helvetica", size=12.0)
    document.set_selection(Selection(frames=[text_frame], caret_run=run, caret_frame=text_frame))

    assert palette.current_mode() == _MODE_TEXT
    assert palette.font_combo.isVisible()
    assert palette.size_spin.isVisible()
    assert palette.bold_btn.isVisible()
    assert palette.paragraph_style_combo.isVisible()

    # Bold is a discrete toggle — it pushes immediately, no debounce.
    palette.bold_btn.click()

    last = document.undo_stack.last
    assert isinstance(last, SetBoldCommand)
    assert last.bold is True


def test_multi_frame_selection_shows_em_dash_placeholder(qtbot, document, palette) -> None:  # type: ignore[no-untyped-def]
    """Multi-frame selection → fields show em-dash placeholder."""
    f1 = Frame(id="A", x=10.0, y=20.0, w=100.0, h=80.0)
    f2 = Frame(id="B", x=300.0, y=400.0, w=200.0, h=150.0)
    document.set_selection(Selection(frames=[f1, f2]))

    assert palette.current_mode() == _MODE_GEOMETRY
    for spin in (
        palette.x_spin,
        palette.y_spin,
        palette.w_spin,
        palette.h_spin,
        palette.rotation_spin,
        palette.skew_spin,
    ):
        assert spin.specialValueText() == MIXED_PLACEHOLDER
        # And the spin is sitting at its `minimum`, which is the value at
        # which the special-value text replaces the numeric display.
        assert spin.value() == pytest.approx(spin.minimum())


def test_text_frame_no_caret_switches_to_columns_mode(qtbot, document, palette) -> None:  # type: ignore[no-untyped-def]
    """A TextFrame selected with no caret → columns mode."""
    tf = TextFrame(id="tf-cols", w=400.0, h=600.0, columns=2, gutter=14.0, baseline_grid=True)
    document.set_selection(Selection(frames=[tf]))

    assert palette.current_mode() == _MODE_COLUMNS
    assert palette.columns_spin.value() == 2
    assert palette.gutter_spin.value() == pytest.approx(14.0)
    assert palette.baseline_grid_check.isChecked() is True

    palette.columns_spin.setValue(3)
    _wait_for_debounce(qtbot)

    last = document.undo_stack.last
    assert isinstance(last, SetColumnsCommand)
    assert last.columns == 3
    assert last.frame_id == "tf-cols"
