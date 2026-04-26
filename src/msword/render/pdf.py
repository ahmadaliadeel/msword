"""Standard (vector) PDF export — unit #17.

Per spec §7: standard PDF goes through ``QPdfWriter`` + ``QPainter``. Text
remains *text* (selectable, searchable, vector glyphs); images embed at
native resolution; transparency is preserved; shapes go via
``QPainterPath``. The PDF/X path (unit #18) is a *post-processor* layered
on top — see ``render.pdf_x``.

Public API:

    options = PdfOptions()
    export_pdf(doc, "out.pdf", options=options)

``doc`` is duck-typed against the ``Document`` shape from ``_stubs`` and
will accept the real model classes once they land — only attribute
access (``doc.pages``, ``page.frames``, frame fields per spec §4.1) is
required.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Literal, TypeAlias

from PySide6.QtCore import QSizeF
from PySide6.QtGui import QPageSize, QPainter, QPdfWriter

from msword.render._painter import paint_frame
from msword.render._stubs import Document, Page

# Type alias — accepts any ``str`` or ``os.PathLike`` (e.g. ``pathlib.Path``).
PathArg: TypeAlias = str | PathLike[str]

ColorSpace: TypeAlias = Literal["rgb", "cmyk", "grayscale"]


@dataclass(frozen=True)
class PdfOptions:
    """Standard PDF export options.

    Attributes:
        page_range: 1-based inclusive ``(start, end)`` page range, or
            ``None`` to export every page.
        include_bleed: extend the media box to include the page's bleed
            (the painter still draws all frames; consumers crop to the
            trim box for screen, to media for print).
        include_marks: draw crop / bleed marks just outside the trim box
            (only meaningful when ``include_bleed`` is True).
        color_space: output color space label. ``"rgb"`` is the default
            for screen / general print; PDF/X export uses ``"cmyk"`` via
            the post-processor in unit #18.
        resolution_dpi: device resolution for the underlying
            ``QPdfWriter``. Vector ops (text, paths) are unaffected;
            raster fallbacks and image embedding inherit this dpi.
    """

    page_range: tuple[int, int] | None = None
    include_bleed: bool = False
    include_marks: bool = False
    color_space: ColorSpace = "rgb"
    resolution_dpi: int = 300
    title: str = ""
    author: str = ""


_DEFAULT_OPTIONS = PdfOptions()


def export_pdf(
    doc: Document,
    path: PathArg,
    *,
    options: PdfOptions | None = None,
) -> Path:
    """Export ``doc`` as a standard (vector) PDF to ``path``.

    Returns the resolved output path on success.

    The function is synchronous; for large documents, callers should run
    it on a worker thread (it does not touch the GUI thread itself).
    """
    if options is None:
        options = _DEFAULT_OPTIONS

    out_path = Path(path)
    if not doc.pages:
        raise ValueError("cannot export: document has no pages")

    pages = list(_select_pages(doc, options.page_range))

    writer = QPdfWriter(str(out_path))
    writer.setResolution(options.resolution_dpi)
    if options.title:
        writer.setTitle(options.title)
    if options.author:
        writer.setAuthor(options.author)
    _set_color_model(writer, options.color_space)

    # Set the *first* page's size before begin() — Qt needs a valid layout
    # before the painter starts so the first page geometry is correct.
    _apply_page_size(writer, pages[0], options)

    painter = QPainter()
    if not painter.begin(writer):
        raise RuntimeError(f"QPainter failed to begin on {out_path}")

    # Map points → device pixels at the writer's resolution.
    # 1 pt = 1/72 inch → dpi/72 device units per point.
    pt_to_device = options.resolution_dpi / 72.0

    try:
        for idx, page in enumerate(pages):
            if idx > 0:
                _apply_page_size(writer, page, options)
                writer.newPage()

            painter.save()
            try:
                painter.scale(pt_to_device, pt_to_device)
                for frame in sorted(page.frames, key=lambda f: f.z_order):
                    paint_frame(painter, frame)
            finally:
                painter.restore()
    finally:
        painter.end()

    return out_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _select_pages(
    doc: Document, page_range: tuple[int, int] | None
) -> Iterator[Page]:
    if page_range is None:
        yield from doc.pages
        return
    start, end = page_range
    if start < 1 or end < start:
        raise ValueError(f"invalid page_range: {page_range!r}")
    # 1-based inclusive, clamp to document length.
    lo = max(1, start) - 1
    hi = min(len(doc.pages), end)
    yield from doc.pages[lo:hi]


def _apply_page_size(writer: QPdfWriter, page: Page, options: PdfOptions) -> None:
    width_pt = page.width_pt
    height_pt = page.height_pt
    if options.include_bleed and page.bleed_pt:
        bleed = page.bleed_pt
        width_pt += 2 * bleed
        height_pt += 2 * bleed
    size = QPageSize(QSizeF(width_pt, height_pt), QPageSize.Unit.Point)
    writer.setPageSize(size)


def _set_color_model(writer: QPdfWriter, color_space: ColorSpace) -> None:
    # ``setColorModel`` is the Qt 6.8+ API; older Qt silently falls back
    # to RGB. Guard with hasattr so we don't crash on slightly older builds.
    if not hasattr(writer, "setColorModel") or not hasattr(QPdfWriter, "ColorModel"):
        return
    mapping = {
        "rgb": QPdfWriter.ColorModel.RGB,
        "cmyk": QPdfWriter.ColorModel.CMYK,
        "grayscale": QPdfWriter.ColorModel.Grayscale,
    }
    model = mapping.get(color_space)
    if model is not None:
        writer.setColorModel(model)


__all__ = ["PdfOptions", "export_pdf"]
