"""Roundtrip and behaviour tests for the four concrete block types."""

from __future__ import annotations

import pytest

from msword.model.block import BlockRegistry, StubRun
from msword.model.blocks import DividerBlock, EmbedBlock, HeadingBlock, ParagraphBlock


def _runs() -> list[StubRun]:
    return [StubRun(text="Hello ", bold=True), StubRun(text="world", italic=True)]


def test_paragraph_roundtrip() -> None:
    block = ParagraphBlock(id="p1", runs=_runs(), paragraph_style_ref="Body")
    restored = BlockRegistry.resolve(block.to_dict())
    assert isinstance(restored, ParagraphBlock)
    assert restored.id == "p1"
    assert restored.paragraph_style_ref == "Body"
    assert [(r.text, r.bold, r.italic) for r in restored.runs] == [
        ("Hello ", True, False),
        ("world", False, True),
    ]


def test_heading_roundtrip() -> None:
    block = HeadingBlock(id="h1", level=2, runs=_runs())
    restored = BlockRegistry.resolve(block.to_dict())
    assert isinstance(restored, HeadingBlock)
    assert restored.id == "h1"
    assert restored.level == 2
    assert len(restored.runs) == 2


def test_divider_roundtrip() -> None:
    block = DividerBlock(id="d1", style="double")
    restored = BlockRegistry.resolve(block.to_dict())
    assert isinstance(restored, DividerBlock)
    assert restored.id == "d1"
    assert restored.style == "double"


def test_embed_roundtrip() -> None:
    block = EmbedBlock(id="e1", embed_kind="iframe", payload={"src": "https://x"})
    restored = BlockRegistry.resolve(block.to_dict())
    assert isinstance(restored, EmbedBlock)
    assert restored.id == "e1"
    assert restored.embed_kind == "iframe"
    assert restored.payload == {"src": "https://x"}


@pytest.mark.parametrize("level", [0, -1, 7, 99])
def test_heading_level_must_be_in_range(level: int) -> None:
    with pytest.raises(ValueError):
        HeadingBlock(id="bad", level=level)


def test_paragraph_iter_yields_one() -> None:
    block = ParagraphBlock(id="p1", runs=_runs(), paragraph_style_ref="Body")
    paragraphs = list(block.iter_paragraphs())
    assert len(paragraphs) == 1
    spec = paragraphs[0]
    assert spec.block_id == "p1"
    assert spec.paragraph_style_ref == "Body"
    assert len(spec.runs) == 2


def test_heading_iter_yields_one() -> None:
    block = HeadingBlock(id="h1", level=1, runs=_runs())
    paragraphs = list(block.iter_paragraphs())
    assert len(paragraphs) == 1
    assert paragraphs[0].block_id == "h1"


def test_divider_iter_yields_none() -> None:
    block = DividerBlock(id="d1")
    assert list(block.iter_paragraphs()) == []


def test_embed_iter_yields_none() -> None:
    block = EmbedBlock(id="e1", embed_kind="iframe")
    assert list(block.iter_paragraphs()) == []


def test_to_dict_contains_kind_and_id() -> None:
    for block in (
        ParagraphBlock(id="p1"),
        HeadingBlock(id="h1", level=3),
        DividerBlock(id="d1"),
        EmbedBlock(id="e1", embed_kind="x"),
    ):
        d = block.to_dict()
        assert d["kind"] == block.kind
        assert d["id"] == block.id
