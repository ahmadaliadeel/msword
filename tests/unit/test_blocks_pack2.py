"""Unit-7 block tests: ImageBlock + TableBlock.

Covers serialization round-trip (including nested ParagraphBlocks via the
unit-5 stub), ``iter_paragraphs`` row-major walk, and BlockRegistry registration.
"""

from __future__ import annotations

from msword.model.block import Block, BlockRegistry, ParagraphSpec
from msword.model.blocks import (
    BlockCell,
    BlockCol,
    BlockRow,
    ImageBlock,
    ParagraphBlock,
    TableBlock,
)
from msword.model.run import Run


def _roundtrip(block: Block) -> Block:
    return BlockRegistry.resolve(block.to_dict())


def test_block_kinds_registered() -> None:
    registered = set(BlockRegistry.kinds())
    for kind in ("image", "table-block"):
        assert kind in registered


# ---------- ImageBlock ----------


def test_image_block_minimum_roundtrip() -> None:
    block = ImageBlock(id="img1", asset_ref="abc123")
    rt = _roundtrip(block)
    assert isinstance(rt, ImageBlock)
    assert rt == block


def test_image_block_full_roundtrip() -> None:
    block = ImageBlock(
        id="img2",
        asset_ref="def456",
        caption="Figure 1: a caption",
        layout="full-width",
        alt_text="A descriptive alt text",
    )
    rt = _roundtrip(block)
    assert isinstance(rt, ImageBlock)
    assert rt == block


def test_image_block_iter_paragraphs_yields_nothing() -> None:
    block = ImageBlock(id="img3", asset_ref="x", caption="cap", alt_text="alt")
    assert list(block.iter_paragraphs()) == []


def test_image_block_layout_values() -> None:
    for layout in ("inline", "float-left", "float-right", "full-width"):
        block = ImageBlock(id=f"img-{layout}", asset_ref="a", layout=layout)  # type: ignore[arg-type]
        rt = _roundtrip(block)
        assert isinstance(rt, ImageBlock)
        assert rt.layout == layout


# ---------- TableBlock ----------


def _para(pid: str, text: str) -> ParagraphBlock:
    return ParagraphBlock(id=pid, runs=[Run(text=text)])


def _build_2x2() -> TableBlock:
    return TableBlock(
        id="tb1",
        rows=[BlockRow(height_pt=20.0, is_header=True), BlockRow(height_pt=18.0)],
        cols=[BlockCol(width_pt=100.0), BlockCol(width_pt=120.0)],
        cells={
            (0, 0): BlockCell(blocks=[_para("p00", "hello")]),
            (0, 1): BlockCell(blocks=[_para("p01", "world")]),
            (1, 0): BlockCell(blocks=[_para("p10", "foo")]),
            (1, 1): BlockCell(blocks=[_para("p11", "bar")], vertical_align="center"),
        },
    )


def test_table_block_roundtrip_with_nested_paragraphs() -> None:
    block = _build_2x2()
    rt = _roundtrip(block)
    assert isinstance(rt, TableBlock)
    assert rt.id == block.id
    assert rt.rows == block.rows
    assert rt.cols == block.cols
    assert sorted(rt.cells.keys()) == sorted(block.cells.keys())
    for key, cell in block.cells.items():
        rt_cell = rt.cells[key]
        assert rt_cell.rowspan == cell.rowspan
        assert rt_cell.colspan == cell.colspan
        assert rt_cell.vertical_align == cell.vertical_align
        assert len(rt_cell.blocks) == len(cell.blocks)
        for rt_b, src_b in zip(rt_cell.blocks, cell.blocks, strict=True):
            assert isinstance(rt_b, ParagraphBlock)
            assert isinstance(src_b, ParagraphBlock)
            assert rt_b.id == src_b.id
            assert [r.text for r in rt_b.runs] == [r.text for r in src_b.runs]


def test_table_block_iter_paragraphs_row_major() -> None:
    block = _build_2x2()
    specs = list(block.iter_paragraphs())
    assert all(isinstance(s, ParagraphSpec) for s in specs)
    assert [s.runs[0].text for s in specs] == ["hello", "world", "foo", "bar"]


def test_table_block_iter_paragraphs_skips_missing_cells() -> None:
    block = TableBlock(
        id="tb-sparse",
        rows=[BlockRow(), BlockRow()],
        cols=[BlockCol(), BlockCol()],
        cells={
            (0, 0): BlockCell(blocks=[_para("a", "A")]),
            (1, 1): BlockCell(blocks=[_para("b", "B")]),
        },
    )
    assert [s.runs[0].text for s in block.iter_paragraphs()] == ["A", "B"]


def test_table_block_iter_paragraphs_walks_nested_blocks_in_order() -> None:
    block = TableBlock(
        id="tb-multi",
        rows=[BlockRow()],
        cols=[BlockCol()],
        cells={
            (0, 0): BlockCell(
                blocks=[_para("p1", "first"), _para("p2", "second"), _para("p3", "third")],
            ),
        },
    )
    assert [s.runs[0].text for s in block.iter_paragraphs()] == ["first", "second", "third"]


def test_table_block_empty_roundtrip() -> None:
    block = TableBlock(id="tb-empty")
    rt = _roundtrip(block)
    assert isinstance(rt, TableBlock)
    assert rt == block


def test_image_block_inside_table_cell_roundtrip() -> None:
    block = TableBlock(
        id="tb-image",
        rows=[BlockRow()],
        cols=[BlockCol()],
        cells={
            (0, 0): BlockCell(blocks=[ImageBlock(id="img-in-cell", asset_ref="hash")]),
        },
    )
    rt = _roundtrip(block)
    assert isinstance(rt, TableBlock)
    inner = rt.cells[(0, 0)].blocks[0]
    assert isinstance(inner, ImageBlock)
    assert inner.id == "img-in-cell"
    assert inner.asset_ref == "hash"
