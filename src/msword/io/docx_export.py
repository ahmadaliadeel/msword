"""Document → DOCX export.

The exporter walks `document.stories[0].blocks` and emits OOXML using
`lxml`. We deliberately do not depend on `python-docx` for writing because
its style-and-numbering opinions get in the way of round-tripping our
richer block types (callouts, embeds) — see spec §8.

Block → OOXML mapping (spec §4.2):

* `ParagraphBlock`         → `<w:p>` with `<w:pStyle w:val="Normal"/>`
* `HeadingBlock(level=N)`  → `<w:p>` with `<w:pStyle w:val="HeadingN"/>`
* `ListBlock`              → one `<w:p>` per item, ListBullet/ListNumber style
* `ImageBlock`             → `<w:p>` containing a DrawingML inline picture
                              (image bytes get a unique part under
                              `word/media/`, plus an `Image` relationship)
* `TableBlock`             → `<w:tbl>` with one `<w:tr>` / `<w:tc>` per cell
* `CalloutBlock`           → styled paragraph (`Callout`) plus a
                              `<mw:roundtrip kind="callout">…</mw:roundtrip>`
                              custom-XML marker carrying the source kind
* `EmbedBlock`             → styled paragraph (`Embed`) plus a
                              `<mw:roundtrip kind="embed">…</mw:roundtrip>` marker

The "richer" features (CalloutBlock/EmbedBlock) are intentionally lossy to
plain Word — the round-trip marker is what lets the import path reconstruct
them. Word ignores unknown XML in the WordprocessingML body, so files stay
valid in third-party readers.

This module does I/O and ZIP packaging. It contains zero Qt imports.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree

from msword.io._ooxml_helpers import (
    A_NS,
    MW,
    PIC,
    PIC_NS,
    WP,
    A,
    R,
    RelTable,
    W,
    content_types_xml,
    make_document_root,
    package_rels_xml,
    serialize_document,
    styles_xml,
)

# Relationship type URIs (constants — kept here, used only by the exporter).
_REL_STYLES = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
_REL_IMAGE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def export_docx(document: Any, path: str | Path) -> None:
    """Write `document` as a `.docx` ZIP at `path`.

    `document` is duck-typed (see spec §4): it must expose `stories`, a list
    where `stories[0]` has a `.blocks` attribute. Blocks are walked via
    `_block_kind()` and dispatched on type name. Unknown block types are
    emitted as empty paragraphs to avoid losing pagination, with a warning
    via the round-trip marker so re-import can flag them.
    """

    path = Path(path)

    state = _ExportState()
    doc_xml = make_document_root()
    body = doc_xml.find(W("body"))
    assert body is not None  # invariant: helper attaches body

    blocks = _root_blocks(document)
    for block in blocks:
        _write_block(body, block, state)

    # Word requires a sectPr at the end of the body. Without it, files open
    # with warnings in some readers.
    _append_section_properties(body)

    # Build relationships (styles is always rId1).
    rels = RelTable()
    rels.add(_REL_STYLES, "styles.xml")
    image_parts: dict[str, bytes] = {}
    image_extensions: set[str] = set()
    for image in state.images:
        rid = rels.add(_REL_IMAGE, f"media/{image.filename}")
        image.rid_holder.set(R("embed"), rid)
        image_parts[f"word/media/{image.filename}"] = image.data
        image_extensions.add(image.extension)

    # Package up the ZIP.
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml(image_extensions))
        zf.writestr("_rels/.rels", package_rels_xml())
        zf.writestr("word/document.xml", serialize_document(doc_xml))
        zf.writestr("word/styles.xml", styles_xml())
        zf.writestr("word/_rels/document.xml.rels", rels.to_xml())
        for name, data in image_parts.items():
            zf.writestr(name, data)


# ---------------------------------------------------------------------------
# Internal export state
# ---------------------------------------------------------------------------


class _PendingImage:
    """An image written to `word/media/` whose relationship id is patched in
    after the relationships table is built."""

    __slots__ = ("data", "extension", "filename", "rid_holder")

    def __init__(self, data: bytes, filename: str, extension: str, rid_holder: etree._Element):
        self.data = data
        self.filename = filename
        self.extension = extension
        self.rid_holder = rid_holder


class _ExportState:
    """Mutable state threaded through the block-walk."""

    def __init__(self) -> None:
        self.images: list[_PendingImage] = []
        self._drawing_id = 0
        self._image_seen: dict[str, str] = {}  # sha256 → filename (de-dupe)

    def next_drawing_id(self) -> int:
        self._drawing_id += 1
        return self._drawing_id

    def register_image(self, data: bytes, hint_ext: str, rid_holder: etree._Element) -> str:
        """Add an image part. Returns the file name within `word/media/`."""
        digest = hashlib.sha256(data).hexdigest()
        ext = hint_ext.lower().lstrip(".") or "png"
        if digest in self._image_seen:
            filename = self._image_seen[digest]
        else:
            filename = f"image{len(self._image_seen) + 1}.{ext}"
            self._image_seen[digest] = filename
        self.images.append(_PendingImage(data, filename, ext, rid_holder))
        return filename


# ---------------------------------------------------------------------------
# Walking the model
# ---------------------------------------------------------------------------


def _root_blocks(document: Any) -> list[Any]:
    """Pull the first story's blocks. Tolerates a missing/empty story."""
    stories = getattr(document, "stories", None) or []
    if not stories:
        return []
    return list(getattr(stories[0], "blocks", None) or [])


