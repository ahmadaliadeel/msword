"""Unit tests for `msword.io.docx_export`.

The model packages (units 2-8) are not landed yet, so we use minimal
duck-typed dataclasses that mirror the spec section 4 shape.
"""

from __future__ import annotations

import io
import struct
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from lxml import etree

from msword.io._ooxml_helpers import MSWORD_RT_NS, R_NS, W_NS
from msword.io.docx_export import export_docx

NS = {"w": W_NS, "r": R_NS, "mw": MSWORD_RT_NS}


# ---------------------------------------------------------------------------
# Tiny in-test model — duck-typed against the spec, no Qt, no model imports.
# ---------------------------------------------------------------------------


@dataclass
class Run:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strike: bool = False
    size: float | None = None


@dataclass
class ParagraphBlock:
    runs: list[Run] = field(default_factory=list)


@dataclass
class HeadingBlock:
    level: int = 1
    runs: list[Run] = field(default_factory=list)


@dataclass
class ListBlock:
    list_kind: str = "bullet"
    items: list[Any] = field(default_factory=list)


@dataclass
class ImageBlock:
    asset_ref: Any = None
    width_emu: int = 5000000
    height_emu: int = 3750000


@dataclass
class TableBlock:
    rows: list[Any] = field(default_factory=list)
    cols: list[Any] = field(default_factory=list)
    cells: list[list[Any]] = field(default_factory=list)


@dataclass
class CalloutBlock:
    callout_kind: str = "info"
    runs: list[Run] = field(default_factory=list)
    blocks: list[Any] = field(default_factory=list)


@dataclass
class EmbedBlock:
    embed_kind: str = "youtube"
    payload: dict[str, Any] = field(default_factory=dict)
    runs: list[Run] = field(default_factory=list)


@dataclass
class Story:
    blocks: list[Any] = field(default_factory=list)


@dataclass
class Document:
    stories: list[Story] = field(default_factory=list)


@dataclass
class ImageAsset:
    """Duck-typed asset with raw bytes + extension."""

    data: bytes
    extension: str = "png"


# ---------------------------------------------------------------------------
# Synthetic PNG (bytes-only — avoids Pillow dep at test time).
# ---------------------------------------------------------------------------


