"""Unit-6 tests: ListBlock, QuoteBlock, CodeBlock, CalloutBlock.

Covers serialization round-trip (including nested blocks), `iter_paragraphs`
contract, and BlockRegistry registration.
"""

from __future__ import annotations

from msword.model.block import Block, BlockRegistry, ParagraphSpec
from msword.model.blocks import (
    CalloutBlock,
    CodeBlock,
    ListBlock,
    ListItem,
    ParagraphBlock,
    QuoteBlock,
)
from msword.model.run import Run


def _roundtrip(block: Block) -> Block:
    return BlockRegistry.resolve(block.to_dict())


def test_all_block_kinds_registered() -> None:
    registered = set(BlockRegistry.kinds())
    for kind in ("list", "quote", "code", "callout", "paragraph"):
        assert kind in registered


# ---------- ListBlock ----------


def test_list_block_bullet_roundtrip() -> None:
    block = ListBlock(
        id="l1",
        list_kind="bullet",
        items=[
            ListItem(id="i1", blocks=[ParagraphBlock(id="p1", runs=[Run(text="alpha")])]),
            ListItem(id="i2", blocks=[ParagraphBlock(id="p2", runs=[Run(text="beta")])]),
        ],
    )
    rt = _roundtrip(block)
    assert isinstance(rt, ListBlock)
    assert rt == block


def test_list_block_ordered_roundtrip() -> None:
    block = ListBlock(id="l", list_kind="ordered", items=[ListItem(id="i")])
    rt = _roundtrip(block)
    assert isinstance(rt, ListBlock)
    assert rt.list_kind == "ordered"


def test_list_block_todo_with_checked_items() -> None:
    def _item(item_id: str, text: str, checked: bool | None) -> ListItem:
        return ListItem(
            id=item_id,
            blocks=[ParagraphBlock(id=f"p-{item_id}", runs=[Run(text=text)])],
            checked=checked,
        )

    block = ListBlock(
        id="l",
        list_kind="todo",
        items=[_item("a", "done", True), _item("b", "todo", False), _item("c", "n/a", None)],
    )
    rt = _roundtrip(block)
    assert isinstance(rt, ListBlock)
    assert rt.list_kind == "todo"
    assert [it.checked for it in rt.items] == [True, False, None]
    assert rt == block


def test_list_block_iter_paragraphs_walks_items_recursively() -> None:
    inner_list = ListBlock(
        id="l2",
        list_kind="bullet",
        items=[ListItem(id="i", blocks=[ParagraphBlock(id="p2", runs=[Run(text="nested")])])],
    )
    outer = ListBlock(
        id="l1",
        list_kind="bullet",
        items=[
            ListItem(id="i1", blocks=[ParagraphBlock(id="p1", runs=[Run(text="outer")])]),
            ListItem(id="i2", blocks=[inner_list]),
        ],
    )
    paragraphs = list(outer.iter_paragraphs())
    assert [p.runs[0].text for p in paragraphs] == ["outer", "nested"]


# ---------- QuoteBlock ----------


def test_quote_block_roundtrip_preserves_nested_paragraph_text() -> None:
    block = QuoteBlock(
        id="q1",
        blocks=[ParagraphBlock(id="p1", runs=[Run(text="to be, or not to be")])],
    )
    rt = _roundtrip(block)
    assert isinstance(rt, QuoteBlock)
    assert rt == block
    nested_paragraph = rt.blocks[0]
    assert isinstance(nested_paragraph, ParagraphBlock)
    assert nested_paragraph.runs[0].text == "to be, or not to be"


def test_quote_block_iter_paragraphs_overrides_style_to_quote() -> None:
    block = QuoteBlock(
        id="q",
        blocks=[
            ParagraphBlock(id="p1", runs=[Run(text="line one")], paragraph_style_ref="Body"),
            ParagraphBlock(id="p2", runs=[Run(text="line two")]),
        ],
    )
    specs = list(block.iter_paragraphs())
    assert len(specs) == 2
    for spec in specs:
        assert isinstance(spec, ParagraphSpec)
        assert spec.paragraph_style_ref == "Quote"


# ---------- CodeBlock ----------


def test_code_block_roundtrip() -> None:
    block = CodeBlock(
        id="c1",
        language="python",
        text="print('hi')",
        theme="monokai",
        show_line_numbers=True,
    )
    rt = _roundtrip(block)
    assert isinstance(rt, CodeBlock)
    assert rt == block


def test_code_block_multiline_yields_one_paragraph_per_line() -> None:
    text = "def f():\n    return 1\n    return 2"
    block = CodeBlock(id="c", language="python", text=text)
    specs = list(block.iter_paragraphs())
    assert len(specs) == 3
    assert [s.runs[0].text for s in specs] == ["def f():", "    return 1", "    return 2"]
    assert all(s.paragraph_style_ref == "Code" for s in specs)
    assert all(s.runs[0].font_ref == "mono" for s in specs)


def test_code_block_empty_text_still_yields_one_paragraph() -> None:
    block = CodeBlock(id="c", text="")
    specs = list(block.iter_paragraphs())
    assert len(specs) == 1
    assert specs[0].runs[0].text == ""


# ---------- CalloutBlock ----------


def test_callout_block_roundtrip_all_kinds() -> None:
    for kind in ("info", "warn", "tip", "danger"):
        block = CalloutBlock(
            id=f"co-{kind}",
            callout_kind=kind,
            blocks=[ParagraphBlock(id="p", runs=[Run(text=f"hello {kind}")])],
        )
        rt = _roundtrip(block)
        assert isinstance(rt, CalloutBlock)
        assert rt == block


def test_callout_block_iter_paragraphs_walks_children_without_label() -> None:
    block = CalloutBlock(
        id="co",
        callout_kind="warn",
        blocks=[
            ParagraphBlock(id="p1", runs=[Run(text="careful")]),
            ParagraphBlock(id="p2", runs=[Run(text="really")]),
        ],
    )
    specs = list(block.iter_paragraphs())
    # Per spec: label is decoration (rendered in unit-16), not a synthetic paragraph.
    assert [s.runs[0].text for s in specs] == ["careful", "really"]


# ---------- nested block-in-block roundtrip across types ----------


def test_quote_inside_callout_inside_list_roundtrip() -> None:
    inner_quote = QuoteBlock(
        id="q",
        blocks=[ParagraphBlock(id="p", runs=[Run(text="quoted line")])],
    )
    callout = CalloutBlock(id="co", callout_kind="tip", blocks=[inner_quote])
    outer = ListBlock(
        id="l",
        list_kind="bullet",
        items=[ListItem(id="i", blocks=[callout])],
    )
    rt = _roundtrip(outer)
    assert rt == outer
    paragraphs = list(rt.iter_paragraphs())
    assert len(paragraphs) == 1
    assert paragraphs[0].runs[0].text == "quoted line"
    assert paragraphs[0].paragraph_style_ref == "Quote"