def _block_kind(block: Any) -> str:
    """Return a normalized type tag.

    Prefers an explicit `kind` attribute (set by some block constructors),
    falling back to the class name. This keeps us decoupled from any single
    concrete model implementation while still being predictable.
    """
    kind = getattr(block, "kind", None)
    if isinstance(kind, str) and kind:
        return kind
    return type(block).__name__


def _write_block(parent: etree._Element, block: Any, state: _ExportState) -> None:
    kind = _block_kind(block)
    handler = _BLOCK_HANDLERS.get(kind, _write_unknown_block)
    handler(parent, block, state)


# ---------------------------------------------------------------------------
# Block handlers
# ---------------------------------------------------------------------------


def _write_paragraph_block(parent: etree._Element, block: Any, state: _ExportState) -> None:
    p = _make_paragraph(parent, "Normal")
    _write_runs(p, _runs_of(block))


def _write_heading_block(parent: etree._Element, block: Any, state: _ExportState) -> None:
    level = int(getattr(block, "level", 1) or 1)
    level = max(1, min(level, 6))
    p = _make_paragraph(parent, f"Heading{level}")
    _write_runs(p, _runs_of(block))


def _write_list_block(parent: etree._Element, block: Any, state: _ExportState) -> None:
    kind = getattr(block, "kind_value", None) or getattr(block, "list_kind", None) or "bullet"
    style = "ListNumber" if kind == "ordered" else "ListBullet"
    items = getattr(block, "items", None) or []
    for item in items:
        # Each item is a Block (typically a ParagraphBlock per spec). We
        # render its runs into a styled paragraph; sub-blocks beyond the
        # first paragraph are emitted as additional paragraphs to keep
        # information from being silently dropped.
        first, *rest = _flatten_to_paragraphs(item)
        p = _make_paragraph(parent, style)
        _write_runs(p, first)
        for runs in rest:
            extra = _make_paragraph(parent, style)
            _write_runs(extra, runs)