def _tiny_png() -> bytes:
    """Return the bytes of a 1x1 transparent PNG."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
    raw = b"\x00" + b"\x00\x00\x00\x00"  # filter byte + RGBA pixel
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


# ---------------------------------------------------------------------------
# Sample document used by most tests.
# ---------------------------------------------------------------------------


def _sample_document() -> Document:
    return Document(
        stories=[
            Story(
                blocks=[
                    HeadingBlock(level=1, runs=[Run("Title")]),
                    ParagraphBlock(runs=[Run("Hello "), Run("world", bold=True)]),
                    HeadingBlock(level=2, runs=[Run("Subtitle")]),
                    ParagraphBlock(
                        runs=[Run("A second paragraph with "), Run("italics", italic=True)]
                    ),
                    ListBlock(
                        list_kind="bullet",
                        items=[
                            ParagraphBlock(runs=[Run("First bullet")]),
                            ParagraphBlock(runs=[Run("Second bullet")]),
                        ],
                    ),
                    ListBlock(
                        list_kind="ordered",
                        items=[
                            ParagraphBlock(runs=[Run("Step one")]),
                            ParagraphBlock(runs=[Run("Step two")]),
                        ],
                    ),
                    ImageBlock(asset_ref=ImageAsset(data=_tiny_png(), extension="png")),
                    TableBlock(
                        cols=[None, None],
                        cells=[
                            [
                                ParagraphBlock(runs=[Run("a")]),
                                ParagraphBlock(runs=[Run("b")]),
                            ],
                            [
                                ParagraphBlock(runs=[Run("c")]),
                                ParagraphBlock(runs=[Run("d")]),
                            ],
                        ],
                    ),
                    CalloutBlock(callout_kind="info", runs=[Run("Heads up.")]),
                    EmbedBlock(embed_kind="youtube", payload={"id": "abc"}, runs=[Run("video")]),
                ]
            )
        ]
    )


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def exported(tmp_path: Path) -> tuple[zipfile.ZipFile, etree._Element]:
    """Export the sample doc and return (zip, parsed document.xml)."""
    out = tmp_path / "out.docx"
    export_docx(_sample_document(), out)
    zf = zipfile.ZipFile(out)
    doc = etree.fromstring(zf.read("word/document.xml"))
    return zf, doc


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------


def test_zip_contains_required_parts(exported: tuple[zipfile.ZipFile, etree._Element]) -> None:
    zf, _ = exported
    names = set(zf.namelist())
    for required in (
        "[Content_Types].xml",
        "_rels/.rels",
        "word/document.xml",
        "word/styles.xml",
        "word/_rels/document.xml.rels",
    ):
        assert required in names, f"missing required part: {required}"


def test_document_xml_is_valid_xml(exported: tuple[zipfile.ZipFile, etree._Element]) -> None:
    _, doc = exported
    # The root must be `<w:document>` and contain a `<w:body>`.
    assert doc.tag == f"{{{W_NS}}}document"
    bodies = doc.findall("w:body", NS)
    assert len(bodies) == 1


def test_paragraph_count(exported: tuple[zipfile.ZipFile, etree._Element]) -> None:
    _, doc = exported
    paragraphs = doc.findall(".//w:p", NS)
    # 2 headings + 2 plain paragraphs + 4 list-item paragraphs + 1 image paragraph
    # + 4 table-cell paragraphs + 1 callout + 1 embed = 15
    assert len(paragraphs) == 15


def test_heading_styles(exported: tuple[zipfile.ZipFile, etree._Element]) -> None:
    _, doc = exported
    style_vals = [
        s.get(f"{{{W_NS}}}val")
        for s in doc.findall(".//w:p/w:pPr/w:pStyle", NS)
    ]
    assert "Heading1" in style_vals
    assert "Heading2" in style_vals
    assert "ListBullet" in style_vals
    assert "ListNumber" in style_vals
    assert "Callout" in style_vals
    assert "Embed" in style_vals


def test_table_count(exported: tuple[zipfile.ZipFile, etree._Element]) -> None:
    _, doc = exported
    tables = doc.findall(".//w:tbl", NS)
    assert len(tables) == 1
    rows = tables[0].findall(".//w:tr", NS)
    assert len(rows) == 2
    cells = tables[0].findall(".//w:tc", NS)
    assert len(cells) == 4


def test_drawing_count_and_image_part(exported: tuple[zipfile.ZipFile, etree._Element]) -> None:
    zf, doc = exported
    drawings = doc.findall(".//w:drawing", NS)
    assert len(drawings) == 1
    media = [n for n in zf.namelist() if n.startswith("word/media/")]
    assert len(media) == 1
    # Image bytes survive the round-trip.
    assert zf.read(media[0]).startswith(b"\x89PNG")


def test_image_relationship_resolves(exported: tuple[zipfile.ZipFile, etree._Element]) -> None:
    zf, doc = exported
    blip = doc.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip")
    assert blip is not None
    rid = blip.get(f"{{{R_NS}}}embed")
    assert rid and rid.startswith("rId")

    rels_root = etree.fromstring(zf.read("word/_rels/document.xml.rels"))
    rels = {r.get("Id"): r.get("Target") for r in rels_root}
    assert rid in rels
    assert rels[rid].startswith("media/image")


def test_run_marks_round_trip(exported: tuple[zipfile.ZipFile, etree._Element]) -> None:
    _, doc = exported
    bolds = doc.findall(".//w:r/w:rPr/w:b", NS)
    italics = doc.findall(".//w:r/w:rPr/w:i", NS)
    assert len(bolds) >= 1
    assert len(italics) >= 1


def test_callout_and_embed_emit_roundtrip_marker(
    exported: tuple[zipfile.ZipFile, etree._Element],
) -> None:
    _, doc = exported
    markers = doc.findall(f".//{{{MSWORD_RT_NS}}}roundtrip")
    kinds = sorted(m.get("kind") for m in markers)
    assert kinds == ["callout", "embed"]


def test_content_types_lists_image_extension(
    exported: tuple[zipfile.ZipFile, etree._Element],
) -> None:
    zf, _ = exported
    ct = etree.fromstring(zf.read("[Content_Types].xml"))
    extensions = {d.get("Extension") for d in ct if d.get("Extension")}
    assert "png" in extensions


def test_styles_xml_registers_style_ids(
    exported: tuple[zipfile.ZipFile, etree._Element],
) -> None:
    zf, _ = exported
    styles = etree.fromstring(zf.read("word/styles.xml"))
    style_ids = {s.get(f"{{{W_NS}}}styleId") for s in styles.findall("w:style", NS)}
    for required in ("Normal", "Heading1", "Heading2", "ListBullet", "ListNumber",
                     "Callout", "Embed"):
        assert required in style_ids


def test_styles_relationship_present(
    exported: tuple[zipfile.ZipFile, etree._Element],
) -> None:
    zf, _ = exported
    rels = etree.fromstring(zf.read("word/_rels/document.xml.rels"))
    targets = [r.get("Target") for r in rels]
    assert "styles.xml" in targets


def test_section_properties_emitted(exported: tuple[zipfile.ZipFile, etree._Element]) -> None:
    _, doc = exported
    sect = doc.findall(".//w:body/w:sectPr", NS)
    assert len(sect) == 1


def test_empty_document_still_exports(tmp_path: Path) -> None:
    out = tmp_path / "empty.docx"
    export_docx(Document(stories=[Story(blocks=[])]), out)
    with zipfile.ZipFile(out) as zf:
        doc = etree.fromstring(zf.read("word/document.xml"))
    assert doc.findall(".//w:p", NS) == []
    # sectPr must still be present.
    assert doc.findall(".//w:sectPr", NS)


def test_no_stories_does_not_crash(tmp_path: Path) -> None:
    out = tmp_path / "no-stories.docx"
    export_docx(Document(stories=[]), out)
    assert out.exists()
    with zipfile.ZipFile(out) as zf:
        assert "word/document.xml" in zf.namelist()


def test_string_path_accepted(tmp_path: Path) -> None:
    # `path` parameter type per spec is `path` — both str and Path must work.
    out = tmp_path / "string.docx"
    export_docx(_sample_document(), str(out))
    assert out.exists()


def test_text_with_leading_whitespace_preserved(tmp_path: Path) -> None:
    doc = Document(
        stories=[Story(blocks=[ParagraphBlock(runs=[Run("  leading")])])]
    )
    out = tmp_path / "ws.docx"
    export_docx(doc, out)
    with zipfile.ZipFile(out) as zf:
        body = etree.fromstring(zf.read("word/document.xml"))
    t = body.find(".//w:t", NS)
    assert t is not None
    assert t.text == "  leading"
    assert t.get("{http://www.w3.org/XML/1998/namespace}space") == "preserve"


def test_zip_is_valid_zipfile(exported: tuple[zipfile.ZipFile, etree._Element]) -> None:
    zf, _ = exported
    # `testzip` returns the name of the first bad file or None on success.
    assert zf.testzip() is None


def test_export_writes_to_file_under_directory(tmp_path: Path) -> None:
    # Parent directory is created if missing — we shouldn't require callers to
    # mkdir first.
    nested = tmp_path / "deep" / "deeper" / "out.docx"
    export_docx(_sample_document(), nested)
    assert nested.exists()
    # And it really is a valid zip.
    with zipfile.ZipFile(nested) as zf:
        assert "word/document.xml" in zf.namelist()


def test_inner_document_can_round_trip_through_io(tmp_path: Path) -> None:
    # Sanity: the bytes survive read-back via a BytesIO buffer too (no path
    # caching, etc.).
    buf = io.BytesIO()
    out = tmp_path / "bytes.docx"
    export_docx(_sample_document(), out)
    buf.write(out.read_bytes())
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        doc = etree.fromstring(zf.read("word/document.xml"))
    assert doc.findall(".//w:p", NS)
