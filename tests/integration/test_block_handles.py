"""Integration tests for the block-handle overlay (unit-28, spec §9)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from msword.ui.block_editor import BlockHandlesOverlay
from msword.ui.block_editor._stubs import (
    BlockStub,
    CommandStub,
    DeleteBlockCommand,
    DuplicateBlockCommand,
    MoveBlockCommand,
    StoryStub,
    TextFrameItemStub,
    TransformBlockCommand,
)
from msword.ui.block_editor.handles import CONVERT_TO_OPTIONS


@dataclass
class _Fixture:
    """Bundle of objects the tests need.

    The scene + view are held so that Qt doesn't garbage-collect them
    while the test is running; the tests don't read them directly.
    """

    scene: QGraphicsScene
    view: QGraphicsView
    frame: TextFrameItemStub
    overlay: BlockHandlesOverlay
    sink: list[CommandStub]


def _make_three_block_frame() -> _Fixture:
    scene = QGraphicsScene()
    view = QGraphicsView(scene)
    story = StoryStub(
        id="story-1",
        blocks=[
            BlockStub(id="b1", kind="paragraph"),
            BlockStub(id="b2", kind="heading", attrs={"level": 1}),
            BlockStub(id="b3", kind="paragraph"),
        ],
    )
    frame = TextFrameItemStub(story=story, size=(400.0, 300.0))
    scene.addItem(frame)

    # Three stacked, equal-height regions occupying the frame body.
    frame.set_block_regions(
        [
            ("b1", QRectF(0.0, 0.0, 400.0, 100.0)),
            ("b2", QRectF(0.0, 100.0, 400.0, 100.0)),
            ("b3", QRectF(0.0, 200.0, 400.0, 100.0)),
        ]
    )

    sink: list[CommandStub] = []
    overlay = BlockHandlesOverlay(parent=frame, command_sink=sink.append)
    return _Fixture(scene=scene, view=view, frame=frame, overlay=overlay, sink=sink)


def test_handle_hidden_until_block_is_hovered(qtbot) -> None:  # type: ignore[no-untyped-def]
    fix = _make_three_block_frame()
    qtbot.addWidget(fix.view)

    assert fix.overlay.hovered_block is None
    assert fix.overlay.is_handle_visible() is False


def test_hover_shows_handle_for_correct_block(qtbot) -> None:  # type: ignore[no-untyped-def]
    fix = _make_three_block_frame()
    qtbot.addWidget(fix.view)

    fix.overlay.simulate_hover(QPointF(50.0, 150.0))  # inside block 2

    assert fix.overlay.is_handle_visible() is True
    hit = fix.overlay.hovered_block
    assert hit is not None
    assert hit.block_id == "b2"
    assert hit.block_index == 1

    handle_rect = fix.overlay.handle_rect_for(hit)
    # Handle parks at the left margin (negative x) and is centred on the row.
    assert handle_rect.right() <= 0.0
    assert 100.0 <= handle_rect.center().y() <= 200.0


def test_hover_outside_any_block_hides_handle(qtbot) -> None:  # type: ignore[no-untyped-def]
    fix = _make_three_block_frame()
    qtbot.addWidget(fix.view)

    fix.overlay.simulate_hover(QPointF(50.0, 150.0))
    assert fix.overlay.is_handle_visible() is True

    fix.overlay.simulate_hover(QPointF(50.0, 999.0))
    assert fix.overlay.is_handle_visible() is False
    assert fix.overlay.hovered_block is None


def test_drag_block_1_to_block_3_emits_move_command(qtbot) -> None:  # type: ignore[no-untyped-def]
    """Spec §12 unit-28: ``drag block 1 -> block 3 -> MoveBlockCommand(story, 1, 2)``.

    "Block 1" / "block 3" in the spec read most naturally as 0-based
    block indices in the "drag the handle above this row, drop above
    that row" sense — so source = index 1, target = index 2, yielding
    ``MoveBlockCommand(story_id, 1, 2)``.
    """
    fix = _make_three_block_frame()
    qtbot.addWidget(fix.view)

    cmd = fix.overlay.simulate_drag_release(
        source_local_pos=QPointF(50.0, 150.0),  # block at index 1
        target_local_pos=QPointF(50.0, 250.0),  # block at index 2
    )

    assert isinstance(cmd, MoveBlockCommand)
    assert cmd.story_id == "story-1"
    assert cmd.from_index == 1
    assert cmd.to_index == 2
    assert fix.sink == [cmd]


def test_drag_outside_blocks_emits_nothing(qtbot) -> None:  # type: ignore[no-untyped-def]
    fix = _make_three_block_frame()
    qtbot.addWidget(fix.view)

    cmd = fix.overlay.simulate_drag_release(
        source_local_pos=QPointF(50.0, 50.0),  # block 1
        target_local_pos=QPointF(50.0, 999.0),  # nowhere
    )

    assert cmd is None
    assert fix.sink == []


def test_context_menu_lists_expected_actions(qtbot) -> None:  # type: ignore[no-untyped-def]
    fix = _make_three_block_frame()
    qtbot.addWidget(fix.view)

    fix.overlay.simulate_hover(QPointF(50.0, 150.0))
    hit = fix.overlay.hovered_block
    assert hit is not None

    menu = fix.overlay.build_context_menu(hit)
    labels = [a.text() for a in menu.actions() if a.text()]
    assert "Duplicate" in labels
    assert "Delete" in labels
    assert "Convert To" in labels

    convert_menu = next(a.menu() for a in menu.actions() if a.text() == "Convert To")
    assert convert_menu is not None
    convert_labels = [a.text() for a in convert_menu.actions()]
    for label, _kind, _attrs in CONVERT_TO_OPTIONS:
        assert label in convert_labels


def test_context_menu_duplicate_emits_duplicate_command(qtbot) -> None:  # type: ignore[no-untyped-def]
    fix = _make_three_block_frame()
    qtbot.addWidget(fix.view)

    fix.overlay.simulate_hover(QPointF(50.0, 150.0))
    hit = fix.overlay.hovered_block
    assert hit is not None

    menu = fix.overlay.build_context_menu(hit)
    duplicate_action = next(a for a in menu.actions() if a.text() == "Duplicate")
    cmd = fix.overlay.dispatch_menu_action(duplicate_action, hit)

    assert isinstance(cmd, DuplicateBlockCommand)
    assert cmd.block_id == "b2"
    assert fix.sink == [cmd]


def test_context_menu_delete_emits_delete_command(qtbot) -> None:  # type: ignore[no-untyped-def]
    fix = _make_three_block_frame()
    qtbot.addWidget(fix.view)

    fix.overlay.simulate_hover(QPointF(50.0, 150.0))
    hit = fix.overlay.hovered_block
    assert hit is not None

    menu = fix.overlay.build_context_menu(hit)
    delete_action = next(a for a in menu.actions() if a.text() == "Delete")
    cmd = fix.overlay.dispatch_menu_action(delete_action, hit)

    assert isinstance(cmd, DeleteBlockCommand)
    assert cmd.block_id == "b2"
    assert fix.sink == [cmd]


def test_context_menu_convert_emits_transform_command(qtbot) -> None:  # type: ignore[no-untyped-def]
    fix = _make_three_block_frame()
    qtbot.addWidget(fix.view)

    fix.overlay.simulate_hover(QPointF(50.0, 50.0))  # block 1 (paragraph)
    hit = fix.overlay.hovered_block
    assert hit is not None

    menu = fix.overlay.build_context_menu(hit)
    convert_menu = next(a.menu() for a in menu.actions() if a.text() == "Convert To")
    assert convert_menu is not None
    h2_action = next(a for a in convert_menu.actions() if a.text() == "Heading 2")
    cmd = fix.overlay.dispatch_menu_action(h2_action, hit)

    assert isinstance(cmd, TransformBlockCommand)
    assert cmd.block_id == "b1"
    assert cmd.target_kind == "heading"
    assert cmd.target_attrs == {"level": 2}
    assert fix.sink == [cmd]