def _write_image_block(parent: etree._Element, block: Any, state: _ExportState) -> None:
    asset = getattr(block, "asset_ref", None) or getattr(block, "asset", None)
    image_data, ext = _resolve_image_bytes(asset)
    if image_data is None:
        # Fall back to a placeholder paragraph so the document still parses.
        p = _make_paragraph(parent, "Caption")
        _add_text_run(p, "[image]")
        return

    p = _make_paragraph(parent, "Normal")
    r = etree.SubElement(p, W("r"))
    drawing = etree.SubElement(r, W("drawing"))

    inline = etree.SubElement(drawing, WP("inline"))
    # Required size attributes (extent + effectExtent).
    cx = int(getattr(block, "width_emu", 0) or 5000000)  # 5,000,000 EMU ≈ 13.9 cm
    cy = int(getattr(block, "height_emu", 0) or 3750000)
    extent = etree.SubElement(inline, WP("extent"))
    extent.set("cx", str(cx))
    extent.set("cy", str(cy))
    eff = etree.SubElement(inline, WP("effectExtent"))
    eff.set("l", "0")
    eff.set("t", "0")
    eff.set("r", "0")
    eff.set("b", "0")

    drawing_id = state.next_drawing_id()
    doc_pr = etree.SubElement(inline, WP("docPr"))
    doc_pr.set("id", str(drawing_id))
    doc_pr.set("name", f"Picture {drawing_id}")

    graphic = etree.SubElement(inline, A("graphic"), nsmap={"a": A_NS})
    graphic_data = etree.SubElement(graphic, A("graphicData"))
    graphic_data.set("uri", PIC_NS)
    pic = etree.SubElement(graphic_data, PIC("pic"), nsmap={"pic": PIC_NS})

    nv_pic_pr = etree.SubElement(pic, PIC("nvPicPr"))
    cnv_pr = etree.SubElement(nv_pic_pr, PIC("cNvPr"))
    cnv_pr.set("id", str(drawing_id))
    cnv_pr.set("name", f"Picture {drawing_id}")
    etree.SubElement(nv_pic_pr, PIC("cNvPicPr"))

    blip_fill = etree.SubElement(pic, PIC("blipFill"))
    blip = etree.SubElement(blip_fill, A("blip"))
    # rid placeholder; real id is patched in once relationships are built.
    state.register_image(image_data, ext, blip)
    etree.SubElement(blip_fill, A("stretch")).append(etree.Element(A("fillRect")))

    sp_pr = etree.SubElement(pic, PIC("spPr"))
    xfrm = etree.SubElement(sp_pr, A("xfrm"))
    off = etree.SubElement(xfrm, A("off"))
    off.set("x", "0")
    off.set("y", "0")
    ext_e = etree.SubElement(xfrm, A("ext"))
    ext_e.set("cx", str(cx))
    ext_e.set("cy", str(cy))
    prst = etree.SubElement(sp_pr, A("prstGeom"))
    prst.set("prst", "rect")
    etree.SubElement(prst, A("avLst"))


def _write_table_block(parent: etree._Element, block: Any, state: _ExportState) -> None:
    tbl = etree.SubElement(parent, W("tbl"))

    # Minimal table properties — Word wants at least a tblW.
    tbl_pr = etree.SubElement(tbl, W("tblPr"))
    tbl_w = etree.SubElement(tbl_pr, W("tblW"))
    tbl_w.set(W("w"), "0")
    tbl_w.set(W("type"), "auto")

    cells = getattr(block, "cells", None) or []
    cols = getattr(block, "cols", None)
    n_cols = len(cols) if cols else (max((len(row) for row in cells), default=1))
    grid = etree.SubElement(tbl, W("tblGrid"))
    for _ in range(n_cols):
        etree.SubElement(grid, W("gridCol"))

    for row in cells:
        tr = etree.SubElement(tbl, W("tr"))
        # Pad short rows so the table has a consistent column count.
        row_cells = list(row) + [None] * max(0, n_cols - len(row))
        for cell in row_cells[:n_cols]:
            tc = etree.SubElement(tr, W("tc"))
            tc_pr = etree.SubElement(tc, W("tcPr"))
            tc_w = etree.SubElement(tc_pr, W("tcW"))
            tc_w.set(W("w"), "0")
            tc_w.set(W("type"), "auto")
            sub_blocks = _cell_blocks(cell)
            for sub in sub_blocks:
                _write_block(tc, sub, state)
            # Word requires every w:tc to end with a paragraph.
            if not sub_blocks:
                _make_paragraph(tc, "Normal")


def _write_callout_block(parent: etree._Element, block: Any, state: _ExportState) -> None:
    _write_roundtrip_block(parent, block, state, kind="callout", style="Callout")


def _write_embed_block(parent: etree._Element, block: Any, state: _ExportState) -> None:
    _write_roundtrip_block(parent, block, state, kind="embed", style="Embed")


def _write_divider_block(parent: etree._Element, block: Any, state: _ExportState) -> None:
    # Empty styled paragraph; renders as a Word divider via paragraph border
    # in real styles, but the marker is enough for round-tripping.
    p = _make_paragraph(parent, "Normal")
    p_pr = p.find(W("pPr"))
    assert p_pr is not None
    p_bdr = etree.SubElement(p_pr, W("pBdr"))
    bottom = etree.SubElement(p_bdr, W("bottom"))
    bottom.set(W("val"), "single")
    bottom.set(W("sz"), "6")
    bottom.set(W("space"), "1")
    bottom.set(W("color"), "auto")


