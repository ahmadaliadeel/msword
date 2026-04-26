"""Integration tests for PDF/X export (unit-18).

Covers the X-1a and X-4 paths through :func:`msword.render.pdf_x.export_pdf_x`
with a stub document. Real document model lands in unit-2 onward; we use a
trivial duck-typed stub here so this unit is independently testable.
"""

from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

import pikepdf
import pytest

from msword.render._icc_profiles import (
    cmyk_fogra39_profile,
    srgb_profile,
)
from msword.render.pdf_x import (
    PdfXError,
    PdfXFontEmbeddingError,
    PdfXProfile,
    PdfXTransparencyError,
    export_pdf_x,
)


def _stub_doc(num_pages: int = 1) -> SimpleNamespace:
    return SimpleNamespace(pages=[SimpleNamespace(index=i) for i in range(num_pages)])


# --------------------------------------------------------------------------- #
# Profile enum
# --------------------------------------------------------------------------- #


def test_profile_enum_values() -> None:
    assert {p.name for p in PdfXProfile} == {"X1A", "X3", "X4"}


def test_profile_x3_raises_not_implemented(tmp_path: Path) -> None:
    out = tmp_path / "out.pdf"
    with pytest.raises(NotImplementedError):
        export_pdf_x(_stub_doc(), out, profile=PdfXProfile.X3)


# --------------------------------------------------------------------------- #
# ICC profile helpers
# --------------------------------------------------------------------------- #


def test_srgb_profile_is_valid_icc() -> None:
    data = srgb_profile()
    assert len(data) >= 128
    assert data[36:40] == b"acsp"
    assert data[16:20] == b"RGB "


def test_cmyk_fallback_profile_is_valid_icc() -> None:
    data = cmyk_fogra39_profile()
    assert len(data) >= 128
    assert data[36:40] == b"acsp"
    assert data[16:20] == b"CMYK"
    assert data[12:16] == b"prtr"  # output device class


def test_cmyk_profile_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    custom = b"X" * 256
    icc_file = tmp_path / "custom.icc"
    icc_file.write_bytes(custom)
    monkeypatch.setenv("MSWORD_CMYK_ICC_PATH", str(icc_file))
    assert cmyk_fogra39_profile() == custom


# --------------------------------------------------------------------------- #
# X-4 export — primary spec path
# --------------------------------------------------------------------------- #


def test_export_x4_writes_output_intent_and_boxes(tmp_path: Path) -> None:
    out = tmp_path / "x4.pdf"
    result = export_pdf_x(_stub_doc(2), out, profile=PdfXProfile.X4)

    assert result == out
    assert out.is_file()
    assert out.read_bytes()[:5] == b"%PDF-"

    with pikepdf.open(out) as pdf:
        # /OutputIntents exists and is non-empty
        intents = pdf.Root.get("/OutputIntents")
        assert intents is not None
        assert len(intents) >= 1
        intent = intents[0]
        assert intent.get("/S") == pikepdf.Name("/GTS_PDFX")
        assert intent.get("/DestOutputProfile") is not None

        # docinfo carries /GTS_PDFXVersion
        assert pdf.docinfo is not None
        assert pdf.docinfo.get("/GTS_PDFXVersion") is not None

        # Each page has /MediaBox != /TrimBox, plus a /BleedBox
        for page in pdf.pages:
            media = page.obj.get("/MediaBox")
            trim = page.obj.get("/TrimBox")
            bleed = page.obj.get("/BleedBox")
            assert media is not None
            assert trim is not None
            assert bleed is not None
            media_vals = [float(v) for v in media]
            trim_vals = [float(v) for v in trim]
            assert media_vals != trim_vals


def test_export_x4_atomic_no_tmp_left_behind(tmp_path: Path) -> None:
    out = tmp_path / "atomic.pdf"
    export_pdf_x(_stub_doc(), out, profile=PdfXProfile.X4)
    leftover = list(tmp_path.glob("*.tmp"))
    assert leftover == []


def test_export_x4_accepts_custom_icc(tmp_path: Path) -> None:
    custom_icc = cmyk_fogra39_profile()
    out = tmp_path / "x4_custom_icc.pdf"
    export_pdf_x(
        _stub_doc(),
        out,
        profile=PdfXProfile.X4,
        output_intent_icc=custom_icc,
    )
    with pikepdf.open(out) as pdf:
        intent = pdf.Root["/OutputIntents"][0]
        icc_stream = intent["/DestOutputProfile"]
        assert icc_stream["/N"] == 4


# --------------------------------------------------------------------------- #
# X-1a export
# --------------------------------------------------------------------------- #


def test_export_x1a_succeeds_on_opaque_doc(tmp_path: Path) -> None:
    out = tmp_path / "x1a.pdf"
    export_pdf_x(_stub_doc(), out, profile=PdfXProfile.X1A)
    with pikepdf.open(out) as pdf:
        assert pdf.docinfo is not None
        assert pdf.docinfo.get("/GTS_PDFXConformance") is not None
        assert "X-1" in str(pdf.docinfo["/GTS_PDFXVersion"])


