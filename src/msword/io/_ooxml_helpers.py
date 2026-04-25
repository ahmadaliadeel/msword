"""Low-level OOXML helpers for DOCX export.

Pure I/O / XML helpers — no Qt, no model imports. The exporter walks the
document model and asks this module to produce wire-format pieces:

* namespace constants and qualified names,
* the static fragments shipped in every `.docx` (`[Content_Types].xml`,
  `_rels/.rels`, a minimal `word/styles.xml`),
* the `word/_rels/document.xml.rels` file built from a relationship table.

Keeping these here lets `docx_export.py` stay focused on model→XML
mapping and keeps the byte-fragment templates testable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from lxml import etree

# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------

# WordprocessingML — body XML.
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
# DrawingML — picture/inline frame.
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
# Relationships.
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
# Custom XML — used as the round-trip marker for callouts/embeds.
MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
MSWORD_RT_NS = "urn:msword:roundtrip"

NS_MAP = {
    "w": W_NS,
    "r": R_NS,
    "a": A_NS,
    "pic": PIC_NS,
    "wp": WP_NS,
    "mc": MC_NS,
    "mw": MSWORD_RT_NS,
}


def qn(ns: str, tag: str) -> str:
    """Return Clark-notation qualified name `{ns}tag`."""
    return f"{{{ns}}}{tag}"


def W(tag: str) -> str:
    """Wordprocessing-ML qualified name."""
    return qn(W_NS, tag)


def R(tag: str) -> str:
    """Relationships qualified name."""
    return qn(R_NS, tag)


def WP(tag: str) -> str:
    """DrawingML wordprocessingDrawing qualified name."""
    return qn(WP_NS, tag)


def A(tag: str) -> str:
    """DrawingML qualified name."""
    return qn(A_NS, tag)


def PIC(tag: str) -> str:
    """DrawingML picture qualified name."""
    return qn(PIC_NS, tag)


def MW(tag: str) -> str:
    """msword round-trip qualified name."""
    return qn(MSWORD_RT_NS, tag)


def _xml_bytes(root: etree._Element) -> bytes:
    """Serialize an element to wire-format bytes (typed wrapper for lxml)."""
    return cast(
        bytes,
        etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True),
    )


# ---------------------------------------------------------------------------
# Relationships table
# ---------------------------------------------------------------------------


@dataclass
class Relationship:
    """One row in `word/_rels/document.xml.rels`."""

    rid: str
    type: str
    target: str


@dataclass
class RelTable:
    """Builder for the document relationships file.

    The styles relationship is always present so `word/styles.xml` resolves;
    image relationships are appended as the exporter encounters image blocks.
    """

    rels: list[Relationship] = field(default_factory=list)
    _next_id: int = 1

    def add(self, rel_type: str, target: str) -> str:
        rid = f"rId{self._next_id}"
        self._next_id += 1
        self.rels.append(Relationship(rid=rid, type=rel_type, target=target))
        return rid

    def to_xml(self) -> bytes:
        root = etree.Element(
            qn(PKG_REL_NS, "Relationships"),
            nsmap={None: PKG_REL_NS},
        )
        for rel in self.rels:
            etree.SubElement(
                root,
                qn(PKG_REL_NS, "Relationship"),
                Id=rel.rid,
                Type=rel.type,
                Target=rel.target,
            )
        return _xml_bytes(root)


# ---------------------------------------------------------------------------
# Static document parts
# ---------------------------------------------------------------------------


def content_types_xml(image_extensions: set[str]) -> bytes:
    """Return `[Content_Types].xml` listing all parts and image defaults.

    `image_extensions` are lowercase extensions without the dot (e.g. `"png"`).
    """

    ct_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
    root = etree.Element(qn(ct_ns, "Types"), nsmap={None: ct_ns})

    # Standard defaults: rels + xml.
    etree.SubElement(
        root,
        qn(ct_ns, "Default"),
        Extension="rels",
        ContentType="application/vnd.openxmlformats-package.relationships+xml",
    )
    etree.SubElement(
        root,
        qn(ct_ns, "Default"),
        Extension="xml",
        ContentType="application/xml",
    )
    for ext in sorted(image_extensions):
        etree.SubElement(
            root,
            qn(ct_ns, "Default"),
            Extension=ext,
            ContentType=_image_content_type(ext),
        )

    # Override for the document and styles parts.
    etree.SubElement(
        root,
        qn(ct_ns, "Override"),
        PartName="/word/document.xml",
        ContentType=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
        ),
    )
    etree.SubElement(
        root,
        qn(ct_ns, "Override"),
        PartName="/word/styles.xml",
        ContentType=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"
        ),
    )
    return _xml_bytes(root)


def _image_content_type(ext: str) -> str:
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "bmp": "image/bmp",
        "tif": "image/tiff",
        "tiff": "image/tiff",
        "svg": "image/svg+xml",
    }.get(ext, "application/octet-stream")


def package_rels_xml() -> bytes:
    """Return `_rels/.rels` — the package-level relationships file."""
    root = etree.Element(qn(PKG_REL_NS, "Relationships"), nsmap={None: PKG_REL_NS})
    etree.SubElement(
        root,
        qn(PKG_REL_NS, "Relationship"),
        Id="rId1",
        Type=(
            "http://schemas.openxmlformats.org/officeDocument/2006/"
            "relationships/officeDocument"
        ),
        Target="word/document.xml",
    )
    return _xml_bytes(root)


# Style ids we emit. The set is intentionally small — Word will fall back to
# defaults for anything unknown, and richer styling is the import path's job.
STYLE_IDS: dict[str, tuple[str, str]] = {
    # style_id -> (display_name, type)
    "Normal": ("Normal", "paragraph"),
    "Heading1": ("Heading 1", "paragraph"),
    "Heading2": ("Heading 2", "paragraph"),
    "Heading3": ("Heading 3", "paragraph"),
    "Heading4": ("Heading 4", "paragraph"),
    "Heading5": ("Heading 5", "paragraph"),
    "Heading6": ("Heading 6", "paragraph"),
    "ListBullet": ("List Bullet", "paragraph"),
    "ListNumber": ("List Number", "paragraph"),
    "Quote": ("Quote", "paragraph"),
    "Code": ("Code", "paragraph"),
    "Caption": ("Caption", "paragraph"),
    "Callout": ("Callout", "paragraph"),
    "Embed": ("Embed", "paragraph"),
}


def styles_xml() -> bytes:
    """Return `word/styles.xml` — registers the style ids `STYLE_IDS` lists."""
    styles = etree.Element(W("styles"), nsmap={"w": W_NS})
    for style_id, (display, kind) in STYLE_IDS.items():
        s = etree.SubElement(styles, W("style"))
        s.set(W("type"), kind)
        s.set(W("styleId"), style_id)
        name = etree.SubElement(s, W("name"))
        name.set(W("val"), display)
        if style_id == "Normal":
            etree.SubElement(s, W("default")).set(W("val"), "1")
    return _xml_bytes(styles)


# ---------------------------------------------------------------------------
# Document body — building blocks
# ---------------------------------------------------------------------------


def make_document_root() -> etree._Element:
    """Return `<w:document>` with `<w:body>` already attached."""
    doc = etree.Element(W("document"), nsmap={"w": W_NS, "r": R_NS, "wp": WP_NS, "a": A_NS,
                                              "pic": PIC_NS, "mw": MSWORD_RT_NS})
    etree.SubElement(doc, W("body"))
    return doc


def serialize_document(doc: etree._Element) -> bytes:
    """Serialize the document element to wire-format bytes."""
    return _xml_bytes(doc)
