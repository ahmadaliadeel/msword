from __future__ import annotations

from msword.feat.toc import (
    Document,
    HeadingBlock,
    PageRefRun,
    ParagraphBlock,
    Run,
    Story,
    TocAutoUpdater,
    TocSpec,
    UpdateTocCommand,
    generate_toc_blocks,
    resolve_page_refs,
    update_toc,
)


def _build_document() -> Document:
    """Build the canonical 3-story fixture from the spec.

    story1 [H1 "Intro", H2 "Sub", P]
    story2 [H1 "Methods"]
    story3 [P, H1 "Results"]
    """
    story1 = Story(
        id="s1",
        blocks=[
            HeadingBlock(id="h-intro", level=1, runs=[Run(text="Intro")]),
            HeadingBlock(id="h-sub", level=2, runs=[Run(text="Sub")]),
            ParagraphBlock(id="p1", runs=[Run(text="body")]),
        ],
    )
    story2 = Story(
        id="s2",
        blocks=[HeadingBlock(id="h-methods", level=1, runs=[Run(text="Methods")])],
    )
    story3 = Story(
        id="s3",
        blocks=[
            ParagraphBlock(id="p2", runs=[Run(text="lead")]),
            HeadingBlock(id="h-results", level=1, runs=[Run(text="Results")]),
        ],
    )
    toc_story = Story(id="toc", is_toc=True)
    return Document(stories=[story1, story2, story3, toc_story])


def _heading_texts(blocks: list) -> list[str]:
    """Extract entry heading text from generate_toc_blocks output (skipping title)."""
    out: list[str] = []
    for block in blocks[1:]:
        assert isinstance(block, ParagraphBlock)
        # First run carries the heading text.
        first = block.runs[0]
        assert isinstance(first, Run)
        out.append(first.text)
    return out


def test_generate_toc_levels_1_and_2() -> None:
    doc = _build_document()
    blocks = generate_toc_blocks(doc, TocSpec(levels=(1, 2)))

    # Title + 4 entries (Intro, Sub, Methods, Results).
    assert len(blocks) == 5
    title = blocks[0]
    assert isinstance(title, HeadingBlock)
    assert title.level == 1
    assert title.text == "Contents"

    assert _heading_texts(blocks) == ["Intro", "Sub", "Methods", "Results"]


def test_generate_toc_level_1_only_excludes_sub() -> None:
    doc = _build_document()
    blocks = generate_toc_blocks(doc, TocSpec(levels=(1,)))

    # Title + 3 entries (Intro, Methods, Results); Sub is excluded.
    assert len(blocks) == 4
    assert _heading_texts(blocks) == ["Intro", "Methods", "Results"]


def test_entry_paragraph_uses_per_level_style() -> None:
    doc = _build_document()
    spec = TocSpec(levels=(1, 2), style_per_level={1: "TOC Lvl1", 2: "TOC Lvl2"})
    blocks = generate_toc_blocks(doc, spec)

    intro_entry = blocks[1]
    sub_entry = blocks[2]
    assert isinstance(intro_entry, ParagraphBlock)
    assert isinstance(sub_entry, ParagraphBlock)
    assert intro_entry.paragraph_style_ref == "TOC Lvl1"
    assert sub_entry.paragraph_style_ref == "TOC Lvl2"


def test_entry_default_style_is_toc_level_n() -> None:
    doc = _build_document()
    blocks = generate_toc_blocks(doc, TocSpec(levels=(1, 2)))
    intro_entry = blocks[1]
    sub_entry = blocks[2]
    assert isinstance(intro_entry, ParagraphBlock)
    assert isinstance(sub_entry, ParagraphBlock)
    assert intro_entry.paragraph_style_ref == "TOC 1"
    assert sub_entry.paragraph_style_ref == "TOC 2"


def test_entry_runs_include_text_tab_leader_and_pageref() -> None:
    doc = _build_document()
    blocks = generate_toc_blocks(doc, TocSpec(levels=(1, 2), tab_leader="."))
    intro = blocks[1]
    assert isinstance(intro, ParagraphBlock)
    assert len(intro.runs) == 3

    text_run, leader_run, page_run = intro.runs
    assert isinstance(text_run, Run)
    assert text_run.text == "Intro"

    assert isinstance(leader_run, Run)
    assert leader_run.text == "."
    assert leader_run.marks.get("role") == "tab-leader"

    assert isinstance(page_run, PageRefRun)
    assert page_run.target_block_id == "h-intro"
    assert page_run.text == "?"


def test_update_toc_replaces_in_place_and_is_idempotent() -> None:
    doc = _build_document()
    cmd1 = update_toc(doc, "toc", TocSpec(levels=(1, 2)))
    assert isinstance(cmd1, UpdateTocCommand)

    toc_story = doc.get_story("toc")
    first_block_ids = [getattr(b, "id", None) for b in toc_story.blocks]
    assert _heading_texts(toc_story.blocks) == ["Intro", "Sub", "Methods", "Results"]

    # Re-run with no doc changes → exact same content.
    update_toc(doc, "toc", TocSpec(levels=(1, 2)))
    assert [getattr(b, "id", None) for b in toc_story.blocks] == first_block_ids
    assert _heading_texts(toc_story.blocks) == ["Intro", "Sub", "Methods", "Results"]

    # Undo restores the previous (most recent prior) blocks.
    cmd2 = doc.undo_stack.commands[-1]
    cmd2.undo(doc)
    assert _heading_texts(toc_story.blocks) == ["Intro", "Sub", "Methods", "Results"]


