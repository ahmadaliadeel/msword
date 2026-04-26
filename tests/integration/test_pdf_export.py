"""Integration tests for ``msword.render.pdf`` (unit #17).

Builds a master-model document with one of each frame type (text, image,
shape), exports it via ``export_pdf``, then re-opens the result with
``pikepdf`` and asserts:

* the PDF has exactly one page,
* a text-showing operator is present (i.e. text stayed *text*, not a
  flattened raster),
* at least one image XObject is embedded.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pikepdf
import pytest

from msword.model.blocks import ParagraphBlock
from msword.model.document import Document
from msword.model.frame import Fill, ImageFrame, ShapeFrame, Stroke, TextFrame
from msword.model.page import Page
from msword.model.run import Run
from msword.model.story import Story
from msword.render.pdf import PdfOptions, export_pdf


def _make_png(width: int = 100, height: int = 100) -> bytes:
    """Hand-roll a tiny solid-color PNG so the test has no Pillow runtime dep."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    raw = b""
    for _ in range(height):
        raw += b"\x00" + (b"\x80\x40\x20" * width)  # filter byte + RGB pixels
    idat = zlib.compress(raw, 9)
    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


@pytest.fixture
def sample_doc() -> Document:
    doc = Document()
    page = Page(id="p1", master_id=None, width_pt=595.0, height_pt=842.0)
    doc.add_page(page)

    story = Story(id="s1", language="en-US")
    story.add_block(ParagraphBlock(id="b1", runs=[Run(text="Hello world")]))
    doc.stories.append(story)

    page.frames.append(
        TextFrame(
            id="ft",
            page_id=page.id,
            x_pt=72.0,
            y_pt=72.0,
            w_pt=400.0,
            h_pt=200.0,
            z_order=1,
            story_ref=story.id,
        )
    )
    asset = doc.assets.add(
        data=_make_png(100, 100),
        kind="image",
        mime_type="image/png",
        original_filename="test.png",
    )
    page.frames.append(
        ImageFrame(
            id="fi",
            page_id=page.id,
            x_pt=72.0,
            y_pt=400.0,
            w_pt=200.0,
            h_pt=200.0,
            z_order=2,
            asset_ref=asset.sha256,
        )
    )
    page.frames.append(
        ShapeFrame(
            id="fs",
            page_id=page.id,
            x_pt=350.0,
            y_pt=400.0,
            w_pt=150.0,
            h_pt=100.0,
            z_order=3,
            shape_kind="ellipse",
            stroke=Stroke(color_ref="black", width_pt=2.0),
            fill=Fill(color_ref="lavender"),
        )
    )
    return doc


def test_export_pdf_writes_file(tmp_path: Path, sample_doc: Document, qtbot) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "out.pdf"
    result = export_pdf(sample_doc, out)
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 0


def test_export_pdf_single_page(tmp_path: Path, sample_doc: Document, qtbot) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "out.pdf"
    export_pdf(sample_doc, out)
    with pikepdf.open(out) as pdf:
        assert len(pdf.pages) == 1


def test_export_pdf_text_is_searchable(tmp_path: Path, sample_doc: Document, qtbot) -> None:  # type: ignore[no-untyped-def]
    """Text drawn via ``QPainter.drawText`` must remain text — not raster."""
    out = tmp_path / "out.pdf"
    export_pdf(sample_doc, out)

    with pikepdf.open(out) as pdf:
        page = pdf.pages[0]
        # Concatenate all content streams into one bytes blob.
        contents = page.Contents
        if isinstance(contents, pikepdf.Array):
            stream = b"".join(c.read_bytes() for c in contents)
        else:
            stream = contents.read_bytes()

    # Qt's PDF backend may emit the text via a Tj/TJ operator; the actual
    # codepoints often go through a custom ToUnicode CMap, so the literal
    # "Hello world" string need not appear verbatim in the content stream.
    # The minimum we *can* assert without parsing the full text-extraction
    # pipeline is the presence of a text-showing operator (``Tj``/``TJ``)
    # and a font-resource reference — both signal vector text, not a
    # rasterized image of text.
    assert b"Tj" in stream or b"TJ" in stream, "no text-showing operator found"

    # Re-open and use pikepdf's high-level helper to fetch the page's font
    # resources; presence of /Font asserts vector text layered into the page.
    with pikepdf.open(out) as pdf:
        page = pdf.pages[0]
        resources = page.Resources
        has_font = ("/Font" in resources) or ("Font" in resources)
        assert has_font, "no /Font resource on the page"


def test_export_pdf_embeds_image(tmp_path: Path, sample_doc: Document, qtbot) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "out.pdf"
    export_pdf(sample_doc, out)

    with pikepdf.open(out) as pdf:
        page = pdf.pages[0]
        images = page.images
        assert len(images) >= 1, "expected at least one image XObject"


def test_export_pdf_empty_document_raises(tmp_path: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "out.pdf"
    with pytest.raises(ValueError):
        export_pdf(Document(), out)


def test_export_pdf_page_range(tmp_path: Path, qtbot) -> None:  # type: ignore[no-untyped-def]
    doc = Document()
    for i in range(3):
        page = Page(id=f"p{i}", master_id=None, width_pt=595.0, height_pt=842.0)
        doc.add_page(page)
        story = Story(id=f"s{i}", language="en-US")
        story.add_block(ParagraphBlock(id=f"b{i}", runs=[Run(text=f"Page {i + 1}")]))
        doc.stories.append(story)
        page.frames.append(
            TextFrame(
                id=f"f{i}",
                page_id=page.id,
                x_pt=72.0,
                y_pt=72.0,
                w_pt=400.0,
                h_pt=400.0,
                story_ref=story.id,
            )
        )

    out = tmp_path / "range.pdf"
    export_pdf(doc, out, options=PdfOptions(page_range=(2, 3)))
    with pikepdf.open(out) as pdf:
        assert len(pdf.pages) == 2


def test_pdf_options_defaults() -> None:
    opts = PdfOptions()
    assert opts.color_space == "rgb"
    assert opts.resolution_dpi == 300
    assert opts.include_bleed is False
    assert opts.include_marks is False
    assert opts.page_range is None
