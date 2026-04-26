"""Integration tests for the Linker and Unlinker tools (unit 21)."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from msword.ui.tools._stubs import (
    StubCanvas,
    _StubLinkFrameCommand,
    _StubMergeStoriesCommand,
    _StubStory,
    _StubTextFrame,
    _StubUnlinkFrameCommand,
)
from msword.ui.tools.linker import LinkerTool
from msword.ui.tools.unlinker import UnlinkerTool

_NoMod = Qt.KeyboardModifier.NoModifier


def _press(scene_pos: tuple[float, float]) -> QMouseEvent:
    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(*scene_pos),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        _NoMod,
    )


def _click(tool: LinkerTool | UnlinkerTool, scene_pos: tuple[float, float]) -> None:
    tool.on_mouse_press(_press(scene_pos), QPointF(*scene_pos))


@pytest.fixture
def canvas_with_two_text_frames() -> tuple[StubCanvas, _StubTextFrame, _StubTextFrame]:
    canvas = StubCanvas()
    page = canvas.current_page

    # Source frame A starts with a story that has one paragraph.
    story_a = _StubStory(blocks=["A: Hello world"])
    frame_a = _StubTextFrame(x=0, y=0, w=100, h=50, story_ref=story_a, story_index=0)

    # Target frame B has no story at all (truly empty).
    frame_b = _StubTextFrame(x=200, y=0, w=100, h=50, story_ref=None, story_index=0)

    page.frames.append(frame_a)
    page.frames.append(frame_b)
    return canvas, frame_a, frame_b


# ---------------------------------------------------------------------------
# LinkerTool
# ---------------------------------------------------------------------------


def test_linker_first_click_stores_source(
    canvas_with_two_text_frames: tuple[StubCanvas, _StubTextFrame, _StubTextFrame],
) -> None:
    canvas, frame_a, _frame_b = canvas_with_two_text_frames
    tool = LinkerTool()
    canvas.set_tool(tool)

    _click(tool, (50, 25))  # inside frame A

    assert tool.from_frame is frame_a
    assert canvas.executed_commands == []
    # Faint preview line should have been installed as an overlay.
    assert len(canvas.overlays) == 1


def test_linker_second_click_on_empty_target_pushes_link_command(
    canvas_with_two_text_frames: tuple[StubCanvas, _StubTextFrame, _StubTextFrame],
) -> None:
    canvas, frame_a, frame_b = canvas_with_two_text_frames
    tool = LinkerTool()
    canvas.set_tool(tool)

    _click(tool, (50, 25))   # source = A
    _click(tool, (250, 25))  # target = B (empty story)

    assert len(canvas.executed_commands) == 1
    command = canvas.executed_commands[0]
    assert isinstance(command, _StubLinkFrameCommand)
    assert command.source is frame_a
    assert command.target is frame_b

    # Tool should reset and remove its preview after a successful link.
    assert tool.from_frame is None
    assert canvas.overlays == []
    assert canvas.recompose_calls == 1

    # Per spec: target.story_ref = source.story_ref; story_index += 1.
    assert frame_b.story_ref is frame_a.story_ref
    assert frame_b.story_index == 1


def test_linker_target_with_non_empty_story_confirms_then_merges(
    canvas_with_two_text_frames: tuple[StubCanvas, _StubTextFrame, _StubTextFrame],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canvas, frame_a, frame_b = canvas_with_two_text_frames
    # Give B its own non-empty story so the merge-confirm dialog is required.
    frame_b.story_ref = _StubStory(blocks=["B: existing content"])
    frame_b.story_index = 0

    tool = LinkerTool()
    canvas.set_tool(tool)

    # Mock the dialog: user presses Yes.
    confirm_calls = {"n": 0}

    def _confirm_yes() -> bool:
        confirm_calls["n"] += 1
        return True

    monkeypatch.setattr(tool, "_confirm_merge", _confirm_yes)

    _click(tool, (50, 25))   # source = A
    _click(tool, (250, 25))  # target = B (non-empty)

    assert confirm_calls["n"] == 1
    assert len(canvas.executed_commands) == 1
    command = canvas.executed_commands[0]
    assert isinstance(command, _StubMergeStoriesCommand)
    assert command.source is frame_a
    assert command.target is frame_b

    # B's blocks should now be appended onto A's story.
    assert frame_a.story_ref is not None
    assert frame_a.story_ref.blocks == ["A: Hello world", "B: existing content"]
    # And B should now point at A's story chain.
    assert frame_b.story_ref is frame_a.story_ref
    assert frame_b.story_index == 1
    assert tool.from_frame is None


def test_linker_target_with_non_empty_story_aborts_on_no(
    canvas_with_two_text_frames: tuple[StubCanvas, _StubTextFrame, _StubTextFrame],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canvas, _frame_a, frame_b = canvas_with_two_text_frames
    frame_b.story_ref = _StubStory(blocks=["B: existing content"])
    original_story = frame_b.story_ref

    tool = LinkerTool()
    canvas.set_tool(tool)
    monkeypatch.setattr(tool, "_confirm_merge", lambda: False)

    _click(tool, (50, 25))
    _click(tool, (250, 25))

    assert canvas.executed_commands == []
    assert frame_b.story_ref is original_story  # untouched
    assert tool.from_frame is None  # state reset on cancel


def test_linker_click_in_empty_space_resets_state(
    canvas_with_two_text_frames: tuple[StubCanvas, _StubTextFrame, _StubTextFrame],
) -> None:
    canvas, _frame_a, _frame_b = canvas_with_two_text_frames
    tool = LinkerTool()
    canvas.set_tool(tool)

    _click(tool, (50, 25))   # source = A
    _click(tool, (500, 500))  # empty space → cancel

    assert tool.from_frame is None
    assert canvas.executed_commands == []
    assert canvas.overlays == []


def test_linker_self_click_is_noop(
    canvas_with_two_text_frames: tuple[StubCanvas, _StubTextFrame, _StubTextFrame],
) -> None:
    canvas, _frame_a, _frame_b = canvas_with_two_text_frames
    tool = LinkerTool()
    canvas.set_tool(tool)

    _click(tool, (50, 25))  # source = A
    _click(tool, (10, 10))  # also inside A

    assert canvas.executed_commands == []
    assert tool.from_frame is None


# ---------------------------------------------------------------------------
# UnlinkerTool
# ---------------------------------------------------------------------------


def test_unlinker_click_on_linked_frame_pushes_unlink_command(
    canvas_with_two_text_frames: tuple[StubCanvas, _StubTextFrame, _StubTextFrame],
) -> None:
    canvas, frame_a, frame_b = canvas_with_two_text_frames
    # Link B onto A's story so the unlink has something to do.
    frame_b.story_ref = frame_a.story_ref
    frame_b.story_index = 1

    tool = UnlinkerTool()
    canvas.set_tool(tool)

    _click(tool, (250, 25))  # click frame B

    assert len(canvas.executed_commands) == 1
    command = canvas.executed_commands[0]
    assert isinstance(command, _StubUnlinkFrameCommand)
    assert command.frame is frame_b
    # After redo: target detached from chain.
    assert frame_b.story_ref is None
    assert frame_b.story_index == 0
    assert canvas.recompose_calls == 1


def test_unlinker_click_on_unlinked_frame_is_noop(
    canvas_with_two_text_frames: tuple[StubCanvas, _StubTextFrame, _StubTextFrame],
) -> None:
    canvas, _frame_a, frame_b = canvas_with_two_text_frames
    assert frame_b.story_ref is None  # precondition

    tool = UnlinkerTool()
    canvas.set_tool(tool)

    _click(tool, (250, 25))

    assert canvas.executed_commands == []


def test_unlinker_click_in_empty_space_is_noop(
    canvas_with_two_text_frames: tuple[StubCanvas, _StubTextFrame, _StubTextFrame],
) -> None:
    canvas, _frame_a, _frame_b = canvas_with_two_text_frames
    tool = UnlinkerTool()
    canvas.set_tool(tool)

    _click(tool, (1000, 1000))

    assert canvas.executed_commands == []