def test_update_toc_pushes_command_onto_undo_stack() -> None:
    doc = _build_document()
    assert doc.undo_stack.commands == []
    update_toc(doc, "toc", TocSpec(levels=(1,)))
    assert len(doc.undo_stack.commands) == 1
    assert isinstance(doc.undo_stack.commands[0], UpdateTocCommand)


def test_update_toc_reflects_heading_mutations() -> None:
    doc = _build_document()
    update_toc(doc, "toc", TocSpec(levels=(1, 2)))

    # Mutate: rename Methods, drop Sub by retitling story1 H2 to a P (just remove it).
    story1 = doc.get_story("s1")
    story1.blocks = [b for b in story1.blocks if getattr(b, "id", None) != "h-sub"]
    story2 = doc.get_story("s2")
    methods = story2.blocks[0]
    assert isinstance(methods, HeadingBlock)
    methods.runs = [Run(text="Methodology")]

    update_toc(doc, "toc", TocSpec(levels=(1, 2)))
    toc_story = doc.get_story("toc")
    assert _heading_texts(toc_story.blocks) == ["Intro", "Methodology", "Results"]


def test_resolve_page_refs_with_dict_lookup() -> None:
    doc = _build_document()
    update_toc(doc, "toc", TocSpec(levels=(1, 2)))
    resolve_page_refs(
        doc,
        "toc",
        {"h-intro": 1, "h-sub": 1, "h-methods": 4, "h-results": 7},
    )
    toc_story = doc.get_story("toc")
    pages = [
        run.text
        for block in toc_story.blocks
        if isinstance(block, ParagraphBlock)
        for run in block.runs
        if isinstance(run, PageRefRun)
    ]
    assert pages == ["1", "1", "4", "7"]


def test_resolve_page_refs_with_callable_and_unknown_target() -> None:
    doc = _build_document()
    update_toc(doc, "toc", TocSpec(levels=(1,)))
    pages_map = {"h-intro": 2, "h-results": 9}
    resolve_page_refs(doc, "toc", lambda bid: pages_map.get(bid))
    toc_story = doc.get_story("toc")
    rendered = [
        run.text
        for block in toc_story.blocks
        if isinstance(block, ParagraphBlock)
        for run in block.runs
        if isinstance(run, PageRefRun)
    ]
    # Methods has no page mapping → keeps the "?" placeholder.
    assert rendered == ["2", "?", "9"]


def test_toc_skips_blocks_in_the_toc_story_itself() -> None:
    doc = _build_document()
    # Pre-seed the TOC story with a fake heading to confirm it's filtered out.
    toc_story = doc.get_story("toc")
    toc_story.blocks = [HeadingBlock(id="leftover", level=1, runs=[Run(text="STALE")])]

    blocks = generate_toc_blocks(doc, TocSpec(levels=(1, 2)))
    assert "STALE" not in _heading_texts(blocks)


def test_auto_updater_runs_on_heading_changed() -> None:
    doc = _build_document()
    updater = TocAutoUpdater(document=doc, toc_story_id="toc", spec=TocSpec(levels=(1,)))
    updater.install()

    # No timer scheduler → fires synchronously.
    story1 = doc.get_story("s1")
    intro = story1.blocks[0]
    assert isinstance(intro, HeadingBlock)
    intro.runs = [Run(text="Introduction")]
    doc.emit_heading_changed()

    toc_story = doc.get_story("toc")
    assert _heading_texts(toc_story.blocks) == ["Introduction", "Methods", "Results"]


def test_auto_updater_debounces_via_scheduler() -> None:
    doc = _build_document()
    pending: list[tuple] = []

    def fake_schedule(fn, ms):  # type: ignore[no-untyped-def]
        pending.append((fn, ms))

    updater = TocAutoUpdater(
        document=doc,
        toc_story_id="toc",
        spec=TocSpec(levels=(1,)),
        debounce_ms=500,
        schedule=fake_schedule,
    )
    updater.install()

    # Three rapid signals → only one scheduled callback.
    doc.emit_heading_changed()
    doc.emit_heading_changed()
    doc.emit_heading_changed()
    assert len(pending) == 1
    assert pending[0][1] == 500

    # Fire the timer.
    fn, _ = pending[0]
    fn()
    toc_story = doc.get_story("toc")
    assert _heading_texts(toc_story.blocks) == ["Intro", "Methods", "Results"]


def test_auto_updater_falls_back_to_on_changed_with_hash_diff() -> None:
    """If on_heading_changed isn't supported, hash-based on_changed kicks in."""

    doc = _build_document()

    class HashOnlyUpdater(TocAutoUpdater):
        def _heading_signal_supported(self) -> bool:
            return False

    updater = HashOnlyUpdater(
        document=doc, toc_story_id="toc", spec=TocSpec(levels=(1,))
    )
    updater.install()

    # No heading change → no work done.
    doc.emit_changed()
    toc_story = doc.get_story("toc")
    assert toc_story.blocks == []  # no update_toc has run

    # Mutate a heading then emit on_changed → updater detects the diff.
    story2 = doc.get_story("s2")
    methods = story2.blocks[0]
    assert isinstance(methods, HeadingBlock)
    methods.runs = [Run(text="Method")]
    doc.emit_changed()
    assert _heading_texts(toc_story.blocks) == ["Intro", "Method", "Results"]
