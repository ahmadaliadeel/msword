"""Unit tests for ``FootnoteBlock`` (unit-32).

Per spec §12 row 32 acceptance:

  * FootnoteBlock roundtrips JSON cleanly.
  * ``iter_paragraphs`` yields nothing in normal flow.
  * ``iter_footnote_paragraphs`` yields the body paragraphs.
"""

from __future__ import annotations

from msword.model.block import BlockRegistry, ParagraphSpec
from msword.model.blocks.footnote import FootnoteBlock
from msword.model.blocks.paragraph import ParagraphBlock
from msword.model.run import Run


def _para_text(spec: ParagraphSpec) -> str:
    return "".join(r.text for r in spec.runs)


def test_footnote_registers_in_block_registry() -> None:
    assert "footnote" in BlockRegistry.kinds()
    rebuilt = BlockRegistry.resolve({"kind": "footnote", "id": "fn-x"})
    assert isinstance(rebuilt, FootnoteBlock)


def test_iter_paragraphs_yields_nothing_in_main_flow() -> None:
    fn = FootnoteBlock(
        id="fn-1",
        body_blocks=[ParagraphBlock(id="p1", runs=[Run(text="See ibid.")])],
    )
    assert list(fn.iter_paragraphs()) == []


def test_iter_footnote_paragraphs_walks_body_blocks() -> None:
    fn = FootnoteBlock(
        id="fn-1",
        body_blocks=[
            ParagraphBlock(id="p1", runs=[Run(text="First note line.")]),
            ParagraphBlock(id="p2", runs=[Run(text="Second note line.")]),
        ],
    )
    out = list(fn.iter_footnote_paragraphs())
    assert [_para_text(p) for p in out] == ["First note line.", "Second note line."]


def test_footnote_roundtrips_through_dict() -> None:
    original = FootnoteBlock(
        id="fn-7",
        body_blocks=[ParagraphBlock(id="p1", runs=[Run(text="hello")])],
        marker="*",
    )
    payload = original.to_dict()
    assert payload["kind"] == "footnote"
    assert payload["id"] == "fn-7"
    assert payload["marker"] == "*"

    rebuilt = BlockRegistry.resolve(payload)
    assert isinstance(rebuilt, FootnoteBlock)
    assert rebuilt.id == "fn-7"
    assert rebuilt.marker == "*"
    assert [_para_text(p) for p in rebuilt.iter_footnote_paragraphs()] == ["hello"]


def test_footnote_marker_default_is_empty_for_auto_numbering() -> None:
    fn = FootnoteBlock(id="fn-1")
    assert fn.marker == ""
    assert fn.body_blocks == []
