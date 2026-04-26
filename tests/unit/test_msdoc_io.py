"""Unit tests for ``msword.io.msdoc``.

Covers:

* Roundtripping a populated Document (2 pages, 3 frames, 1 story w/ 4
  blocks, 2 assets, 1 swatch, 1 paragraph style) → structural equality.
* Tampered ``format_version`` / ``blocks_schema_version`` raise the right
  errors.
* Atomicity: a crash mid-write leaves the original file untouched and
  doesn't leave a stray tmp file blocking the target.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from msword.io._manifest import (
    BlocksSchemaMismatchError,
    ManifestError,
    UnsupportedFormatError,
)
from msword.io.msdoc import (
    BLOCKS_SCHEMA_VERSION,
    MSDOC_FORMAT_VERSION,
    InMemoryAsset,
    InMemoryBlock,
    InMemoryColorProfile,
    InMemoryColorSwatch,
    InMemoryDocument,
    InMemoryMasterPage,
    InMemoryPage,
    InMemoryStory,
    InMemoryStyle,
    read_msdoc,
    write_msdoc,
)

# --- Helpers ----------------------------------------------------------------


def _sample_document() -> InMemoryDocument:
    """Build the spec-required fixture: 2 pages, 3 frames, 1 story (4 blocks),
    2 assets, 1 swatch, 1 paragraph style.

    Frames are deliberately split 2/1 across the pages so the test exercises
    the case where pages have differing frame counts.
    """
    return InMemoryDocument(
        meta={"title": "Roundtrip", "author": "test", "locale": "en-US"},
        color_profiles=[
            InMemoryColorProfile(id="srgb", name="sRGB v2", kind="sRGB", data=b"ICC-SRGB-BYTES"),
        ],
        color_swatches=[
            InMemoryColorSwatch(
                id="brand-red",
                name="Brand Red",
                components=[0.86, 0.16, 0.13],
                profile_ref="srgb",
            ),
        ],
        paragraph_styles=[
            InMemoryStyle(
                id="body",
                kind="paragraph",
                name="Body",
                based_on=None,
                attrs={"font": "Source Serif", "size": 11.0, "leading": 14.0},
            ),
        ],
        master_pages=[
            InMemoryMasterPage(
                id="A-Master",
                name="A-Master",
                based_on=None,
                frames=[
                    {"id": "mf1", "kind": "text", "x": 36, "y": 36, "w": 522, "h": 720},
                ],
            ),
        ],
        pages=[
            InMemoryPage(
                id="p1",
                master_ref="A-Master",
                frames=[
                    {"id": "f1", "kind": "text", "x": 36, "y": 36, "w": 522, "h": 360},
                    {"id": "f2", "kind": "image", "x": 36, "y": 420, "w": 200, "h": 300},
                ],
            ),
            InMemoryPage(
                id="p2",
                master_ref="A-Master",
                frames=[
                    {"id": "f3", "kind": "text", "x": 36, "y": 36, "w": 522, "h": 720},
                ],
            ),
        ],
        stories=[
            InMemoryStory(
                id="s1",
                blocks=[
                    InMemoryBlock(type="heading", data={"level": 1, "text": "Hello"}),
                    InMemoryBlock(
                        type="paragraph",
                        data={"runs": [{"text": "First paragraph."}]},
                    ),
                    InMemoryBlock(
                        type="paragraph",
                        data={"runs": [{"text": "مرحبا — Arabic mixed."}]},
                    ),
                    InMemoryBlock(type="divider", data={}),
                ],
            ),
        ],
        assets=[
            InMemoryAsset(
                id="img1",
                sha256="a" * 64,
                ext="png",
                kind="image",
                data=b"\x89PNG\r\n\x1a\nfake-png-bytes",
            ),
            InMemoryAsset(
                id="font1",
                sha256="b" * 64,
                ext="otf",
                kind="font",
                data=b"OTTO" + b"fake-font-bytes",
            ),
        ],
    )


def _doc_to_canonical(doc: InMemoryDocument) -> dict[str, Any]:
    """Compare-friendly canonical form. Bytes are represented by their length
    + a hash-stable hex prefix so equality is structural, not identity."""
    return asdict(doc)


# --- Roundtrip --------------------------------------------------------------


def test_roundtrip_structural_equality(tmp_path: Path) -> None:
    src = _sample_document()
    target = tmp_path / "doc.msdoc"

    write_msdoc(src, target)
    assert target.is_file()
    assert zipfile.is_zipfile(target)

    loaded = read_msdoc(target)
    assert _doc_to_canonical(loaded) == _doc_to_canonical(src)


def test_roundtrip_archive_layout(tmp_path: Path) -> None:
    """Archive must contain the spec §8 entries: manifest, document, stories,
    assets, fonts."""
    src = _sample_document()
    target = tmp_path / "doc.msdoc"
    write_msdoc(src, target)

    with zipfile.ZipFile(target) as zf:
        names = set(zf.namelist())
    assert "manifest.json" in names
    assert "document.json" in names
    assert "stories/s1.json" in names
    assert any(n.startswith("assets/") and n.endswith(".png") for n in names)
    assert any(n.startswith("fonts/") and n.endswith(".otf") for n in names)
    assert any(n.startswith("assets/profile-") and n.endswith(".icc") for n in names)


def test_json_is_pretty_printed_and_sorted(tmp_path: Path) -> None:
    """JSON must be ``indent=2, sort_keys=True`` so the format diffs cleanly."""
    src = _sample_document()
    target = tmp_path / "doc.msdoc"
    write_msdoc(src, target)

    with zipfile.ZipFile(target) as zf:
        manifest_bytes = zf.read("manifest.json")
        document_bytes = zf.read("document.json")

    # Pretty: contains newlines and 2-space indentation.
    assert b"\n  " in manifest_bytes
    assert b"\n  " in document_bytes

    # Sorted: the first key in document.json is alphabetically first.
    document = json.loads(document_bytes)
    assert list(document.keys()) == sorted(document.keys())
    manifest = json.loads(manifest_bytes)
    assert list(manifest.keys()) == sorted(manifest.keys())


def test_zip_uses_deflate_compression(tmp_path: Path) -> None:
    src = _sample_document()
    target = tmp_path / "doc.msdoc"
    write_msdoc(src, target)
    with zipfile.ZipFile(target) as zf:
        for info in zf.infolist():
            assert info.compress_type == zipfile.ZIP_DEFLATED, info.filename


# --- Tampered version errors ------------------------------------------------


def _rewrite_manifest(path: Path, **patches: Any) -> None:
    """Helper: open the archive, patch the manifest, write a new archive."""
    with zipfile.ZipFile(path) as zf:
        members = {name: zf.read(name) for name in zf.namelist()}

    manifest = json.loads(members["manifest.json"])
    manifest.update(patches)
    members["manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")

    path.unlink()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)


def test_unsupported_format_version_raises(tmp_path: Path) -> None:
    target = tmp_path / "doc.msdoc"
    write_msdoc(_sample_document(), target)
    _rewrite_manifest(target, format_version=MSDOC_FORMAT_VERSION + 1)

    with pytest.raises(UnsupportedFormatError):
        read_msdoc(target)


def test_future_blocks_schema_version_raises(tmp_path: Path) -> None:
    target = tmp_path / "doc.msdoc"
    write_msdoc(_sample_document(), target)
    _rewrite_manifest(target, blocks_schema_version=BLOCKS_SCHEMA_VERSION + 99)

    with pytest.raises(BlocksSchemaMismatchError):
        read_msdoc(target)


def test_missing_manifest_raises(tmp_path: Path) -> None:
    """An archive without a manifest is malformed."""
    target = tmp_path / "doc.msdoc"
    with zipfile.ZipFile(target, "w") as zf:
        zf.writestr("document.json", b"{}")
    with pytest.raises(ManifestError):
        read_msdoc(target)


def test_corrupt_manifest_json_raises(tmp_path: Path) -> None:
    target = tmp_path / "doc.msdoc"
    with zipfile.ZipFile(target, "w") as zf:
        zf.writestr("manifest.json", b"{not json")
    with pytest.raises(ManifestError):
        read_msdoc(target)


def test_read_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_msdoc(tmp_path / "does-not-exist.msdoc")


# --- Atomicity --------------------------------------------------------------


def test_atomic_crash_leaves_original_untouched(tmp_path: Path) -> None:
    """Simulate a crash mid-write: the original file must survive and no tmp
    file may remain blocking the target name."""
    target = tmp_path / "doc.msdoc"

    # Lay down a known-good archive first.
    original = _sample_document()
    write_msdoc(original, target)
    original_bytes = target.read_bytes()

    # Now try to overwrite it, but make ``os.replace`` blow up *after* the
    # tmp file has been written. This mimics a crash between "ZIP closed"
    # and "rename succeeded".
    mutated = _sample_document()
    mutated.meta["title"] = "Mutated"

    with (
        patch("msword.io.msdoc.os.replace", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        write_msdoc(mutated, target)

    # Original is byte-identical.
    assert target.read_bytes() == original_bytes

    # No stray ``*.tmp-*`` files left lying around.
    leftovers = list(tmp_path.glob("doc.msdoc.tmp-*"))
    assert leftovers == [], f"tmp file(s) leaked: {leftovers}"

    # And we can still read the original.
    loaded = read_msdoc(target)
    assert loaded.meta["title"] == "Roundtrip"


def test_atomic_first_write_no_partial_file(tmp_path: Path) -> None:
    """First-time write that crashes leaves *no* file at ``target``."""
    target = tmp_path / "fresh.msdoc"
    assert not target.exists()

    with (
        patch("msword.io.msdoc.os.replace", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        write_msdoc(_sample_document(), target)

    assert not target.exists()
    leftovers = list(tmp_path.glob("fresh.msdoc.tmp-*"))
    assert leftovers == []


# --- Empty document edge case ----------------------------------------------


def test_roundtrip_empty_document(tmp_path: Path) -> None:
    """A brand-new Document with no content still roundtrips cleanly."""
    target = tmp_path / "empty.msdoc"
    write_msdoc(InMemoryDocument(), target)
    loaded = read_msdoc(target)
    assert _doc_to_canonical(loaded) == _doc_to_canonical(InMemoryDocument())


# --- Constants tied to spec ------------------------------------------------


def test_format_version_is_int_one() -> None:
    assert MSDOC_FORMAT_VERSION == 1
    assert isinstance(MSDOC_FORMAT_VERSION, int)


def test_blocks_schema_version_is_int() -> None:
    assert isinstance(BLOCKS_SCHEMA_VERSION, int)
    assert BLOCKS_SCHEMA_VERSION >= 1
