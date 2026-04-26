"""Unit-7 TableFrame tests: 3x3 construction, merge/split, roundtrip."""

from __future__ import annotations

import pytest

from msword.model.table_frame import (
    Col,
    Padding,
    Row,
    TableCell,
    TableFrame,
)


def _build_3x3() -> TableFrame:
    cells: dict[tuple[int, int], TableCell] = {}
    for r in range(3):
        for c in range(3):
            cells[(r, c)] = TableCell(block_ids=[f"b-{r}-{c}"])
    return TableFrame(
        id="tf1",
        page_id="p1",
        x_pt=10.0,
        y_pt=20.0,
        w_pt=300.0,
        h_pt=180.0,
        rows=[Row(height_pt=60.0), Row(height_pt=60.0), Row(height_pt=60.0)],
        cols=[Col(width_pt=100.0), Col(width_pt=100.0), Col(width_pt=100.0)],
        cells=cells,
    )


def test_table_frame_kind() -> None:
    assert TableFrame.kind == "table"


def test_table_frame_3x3_cell_at() -> None:
    frame = _build_3x3()
    assert frame.cell_at(0, 0).block_ids == ["b-0-0"]
    assert frame.cell_at(2, 2).block_ids == ["b-2-2"]


def test_cell_at_missing_raises() -> None:
    frame = _build_3x3()
    del frame.cells[(1, 1)]
    with pytest.raises(KeyError):
        frame.cell_at(1, 1)


def test_merge_cells_2x2_top_left() -> None:
    frame = _build_3x3()
    merged = frame.merge_cells(0, 0, 1, 1)
    assert merged.rowspan == 2
    assert merged.colspan == 2
    assert merged.block_ids == ["b-0-0", "b-0-1", "b-1-0", "b-1-1"]
    # merged absorbed cells are gone
    assert (0, 1) not in frame.cells
    assert (1, 0) not in frame.cells
    assert (1, 1) not in frame.cells
    # surviving cells outside rectangle are untouched
    assert frame.cell_at(0, 2).block_ids == ["b-0-2"]
    assert frame.cell_at(2, 2).block_ids == ["b-2-2"]


def test_merge_cells_full_row() -> None:
    frame = _build_3x3()
    merged = frame.merge_cells(0, 0, 0, 2)
    assert merged.rowspan == 1
    assert merged.colspan == 3
    assert merged.block_ids == ["b-0-0", "b-0-1", "b-0-2"]
    assert (0, 1) not in frame.cells
    assert (0, 2) not in frame.cells


def test_merge_out_of_bounds_raises() -> None:
    frame = _build_3x3()
    with pytest.raises(ValueError):
        frame.merge_cells(0, 0, 3, 3)
    with pytest.raises(ValueError):
        frame.merge_cells(2, 0, 1, 0)


def test_split_cell_restores_unit_cells() -> None:
    frame = _build_3x3()
    frame.merge_cells(0, 0, 1, 1)
    frame.split_cell(0, 0)
    anchor = frame.cell_at(0, 0)
    assert anchor.rowspan == 1
    assert anchor.colspan == 1
    # anchor keeps its absorbed block_ids — they're not redistributed
    assert anchor.block_ids == ["b-0-0", "b-0-1", "b-1-0", "b-1-1"]
    # other positions are restored as fresh empty cells
    for pos in [(0, 1), (1, 0), (1, 1)]:
        cell = frame.cell_at(*pos)
        assert cell.rowspan == 1
        assert cell.colspan == 1
        assert cell.block_ids == []


def test_split_unit_cell_is_noop() -> None:
    frame = _build_3x3()
    before = dict(frame.cells)
    frame.split_cell(0, 0)
    assert frame.cells == before


def test_merge_then_remerge_inside_span_raises() -> None:
    frame = _build_3x3()
    frame.merge_cells(0, 0, 1, 1)
    with pytest.raises(ValueError):
        frame.merge_cells(0, 0, 2, 2)


def test_table_frame_roundtrip_3x3() -> None:
    frame = _build_3x3()
    frame.padding = Padding(top=2.0, right=3.0, bottom=4.0, left=5.0)
    frame.cells[(2, 2)].vertical_align = "bottom"
    rt = TableFrame.from_dict(frame.to_dict())
    assert rt.id == frame.id
    assert rt.page_id == frame.page_id
    assert rt.x_pt == frame.x_pt
    assert rt.y_pt == frame.y_pt
    assert rt.w_pt == frame.w_pt
    assert rt.h_pt == frame.h_pt
    assert rt.padding == frame.padding
    assert rt.rows == frame.rows
    assert rt.cols == frame.cols
    assert sorted(rt.cells) == sorted(frame.cells)
    for key, cell in frame.cells.items():
        rt_cell = rt.cells[key]
        assert rt_cell.block_ids == cell.block_ids
        assert rt_cell.rowspan == cell.rowspan
        assert rt_cell.colspan == cell.colspan
        assert rt_cell.vertical_align == cell.vertical_align


def test_table_frame_roundtrip_after_merge() -> None:
    frame = _build_3x3()
    frame.merge_cells(0, 0, 1, 1)
    rt = TableFrame.from_dict(frame.to_dict())
    merged = rt.cell_at(0, 0)
    assert merged.rowspan == 2
    assert merged.colspan == 2
    assert merged.block_ids == ["b-0-0", "b-0-1", "b-1-0", "b-1-1"]
    assert (0, 1) not in rt.cells
    assert (1, 0) not in rt.cells
    assert (1, 1) not in rt.cells


def test_row_is_header_flag() -> None:
    row = Row(height_pt=20.0, is_header=True)
    assert row.is_header is True
    rt = Row.from_dict(row.to_dict())
    assert rt == row
