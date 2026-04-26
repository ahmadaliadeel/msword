"""Unit tests for `msword.feat.find_engine` (no Qt event loop)."""

from __future__ import annotations

import unicodedata

import pytest

from msword.feat.find_engine import find_all, replace_all
from msword.model.blocks import CalloutBlock, ParagraphBlock
from msword.model.document import Document
from msword.model.run import Run
from msword.model.story import Story


def _doc_with_paragraphs(*paragraphs: str) -> Document:
    """Build a document with one story; one paragraph per arg, one run per paragraph."""
    doc = Document()
    blocks = [
        ParagraphBlock(id=f"p{i}", runs=[Run(text=p)])
        for i, p in enumerate(paragraphs)
    ]
    doc.stories.append(Story(id="s1", blocks=blocks))
    return doc


# --------------------------------------------------------------- find_all


def test_find_all_basic_case_insensitive() -> None:
    doc = _doc_with_paragraphs(
        "Hello world",
        "well, hello there",
        "Hello again, hello hello",
    )
    matches = find_all(doc, "hello", case_sensitive=False)
    # 1 + 1 + 3 = 5
    assert len(matches) == 5


def test_find_all_case_sensitive() -> None:
    doc = _doc_with_paragraphs("Hello hello HELLO")
    matches = find_all(doc, "hello", case_sensitive=True)
    assert len(matches) == 1


def test_find_all_whole_word() -> None:
    doc = _doc_with_paragraphs("cat scattered cathedral cat.")
    matches = find_all(doc, "cat", whole_word=True)
    # only the standalone "cat" tokens, not "scattered" or "cathedral"
    assert len(matches) == 2


def test_find_all_regex_word_boundary() -> None:
    doc = _doc_with_paragraphs("hello world", "underworld worldview", "world!")
    matches = find_all(doc, r"\bworld\b", regex=True)
    # "hello world" → 1, "underworld worldview" → 0, "world!" → 1
    assert len(matches) == 2


def test_find_all_offsets_map_back_to_run() -> None:
    doc = _doc_with_paragraphs("abc hello xyz")
    matches = find_all(doc, "hello")
    assert len(matches) == 1
    m = matches[0]
    assert m.run_index == 0
    assert m.char_start == 4
    assert m.char_end == 9


def test_find_all_nfc_composed_and_decomposed() -> None:
    composed = "café"  # NFC: "café"
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed

    doc_composed = _doc_with_paragraphs(composed)
    doc_decomposed = _doc_with_paragraphs(decomposed)

    # composed query, composed haystack
    assert len(find_all(doc_composed, composed)) == 1
    # composed query, decomposed haystack — NFC normalises both → match
    assert len(find_all(doc_decomposed, composed)) == 1
    # decomposed query, composed haystack — same logic, both normalise
    assert len(find_all(doc_composed, decomposed)) == 1


def test_find_all_arabic_logical_order() -> None:
    # "Hello, مرحبا (greeting) world"
    doc = _doc_with_paragraphs("Hello, مرحبا (greeting) world", "ابحث عن مرحبا هنا")
    matches = find_all(doc, "مرحبا")
    assert len(matches) == 2


def test_find_all_urdu() -> None:
    doc = _doc_with_paragraphs("سلام، یہ اردو ہے۔ یہ ٹیسٹ ہے۔")  # noqa: RUF001
    matches = find_all(doc, "یہ")
    assert len(matches) == 2


def test_find_all_empty_query_raises() -> None:
    doc = _doc_with_paragraphs("anything")
    with pytest.raises(ValueError):
        find_all(doc, "")


def test_find_all_scope_story_requires_id() -> None:
    doc = _doc_with_paragraphs("text")
    with pytest.raises(ValueError):
        find_all(doc, "text", scope="story")


def test_find_all_scope_story_filters() -> None:
    s1 = Story(
        id="s1", blocks=[ParagraphBlock(id="p1", runs=[Run(text="needle in story 1")])]
    )
    s2 = Story(
        id="s2", blocks=[ParagraphBlock(id="p2", runs=[Run(text="needle in story 2")])]
    )
    doc = Document()
    doc.stories.extend([s1, s2])
    all_matches = find_all(doc, "needle", scope="document")
    assert len(all_matches) == 2
    only_s1 = find_all(doc, "needle", scope="story", story_id=s1.id)
    assert len(only_s1) == 1
    assert only_s1[0].story_id == s1.id


def test_find_all_multi_run_block() -> None:
    """A match that crosses run boundaries is reported with extra_runs."""
    block = ParagraphBlock(id="p1", runs=[Run(text="hel"), Run(text="lo world")])
    doc = Document()
    doc.stories.append(Story(id="s1", blocks=[block]))
    matches = find_all(doc, "hello")
    assert len(matches) == 1
    m = matches[0]
    assert m.run_index == 0
    assert m.char_start == 0
    assert m.char_end == 3
    assert m.extra_runs == ((1, 0, 2),)


def test_find_all_skips_zero_width_regex() -> None:
    doc = _doc_with_paragraphs("hello world")
    # \b alone is zero-width; engine should skip rather than emit infinite matches.
    matches = find_all(doc, r"\b", regex=True)
    assert matches == []


def test_find_all_recurses_into_container_blocks() -> None:
    inner = ParagraphBlock(id="p_inner", runs=[Run(text="needle inside callout")])
    outer = CalloutBlock(id="c1", blocks=[inner])
    doc = Document()
    doc.stories.append(Story(id="s1", blocks=[outer]))
    matches = find_all(doc, "needle")
    assert len(matches) == 1
    assert matches[0].block_id == inner.id


# ------------------------------------------------------------ replace_all


def test_replace_all_returns_macro_with_per_match_commands() -> None:
    doc = _doc_with_paragraphs("foo bar foo baz foo")
    matches = find_all(doc, "foo")
    macro = replace_all(doc, matches, "qux")
    # Three matches, each contributing exactly one ReplaceTextInRunCommand
    # (single-run block).
    assert len(macro._children) == 3


def test_replace_all_redo_then_undo_round_trips() -> None:
    doc = _doc_with_paragraphs("foo bar foo baz")
    original = doc.stories[0].blocks[0].runs[0].text
    matches = find_all(doc, "foo")
    macro = replace_all(doc, matches, "QUUX")
    macro.redo()
    assert doc.stories[0].blocks[0].runs[0].text == "QUUX bar QUUX baz"
    macro.undo()
    assert doc.stories[0].blocks[0].runs[0].text == original


def test_replace_all_empty_matches_is_noop_macro() -> None:
    doc = _doc_with_paragraphs("nothing to do")
    macro = replace_all(doc, [], "x")
    assert macro._children == []


def test_replace_all_handles_overlapping_offsets_correctly() -> None:
    """Matches in the same block must be applied right-to-left so prior
    offsets don't shift under our feet."""
    doc = _doc_with_paragraphs("aaaa")
    matches = find_all(doc, "aa")
    # "aaaa" contains two non-overlapping occurrences of "aa"
    assert len(matches) == 2
    macro = replace_all(doc, matches, "B")
    macro.redo()
    assert doc.stories[0].blocks[0].runs[0].text == "BB"


def test_replace_all_cross_run_match() -> None:
    block = ParagraphBlock(id="p1", runs=[Run(text="hel"), Run(text="lo!")])
    doc = Document()
    doc.stories.append(Story(id="s1", blocks=[block]))
    matches = find_all(doc, "hello")
    macro = replace_all(doc, matches, "HI")
    macro.redo()
    # Replacement goes into first run; second run loses its covered slice.
    assert block.runs[0].text == "HI"
    assert block.runs[1].text == "!"
