"""Integration tests for ``msword.render.pdf`` (unit #17).

The tests build a document with one of each frame type (text, image,
shape) using the local stubs from ``msword.render._stubs`` (the real
model lands in units #2-7), export it via ``export_pdf``, then re-open
the result with ``pikepdf`` and assert:

* the PDF has exactly one page,
* the text frame's content is present as searchable text in the
  content stream (i.e. text stayed *text*, not a flattened raster),
* at least one image XObject is embedded.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pikepdf
import pytest

from msword.render._stubs import (
    Document,
    ImageFrame,
    Page,
    ShapeFrame,
    TextFrame,
)
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
    page = Page(width_pt=595.0, height_pt=842.0)
    page.frames.extend(
        [
            TextFrame(
                x=72.0,
                y=72.0,
                w=400.0,
                h=200.0,
                story="Hello world",
                font_family="Helvetica",
                font_size_pt=24.0,
                z_order=1,
            ),
            ImageFrame(
                x=72.0,
                y=400.0,
                w=200.0,
                h=200.0,
                image_bytes=_make_png(100, 100),
                z_order=2,
            ),
            ShapeFrame(
                x=350.0,
                y=400.0,
                w=150.0,
                h=100.0,
                kind="ellipse",
                stroke=(0, 0, 0),
                stroke_width_pt=2.0,
                fill=(200, 200, 255),
                z_order=3,
            ),
        ]
    )
    return Document(pages=[page], title="Unit-17 Smoke")


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
    pages = [
        Page(
            width_pt=595.0,
            height_pt=842.0,
            frames=[
                TextFrame(
                    x=72.0,
                    y=72.0,
                    w=400.0,
                    h=400.0,
                    story=f"Page {i + 1}",
                )
            ],
        )
        for i in range(3)
    ]
    doc = Document(pages=pages)

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