def _write_quote_block(parent: etree._Element, block: Any, state: _ExportState) -> None:
    sub_blocks = getattr(block, "blocks", None) or []
    if sub_blocks:
        for sub in sub_blocks:
            # Every quoted child paragraph gets the Quote style, regardless of
            # its own style (Word convention).
            kind = _block_kind(sub)
            if kind in {"ParagraphBlock", "HeadingBlock"}:
                p = _make_paragraph(parent, "Quote")
                _write_runs(p, _runs_of(sub))
            else:
                _write_block(parent, sub, state)
    else:
        # A bare quote with inline runs (some implementations).
        p = _make_paragraph(parent, "Quote")
        _write_runs(p, _runs_of(block))


def _write_code_block(parent: etree._Element, block: Any, state: _ExportState) -> None:
    text = getattr(block, "text", None) or ""
    for line in text.splitlines() or [""]:
        p = _make_paragraph(parent, "Code")
        _add_text_run(p, line)


def _write_unknown_block(parent: etree._Element, block: Any, state: _ExportState) -> None:
    # Preserve as an Embed round-trip marker so re-import can flag the
    # unknown block instead of silently dropping it.
    _write_roundtrip_block(parent, block, state, kind="embed", style="Embed")


_BLOCK_HANDLERS = {
    "ParagraphBlock": _write_paragraph_block,
    "HeadingBlock": _write_heading_block,
    "ListBlock": _write_list_block,
    "ImageBlock": _write_image_block,
    "TableBlock": _write_table_block,
    "CalloutBlock": _write_callout_block,
    "EmbedBlock": _write_embed_block,
    "DividerBlock": _write_divider_block,
    "QuoteBlock": _write_quote_block,
    "CodeBlock": _write_code_block,
}


# ---------------------------------------------------------------------------
# Round-trip marker
# ---------------------------------------------------------------------------


def _write_roundtrip_block(
    parent: etree._Element,
    block: Any,
    state: _ExportState,
    *,
    kind: str,
    style: str,
) -> None:
    p = _make_paragraph(parent, style)

    # Inline marker: a serialized JSON payload of the block, embedded in a
    # custom-namespaced element. Word's spec says unknown elements in the body
    # are ignored; on import we look for `{mw}roundtrip` siblings of <w:p>.
    marker = etree.SubElement(parent, MW("roundtrip"))
    marker.set("kind", kind)
    marker.set("source", _block_kind(block))
    marker.text = _serialize_block_payload(block)

    # Visible content — runs from the block (or from its children, if present)
    runs = _runs_of(block)
    if not runs:
        for sub in getattr(block, "blocks", None) or []:
            runs.extend(_runs_of(sub))
    if runs:
        _write_runs(p, runs)
    else:
        _add_text_run(p, getattr(block, "text", None) or f"[{kind}]")


