"""Tests for `msword.commands` (unit 9).

These tests use a minimal in-memory `Document` stand-in that matches the
`commands.Document` protocol (units 2-7 will land the real one). The
stand-in is a real `QObject` so `changed` is a true Qt signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from PySide6.QtCore import QObject, Signal

from msword.commands import (
    AddFrameCommand,
    AddPageCommand,
    Command,
    MacroCommand,
    MoveFrameCommand,
    MovePageCommand,
    RemoveFrameCommand,
    RemovePageCommand,
    ResizeFrameCommand,
    UndoStack,
)

# --- fakes -----------------------------------------------------------------


@dataclass
class FakeFrame:
    id: str
    x: float = 0.0
    y: float = 0.0
    w: float = 100.0
    h: float = 50.0


@dataclass
class FakePage:
    id: str
    frames: dict[str, FakeFrame] = field(default_factory=dict)


class FakeDocument(QObject):
    """Tiny stand-in matching the `commands.Document` protocol."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.undo_stack = UndoStack(self)
        self._pages: list[FakePage] = []

    # --- pages
    def add_page(self, page: FakePage, index: int | None = None) -> int:
        if index is None or index >= len(self._pages):
            self._pages.append(page)
            return len(self._pages) - 1
        self._pages.insert(index, page)
        return index

    def remove_page(self, index: int) -> FakePage:
        return self._pages.pop(index)

    def move_page(self, from_index: int, to_index: int) -> None:
        page = self._pages.pop(from_index)
        self._pages.insert(to_index, page)

    def page_count(self) -> int:
        return len(self._pages)

    def page_at(self, index: int) -> FakePage:
        return self._pages[index]

    def index_of_page(self, page_id: str) -> int:
        return next(i for i, p in enumerate(self._pages) if p.id == page_id)

    # --- frames
    def add_frame(self, page_id: str, frame: FakeFrame) -> None:
        page = self._page_by_id(page_id)
        page.frames[frame.id] = frame

    def remove_frame(self, page_id: str, frame_id: str) -> FakeFrame:
        return self._page_by_id(page_id).frames.pop(frame_id)

    def get_frame(self, page_id: str, frame_id: str) -> FakeFrame:
        return self._page_by_id(page_id).frames[frame_id]

    def _page_by_id(self, page_id: str) -> FakePage:
        return next(p for p in self._pages if p.id == page_id)


@pytest.fixture
def doc() -> FakeDocument:
    return FakeDocument()


# --- AddPageCommand --------------------------------------------------------


def test_add_page_then_undo_restores_count(doc: FakeDocument) -> None:
    initial = doc.page_count()
    page = FakePage(id="p1")

    doc.undo_stack.push(AddPageCommand(doc, page))

    assert doc.page_count() == initial + 1
    assert doc.page_at(initial).id == "p1"

    doc.undo_stack.undo()

    assert doc.page_count() == initial


def test_add_page_redo_after_undo(doc: FakeDocument) -> None:
    page = FakePage(id="p1")
    doc.undo_stack.push(AddPageCommand(doc, page))
    doc.undo_stack.undo()
    doc.undo_stack.redo()
    assert doc.page_count() == 1
    assert doc.page_at(0).id == "p1"


def test_add_page_at_specific_index(doc: FakeDocument) -> None:
    doc._pages.extend([FakePage(id="a"), FakePage(id="b")])
    doc.undo_stack.push(AddPageCommand(doc, FakePage(id="middle"), index=1))
    assert [p.id for p in doc._pages] == ["a", "middle", "b"]
    doc.undo_stack.undo()
    assert [p.id for p in doc._pages] == ["a", "b"]


# --- RemovePageCommand -----------------------------------------------------


def test_remove_page_undo_restores(doc: FakeDocument) -> None:
    doc._pages.extend([FakePage(id="a"), FakePage(id="b"), FakePage(id="c")])
    doc.undo_stack.push(RemovePageCommand(doc, 1))
    assert [p.id for p in doc._pages] == ["a", "c"]
    doc.undo_stack.undo()
    assert [p.id for p in doc._pages] == ["a", "b", "c"]


# --- MovePageCommand -------------------------------------------------------


def test_move_page_then_undo(doc: FakeDocument) -> None:
    doc._pages.extend([FakePage(id="a"), FakePage(id="b"), FakePage(id="c")])

    doc.undo_stack.push(MovePageCommand(doc, 0, 2))

    assert [p.id for p in doc._pages] == ["b", "c", "a"]

    doc.undo_stack.undo()

    assert [p.id for p in doc._pages] == ["a", "b", "c"]


# --- frame commands --------------------------------------------------------


def test_add_remove_frame(doc: FakeDocument) -> None:
    doc.undo_stack.push(AddPageCommand(doc, FakePage(id="p1")))
    frame = FakeFrame(id="f1", x=10, y=20, w=100, h=50)

    doc.undo_stack.push(AddFrameCommand(doc, "p1", frame))
    assert "f1" in doc.page_at(0).frames

    doc.undo_stack.push(RemoveFrameCommand(doc, "p1", "f1"))
    assert "f1" not in doc.page_at(0).frames

    doc.undo_stack.undo()  # undo remove
    assert "f1" in doc.page_at(0).frames


def test_move_frame_records_old_position(doc: FakeDocument) -> None:
    doc.undo_stack.push(AddPageCommand(doc, FakePage(id="p1")))
    frame = FakeFrame(id="f1", x=10.0, y=20.0)
    doc.undo_stack.push(AddFrameCommand(doc, "p1", frame))

    doc.undo_stack.push(MoveFrameCommand(doc, "p1", "f1", dx=5.0, dy=-3.0))
    assert (frame.x, frame.y) == (15.0, 17.0)

    doc.undo_stack.undo()
    assert (frame.x, frame.y) == (10.0, 20.0)


