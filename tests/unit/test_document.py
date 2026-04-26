"""Unit tests for `msword.model.document` — see spec §3 (Document-MVC) and §4."""

from __future__ import annotations

import pytest

from msword.model.document import Document, DocumentMeta
from msword.model.master_page import MasterPage
from msword.model.page import Page


def test_empty_document_defaults() -> None:
    doc = Document()
    assert isinstance(doc.meta, DocumentMeta)
    assert doc.meta.locale == "en-US"
    assert doc.pages == []
    assert doc.master_pages == []
    assert len(doc.assets) == 0
    # Stub collections are present and empty.
    assert doc.color_profiles == []
    assert doc.color_swatches == []
    assert doc.paragraph_styles == []
    assert doc.character_styles == []
    assert doc.object_styles == []
    assert doc.stories == []


def test_add_three_pages_order_signals_len() -> None:
    """Add three pages and assert order, signals fired in order, and len."""
    doc = Document()
    added_indices: list[int] = []
    changed_count = [0]
    doc.page_added.connect(added_indices.append)
    doc.changed.connect(lambda: changed_count.__setitem__(0, changed_count[0] + 1))

    p1 = Page(id="p1")
    p2 = Page(id="p2")
    p3 = Page(id="p3")

    assert doc.add_page(p1) == 0
    assert doc.add_page(p2) == 1
    assert doc.add_page(p3) == 2

    assert [p.id for p in doc.pages] == ["p1", "p2", "p3"]
    assert len(doc.pages) == 3
    assert added_indices == [0, 1, 2]
    assert changed_count[0] == 3


def test_add_page_at_index() -> None:
    doc = Document()
    doc.add_page(Page(id="a"))
    doc.add_page(Page(id="c"))
    doc.add_page(Page(id="b"), index=1)
    assert [p.id for p in doc.pages] == ["a", "b", "c"]


def test_remove_page_emits_signal() -> None:
    doc = Document()
    doc.add_page(Page(id="a"))
    doc.add_page(Page(id="b"))
    removed_indices: list[int] = []
    doc.page_removed.connect(removed_indices.append)

    page = doc.remove_page(0)
    assert page.id == "a"
    assert [p.id for p in doc.pages] == ["b"]
    assert removed_indices == [0]


def test_move_page_0_to_2_emits_reorder_signal() -> None:
    """Move page from index 0 to 2; assert page_reordered fired correctly."""
    doc = Document()
    for pid in ("a", "b", "c"):
        doc.add_page(Page(id=pid))
    reorder_events: list[tuple[int, int]] = []
    doc.page_reordered.connect(lambda old, new: reorder_events.append((old, new)))

    doc.move_page(0, 2)

    assert [p.id for p in doc.pages] == ["b", "c", "a"]
    assert reorder_events == [(0, 2)]


def test_move_page_no_op_when_indices_equal() -> None:
    doc = Document()
    doc.add_page(Page(id="a"))
    doc.add_page(Page(id="b"))
    reorder_events: list[tuple[int, int]] = []
    doc.page_reordered.connect(lambda old, new: reorder_events.append((old, new)))

    doc.move_page(1, 1)

    assert reorder_events == []
    assert [p.id for p in doc.pages] == ["a", "b"]


def test_add_page_index_out_of_range_raises() -> None:
    doc = Document()
    with pytest.raises(IndexError):
        doc.add_page(Page(id="x"), index=5)


def test_master_pages_add_remove_emits_signals() -> None:
    doc = Document()
    added: list[str] = []
    removed: list[str] = []
    doc.master_page_added.connect(added.append)
    doc.master_page_removed.connect(removed.append)

    doc.add_master_page(MasterPage(id="A", name="A-Master"))
    doc.add_master_page(MasterPage(id="B", name="B-Master", parent_master_id="A"))
    assert [m.id for m in doc.master_pages] == ["A", "B"]
    assert added == ["A", "B"]

    doc.remove_master_page("A")
    assert [m.id for m in doc.master_pages] == ["B"]
    assert removed == ["A"]


def test_add_master_page_duplicate_id_raises() -> None:
    doc = Document()
    doc.add_master_page(MasterPage(id="A", name="A"))
    with pytest.raises(ValueError):
        doc.add_master_page(MasterPage(id="A", name="A again"))


def test_remove_master_page_missing_raises() -> None:
    doc = Document()
    with pytest.raises(KeyError):
        doc.remove_master_page("nope")


def test_to_dict_from_dict_roundtrip() -> None:
    """Document round-trips through to_dict/from_dict for non-stub fields."""
    doc = Document()
    doc.meta = DocumentMeta(
        title="Hello",
        author="Ada",
        locale="ar-SA",
        default_language="ar",
    )
    doc.add_master_page(MasterPage(id="A", name="A-Master"))
    doc.add_page(Page(id="p1", master_id="A"))
    doc.add_page(Page(id="p2", master_id="A"))

    snapshot = doc.to_dict()
    restored = Document.from_dict(snapshot)

    assert restored.meta.title == "Hello"
    assert restored.meta.author == "Ada"
    assert restored.meta.locale == "ar-SA"
    assert restored.meta.default_language == "ar"
    assert [m.id for m in restored.master_pages] == ["A"]
    assert [p.id for p in restored.pages] == ["p1", "p2"]
    assert all(p.master_id == "A" for p in restored.pages)
    # Round-trip should be idempotent at the dict level.
    assert restored.to_dict() == snapshot


def test_changed_signal_fires_on_every_mutation() -> None:
    doc = Document()
    fires = [0]
    doc.changed.connect(lambda: fires.__setitem__(0, fires[0] + 1))

    doc.add_page(Page(id="a"))
    doc.add_page(Page(id="b"))
    doc.move_page(0, 1)
    doc.remove_page(0)
    doc.add_master_page(MasterPage(id="M", name="M"))
    doc.remove_master_page("M")

    assert fires[0] == 6