def _serialize_block_payload(block: Any) -> str:
    """Serialize a block to JSON. Falls back to repr if the block isn't JSON-able.

    The exporter shouldn't fail an export over an unserializable block — the
    marker's job is best-effort round-trip evidence, not authoritative state.
    """
    try:
        if hasattr(block, "to_json") and callable(block.to_json):
            return json.dumps(block.to_json(), ensure_ascii=False, sort_keys=True)
        if hasattr(block, "__dict__"):
            return json.dumps(_safe_dict(block.__dict__), ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        pass
    return repr(block)


def _safe_dict(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if k.startswith("_"):
            continue
        try:
            json.dumps(v)
        except (TypeError, ValueError):
            v = repr(v)
        out[k] = v
    return out


# ---------------------------------------------------------------------------
# Paragraph + run primitives
# ---------------------------------------------------------------------------


def _make_paragraph(parent: etree._Element, style_id: str) -> etree._Element:
    p = etree.SubElement(parent, W("p"))
    p_pr = etree.SubElement(p, W("pPr"))
    p_style = etree.SubElement(p_pr, W("pStyle"))
    p_style.set(W("val"), style_id)
    return p


def _runs_of(block: Any) -> list[Any]:
    return list(getattr(block, "runs", None) or [])


def _write_runs(p: etree._Element, runs: list[Any]) -> None:
    for run in runs:
        _add_run(p, run)


def _add_run(p: etree._Element, run: Any) -> None:
    text = getattr(run, "text", None)
    if text is None:
        # Allow strings as runs for tests / simple callers.
        text = str(run)

    r = etree.SubElement(p, W("r"))

    # Run properties — only emit ones that are actually set.
    marks: dict[str, Any] = {
        "bold": getattr(run, "bold", False),
        "italic": getattr(run, "italic", False),
        "underline": getattr(run, "underline", False),
        "strike": getattr(run, "strike", False),
    }
    if any(marks.values()) or getattr(run, "size", None):
        r_pr = etree.SubElement(r, W("rPr"))
        if marks["bold"]:
            etree.SubElement(r_pr, W("b"))
        if marks["italic"]:
            etree.SubElement(r_pr, W("i"))
        if marks["underline"]:
            u = etree.SubElement(r_pr, W("u"))
            u.set(W("val"), "single")
        if marks["strike"]:
            etree.SubElement(r_pr, W("strike"))
        size = getattr(run, "size", None)
        if size:
            sz = etree.SubElement(r_pr, W("sz"))
            # Word uses half-points.
            sz.set(W("val"), str(round(float(size) * 2)))

    t = etree.SubElement(r, W("t"))
    # Preserve leading/trailing whitespace — required for text like "  foo".
    t.set(qn_xml("space"), "preserve")
    t.text = text


def _add_text_run(p: etree._Element, text: str) -> None:
    r = etree.SubElement(p, W("r"))
    t = etree.SubElement(r, W("t"))
    t.set(qn_xml("space"), "preserve")
    t.text = text


def qn_xml(tag: str) -> str:
    return f"{{http://www.w3.org/XML/1998/namespace}}{tag}"


# ---------------------------------------------------------------------------
# Helpers — table cells, image bytes, paragraphs from a list item
# ---------------------------------------------------------------------------


def _cell_blocks(cell: Any) -> list[Any]:
    if cell is None:
        return []
    # A cell may be a Block, a list of Blocks, or have a `.blocks` attribute.
    if isinstance(cell, list):
        return list(cell)
    inner = getattr(cell, "blocks", None)
    if inner is not None:
        return list(inner)
    return [cell]


def _flatten_to_paragraphs(item: Any) -> list[list[Any]]:
    """Return a list of run-lists: one per paragraph the list item contains."""
    if item is None:
        return [[]]
    runs = _runs_of(item)
    if runs:
        return [runs]
    sub = getattr(item, "blocks", None) or []
    if not sub:
        return [[]]
    return [_runs_of(s) for s in sub]


def _resolve_image_bytes(asset: Any) -> tuple[bytes | None, str]:
    """Pull raw bytes + extension from an asset reference.

    Supports several shapes (concrete vs duck-typed) so we don't lock into
    the asset model of any particular sibling unit:

    * bytes-like → treat as raw image data, extension defaults to "png"
    * `.data` + `.extension` → use those
    * `.path` (or `.filename`) → read from disk; extension comes from suffix
    """
    if asset is None:
        return None, "png"
    if isinstance(asset, (bytes, bytearray, memoryview)):
        return bytes(asset), "png"
    data = getattr(asset, "data", None)
    if data is not None:
        name = getattr(asset, "filename", "") or getattr(asset, "name", "")
        ext = (
            getattr(asset, "extension", None)
            or getattr(asset, "ext", None)
            or Path(name).suffix
            or "png"
        )
        return bytes(data), ext.lstrip(".").lower()
    path = getattr(asset, "path", None) or getattr(asset, "filename", None)
    if path:
        p = Path(path)
        if p.exists():
            return p.read_bytes(), p.suffix.lstrip(".").lower() or "png"
    return None, "png"


def _append_section_properties(body: etree._Element) -> None:
    """Append the trailing `<w:sectPr>` Word expects in every body."""
    sect_pr = etree.SubElement(body, W("sectPr"))
    pg_sz = etree.SubElement(sect_pr, W("pgSz"))
    # A4 in twentieths of a point: 11906 by 16838.
    pg_sz.set(W("w"), "11906")
    pg_sz.set(W("h"), "16838")
    pg_mar = etree.SubElement(sect_pr, W("pgMar"))
    for side, val in (("top", "1440"), ("right", "1440"), ("bottom", "1440"), ("left", "1440")):
        pg_mar.set(W(side), val)


__all__ = ["export_docx"]