def test_resize_frame_records_old_size(doc: FakeDocument) -> None:
    doc.undo_stack.push(AddPageCommand(doc, FakePage(id="p1")))
    frame = FakeFrame(id="f1", w=100.0, h=50.0)
    doc.undo_stack.push(AddFrameCommand(doc, "p1", frame))

    doc.undo_stack.push(ResizeFrameCommand(doc, "p1", "f1", new_w=200.0, new_h=80.0))
    assert (frame.w, frame.h) == (200.0, 80.0)

    doc.undo_stack.undo()
    assert (frame.w, frame.h) == (100.0, 50.0)


# --- macros ----------------------------------------------------------------


def test_begin_end_macro_groups_into_single_undo(doc: FakeDocument) -> None:
    doc.undo_stack.begin_macro("complex")
    doc.undo_stack.push(AddPageCommand(doc, FakePage(id="a")))
    doc.undo_stack.push(AddPageCommand(doc, FakePage(id="b")))
    doc.undo_stack.push(AddPageCommand(doc, FakePage(id="c")))
    doc.undo_stack.end_macro()

    assert doc.page_count() == 3

    doc.undo_stack.undo()  # one call → all three rolled back

    assert doc.page_count() == 0


def test_macro_command_runs_children_forward_and_reverse(doc: FakeDocument) -> None:
    doc.undo_stack.push(AddPageCommand(doc, FakePage(id="p1")))
    frame_a = FakeFrame(id="a", x=0, y=0)
    frame_b = FakeFrame(id="b", x=0, y=0)

    macro = MacroCommand(
        doc,
        [
            AddFrameCommand(doc, "p1", frame_a),
            AddFrameCommand(doc, "p1", frame_b),
        ],
        text="batch add",
    )
    doc.undo_stack.push(macro)

    assert set(doc.page_at(0).frames) == {"a", "b"}

    doc.undo_stack.undo()

    assert doc.page_at(0).frames == {}


# --- signal contracts ------------------------------------------------------


def _count_emits(signal: Signal) -> tuple[list[int], object]:
    # Returns a list that grows by 1 each time the signal fires, plus the
    # callable that should be connected to the signal. (The list is what
    # the test inspects; keeping the slot reference alive prevents Qt from
    # garbage-collecting it.)
    box: list[int] = []
    slot = lambda *_a: box.append(1)  # noqa: E731 — terse closure intentional
    signal.connect(slot)
    return box, slot


def test_changed_emits_exactly_once_per_command(doc: FakeDocument) -> None:
    box, _slot = _count_emits(doc.changed)

    doc.undo_stack.push(AddPageCommand(doc, FakePage(id="a")))
    assert sum(box) == 1

    doc.undo_stack.undo()
    assert sum(box) == 2

    doc.undo_stack.redo()
    assert sum(box) == 3


def test_clean_changed_fires_after_set_clean(doc: FakeDocument) -> None:
    box, _slot = _count_emits(doc.undo_stack.clean_changed)

    doc.undo_stack.push(AddPageCommand(doc, FakePage(id="a")))
    # Pushing dirties the stack — `cleanChanged(False)` fires once.
    assert sum(box) >= 1

    before = sum(box)
    doc.undo_stack.set_clean()
    # Marking clean fires `cleanChanged(True)` exactly once.
    assert sum(box) == before + 1


def test_index_changed_fires_on_push_and_undo(doc: FakeDocument) -> None:
    box, _slot = _count_emits(doc.undo_stack.index_changed)

    doc.undo_stack.push(AddPageCommand(doc, FakePage(id="a")))
    after_push = sum(box)
    assert after_push >= 1

    doc.undo_stack.undo()
    assert sum(box) > after_push


# --- can_undo / can_redo / clear -------------------------------------------


def test_can_undo_redo_and_clear(doc: FakeDocument) -> None:
    assert not doc.undo_stack.can_undo()
    assert not doc.undo_stack.can_redo()

    doc.undo_stack.push(AddPageCommand(doc, FakePage(id="a")))
    assert doc.undo_stack.can_undo()
    assert not doc.undo_stack.can_redo()

    doc.undo_stack.undo()
    assert not doc.undo_stack.can_undo()
    assert doc.undo_stack.can_redo()

    doc.undo_stack.clear()
    assert not doc.undo_stack.can_undo()
    assert not doc.undo_stack.can_redo()


# --- text labels -----------------------------------------------------------


@pytest.mark.parametrize(
    ("factory", "expected"),
    [
        (lambda d: AddPageCommand(d, FakePage(id="x")), "Add Page"),
        (lambda d: RemovePageCommand(d, 0), "Remove Page"),
        (lambda d: MovePageCommand(d, 0, 1), "Move Page"),
        (lambda d: AddFrameCommand(d, "p", FakeFrame(id="f")), "Add Frame"),
        (lambda d: RemoveFrameCommand(d, "p", "f"), "Remove Frame"),
        (lambda d: MoveFrameCommand(d, "p", "f", 0, 0), "Move Frame"),
        (lambda d: ResizeFrameCommand(d, "p", "f", 0, 0), "Resize Frame"),
    ],
)
def test_command_labels(doc: FakeDocument, factory, expected: str) -> None:  # type: ignore[no-untyped-def]
    cmd: Command = factory(doc)
    assert cmd.text() == expected