def test_export_x1a_raises_on_transparency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When the rendered base PDF contains transparency, X-1a must refuse."""
    from msword.render import pdf_x as pdf_x_mod

    real_export = pdf_x_mod._export_pdf

    def transparent_pdf(_doc: object) -> bytes:
        base_bytes = real_export(_doc)
        with pikepdf.open(io.BytesIO(base_bytes)) as pdf:
            page = pdf.pages[0]
            resources = page.obj.get("/Resources")
            if resources is None:
                page.obj["/Resources"] = pikepdf.Dictionary({})
                resources = page.obj["/Resources"]
            gs = pikepdf.Dictionary(
                {
                    "/Type": pikepdf.Name("/ExtGState"),
                    "/CA": 0.5,
                    "/ca": 0.5,
                }
            )
            resources["/ExtGState"] = pikepdf.Dictionary({"/GS0": gs})
            buf = io.BytesIO()
            pdf.save(buf)
            return buf.getvalue()

    monkeypatch.setattr(pdf_x_mod, "_export_pdf", transparent_pdf)

    out = tmp_path / "x1a_transparent.pdf"
    with pytest.raises(PdfXTransparencyError):
        export_pdf_x(_stub_doc(), out, profile=PdfXProfile.X1A)


def test_export_x1a_converts_rgb_image_to_cmyk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RGB image XObjects in a PDF/X-1a candidate must be converted to CMYK."""
    from PIL import Image

    from msword.render import pdf_x as pdf_x_mod

    real_export = pdf_x_mod._export_pdf

    def pdf_with_rgb_image(_doc: object) -> bytes:
        base_bytes = real_export(_doc)
        with pikepdf.open(io.BytesIO(base_bytes)) as pdf:
            page = pdf.pages[0]
            resources = page.obj.get("/Resources")
            if resources is None:
                page.obj["/Resources"] = pikepdf.Dictionary({})
                resources = page.obj["/Resources"]

            img = Image.new("RGB", (8, 8), color=(255, 64, 32))
            jpeg_buf = io.BytesIO()
            img.save(jpeg_buf, format="JPEG", quality=90)

            stream = pdf.make_stream(jpeg_buf.getvalue())
            stream["/Type"] = pikepdf.Name("/XObject")
            stream["/Subtype"] = pikepdf.Name("/Image")
            stream["/Width"] = 8
            stream["/Height"] = 8
            stream["/ColorSpace"] = pikepdf.Name("/DeviceRGB")
            stream["/BitsPerComponent"] = 8
            stream["/Filter"] = pikepdf.Name("/DCTDecode")

            resources["/XObject"] = pikepdf.Dictionary({"/Im0": stream})
            buf = io.BytesIO()
            pdf.save(buf)
            return buf.getvalue()

    monkeypatch.setattr(pdf_x_mod, "_export_pdf", pdf_with_rgb_image)

    out = tmp_path / "x1a_with_image.pdf"
    export_pdf_x(_stub_doc(), out, profile=PdfXProfile.X1A)

    with pikepdf.open(out) as pdf:
        xobjects = pdf.pages[0].obj["/Resources"]["/XObject"]
        for _name, xo in xobjects.items():
            if xo.get("/Subtype") == pikepdf.Name("/Image"):
                assert xo["/ColorSpace"] == pikepdf.Name("/DeviceCMYK")


# --------------------------------------------------------------------------- #
# Font embedding
# --------------------------------------------------------------------------- #


def test_export_raises_on_unembedded_font(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from msword.render import pdf_x as pdf_x_mod

    real_export = pdf_x_mod._export_pdf

    def pdf_with_unembedded_font(_doc: object) -> bytes:
        base_bytes = real_export(_doc)
        with pikepdf.open(io.BytesIO(base_bytes)) as pdf:
            page = pdf.pages[0]
            resources = page.obj.get("/Resources")
            if resources is None:
                page.obj["/Resources"] = pikepdf.Dictionary({})
                resources = page.obj["/Resources"]
            descriptor = pikepdf.Dictionary(
                {
                    "/Type": pikepdf.Name("/FontDescriptor"),
                    "/FontName": pikepdf.Name("/Helvetica"),
                    # No FontFile / FontFile2 / FontFile3 — this is the bug we detect.
                    "/Flags": 32,
                    "/ItalicAngle": 0,
                    "/Ascent": 718,
                    "/Descent": -207,
                    "/CapHeight": 718,
                    "/StemV": 88,
                }
            )
            font = pikepdf.Dictionary(
                {
                    "/Type": pikepdf.Name("/Font"),
                    "/Subtype": pikepdf.Name("/Type1"),
                    "/BaseFont": pikepdf.Name("/Helvetica"),
                    "/FontDescriptor": descriptor,
                }
            )
            resources["/Font"] = pikepdf.Dictionary({"/F1": font})
            buf = io.BytesIO()
            pdf.save(buf)
            return buf.getvalue()

    monkeypatch.setattr(pdf_x_mod, "_export_pdf", pdf_with_unembedded_font)

    out = tmp_path / "unembedded.pdf"
    with pytest.raises(PdfXFontEmbeddingError):
        export_pdf_x(_stub_doc(), out, profile=PdfXProfile.X4)


def test_pdf_x_errors_share_base() -> None:
    assert issubclass(PdfXFontEmbeddingError, PdfXError)
    assert issubclass(PdfXTransparencyError, PdfXError)
