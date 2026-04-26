"""Native ``.msdoc`` ZIP container — read and write.

Per spec §8 the on-disk shape is::

    document.msdoc/
    ├── manifest.json            (container/schema versions, locale, entries)
    ├── document.json            (pages, frames, styles, swatches, profiles, masters)
    ├── stories/<id>.json        (one JSON per story — clean diff/merge)
    ├── assets/<sha256>.<ext>    (images; content-addressed)
    └── fonts/<hash>.otf         (embedded fonts only)

Design notes:

* **JSON pretty-printed, sorted keys** — the format is intentionally
  diff-friendly. ``indent=2, sort_keys=True`` makes a roundtrip stable
  byte-for-byte for unchanged content, which keeps ``git`` review usable on
  ``.msdoc`` files unzipped in branches.
* **Atomic writes** — we write to ``<path>.tmp-<pid>`` and ``os.replace``
  it onto the final path only after the ZIP is fully closed and fsynced.
  A crash mid-write therefore leaves the original (or no file at all) —
  never a corrupted half-written archive.
* **No I/O outside ``io/``** — model objects expose plain attributes; this
  module pulls them apart and assembles the on-disk record.

The model classes themselves haven't all landed yet (units 2-8 are in
flight). To stay independently mergeable, this unit defines :pep:`544`
``Protocol`` shapes describing only the attributes it needs to read, and a
matching ``deserialize`` step that builds simple in-memory objects (used by
tests and as a reference round-trippable form).
"""

from __future__ import annotations

import contextlib
import json
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from msword.io._manifest import (
    BlocksSchemaMismatchError,
    ManifestError,
    MsdocFormatError,
    UnsupportedFormatError,
    build_manifest,
    validate_manifest,
)
from msword.model.block import BLOCKS_SCHEMA_VERSION

# --- Public constants -------------------------------------------------------

#: Container format version. Bump when the *layout of the ZIP itself* changes
#: (new top-level entries, renamed directories, manifest schema changes).
#: Distinct from :data:`BLOCKS_SCHEMA_VERSION`, which tracks the JSON shape
#: of block payloads inside ``stories/<id>.json``.
MSDOC_FORMAT_VERSION: int = 1


# --- Re-exports so callers ``from msword.io.msdoc import …`` the errors ----

__all__ = [
    "BLOCKS_SCHEMA_VERSION",
    "MSDOC_FORMAT_VERSION",
    "AssetLike",
    "BlockLike",
    "BlocksSchemaMismatchError",
    "ColorProfileLike",
    "ColorSwatchLike",
    "DocumentLike",
    "InMemoryAsset",
    "InMemoryBlock",
    "InMemoryColorProfile",
    "InMemoryColorSwatch",
    "InMemoryDocument",
    "InMemoryMasterPage",
    "InMemoryPage",
    "InMemoryStory",
    "InMemoryStyle",
    "ManifestError",
    "MasterPageLike",
    "MsdocFormatError",
    "PageLike",
    "StoryLike",
    "StyleLike",
    "UnsupportedFormatError",
    "deserialize_document",
    "read_msdoc",
    "serialize_document",
    "write_msdoc",
]


# --- Protocols (read-side; the shape the writer needs) ---------------------
#
# We only require the attributes serialize touches. Anything else the real
# model exposes is fine — Protocols are structural.


@runtime_checkable
class AssetLike(Protocol):
    """Binary asset (image/font), content-addressed by ``sha256``."""

    id: str
    sha256: str
    ext: str  # e.g. "png", "jpg", "svg", "otf"
    kind: str  # "image" | "font" — controls the directory inside the ZIP
    data: bytes


@runtime_checkable
class ColorProfileLike(Protocol):
    """ICC profile (sRGB or CMYK). ``data`` is the raw ICC bytes."""

    id: str
    name: str
    kind: str  # "sRGB" | "CMYK" | other
    data: bytes


@runtime_checkable
class ColorSwatchLike(Protocol):
    id: str
    name: str
    components: list[float]
    profile_ref: str | None


@runtime_checkable
class StyleLike(Protocol):
    id: str
    kind: str  # "paragraph" | "character" | "object"
    name: str
    based_on: str | None
    attrs: dict[str, Any]


@runtime_checkable
class BlockLike(Protocol):
    """Minimal block shape for serialization.

    The full block tree lands in unit 5; for the file format we only need
    a discriminated dict-like payload. We keep the serialization path
    explicit so unit 5's richer model can drop in by implementing
    ``to_json``/``from_json`` (or by exposing ``type`` + ``data``).
    """

    type: str
    data: dict[str, Any]


@runtime_checkable
class StoryLike(Protocol):
    id: str
    blocks: list[BlockLike]


@runtime_checkable
class PageLike(Protocol):
    id: str
    master_ref: str | None
    # Frame shape is owned by unit 3. We round-trip it as opaque dicts so
    # this unit doesn't lock that schema down prematurely.
    frames: list[dict[str, Any]]


@runtime_checkable
class MasterPageLike(Protocol):
    id: str
    name: str
    based_on: str | None
    frames: list[dict[str, Any]]


@runtime_checkable
class DocumentLike(Protocol):
    meta: dict[str, Any]
    color_profiles: list[ColorProfileLike]
    color_swatches: list[ColorSwatchLike]
    paragraph_styles: list[StyleLike]
    character_styles: list[StyleLike]
    object_styles: list[StyleLike]
    master_pages: list[MasterPageLike]
    pages: list[PageLike]
    stories: list[StoryLike]
    assets: list[AssetLike]


# --- In-memory mock implementations ----------------------------------------
#
# These are *not* the production model classes (unit 2 owns ``Document``).
# They exist so this unit's tests — and any sibling unit that needs to feed
# something into ``write_msdoc`` before unit 2 lands — have a working,
# minimal Document-shaped object. Plain dataclasses; no Qt; no I/O.


@dataclass
class InMemoryAsset:
    id: str
    sha256: str
    ext: str
    kind: str  # "image" | "font"
    data: bytes


@dataclass
class InMemoryColorProfile:
    id: str
    name: str
    kind: str
    data: bytes


@dataclass
class InMemoryColorSwatch:
    id: str
    name: str
    components: list[float]
    profile_ref: str | None = None


@dataclass
class InMemoryStyle:
    id: str
    kind: str
    name: str
    based_on: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class InMemoryBlock:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class InMemoryStory:
    id: str
    blocks: list[InMemoryBlock] = field(default_factory=list)


@dataclass
class InMemoryPage:
    id: str
    master_ref: str | None = None
    frames: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class InMemoryMasterPage:
    id: str
    name: str
    based_on: str | None = None
    frames: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class InMemoryDocument:
    meta: dict[str, Any] = field(default_factory=dict)
    color_profiles: list[InMemoryColorProfile] = field(default_factory=list)
    color_swatches: list[InMemoryColorSwatch] = field(default_factory=list)
    paragraph_styles: list[InMemoryStyle] = field(default_factory=list)
    character_styles: list[InMemoryStyle] = field(default_factory=list)
    object_styles: list[InMemoryStyle] = field(default_factory=list)
    master_pages: list[InMemoryMasterPage] = field(default_factory=list)
    pages: list[InMemoryPage] = field(default_factory=list)
    stories: list[InMemoryStory] = field(default_factory=list)
    assets: list[InMemoryAsset] = field(default_factory=list)


# --- Serialization (model → JSON-able dicts) -------------------------------


def _serialize_asset(a: AssetLike) -> dict[str, Any]:
    # Note: we do not include ``data`` in document.json — bytes live as
    # separate ZIP entries under ``assets/`` or ``fonts/``.
    return {
        "id": a.id,
        "sha256": a.sha256,
        "ext": a.ext,
        "kind": a.kind,
    }


def _serialize_color_profile(p: ColorProfileLike) -> dict[str, Any]:
    # ICC bytes also live as separate ZIP entries (``assets/<sha256>.icc``)
    # so that document.json stays text-only and diff-friendly. Profiles are
    # written under the assets dir with a ".icc" extension; here we just
    # capture the cross-reference.
    return {
        "id": p.id,
        "name": p.name,
        "kind": p.kind,
    }


def _serialize_color_swatch(s: ColorSwatchLike) -> dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "components": list(s.components),
        "profile_ref": s.profile_ref,
    }


def _serialize_style(s: StyleLike) -> dict[str, Any]:
    return {
        "id": s.id,
        "kind": s.kind,
        "name": s.name,
        "based_on": s.based_on,
        "attrs": dict(s.attrs),
    }


def _serialize_master_page(m: MasterPageLike) -> dict[str, Any]:
    return {
        "id": m.id,
        "name": m.name,
        "based_on": m.based_on,
        "frames": [dict(f) for f in m.frames],
    }


def _serialize_page(p: PageLike) -> dict[str, Any]:
    return {
        "id": p.id,
        "master_ref": p.master_ref,
        "frames": [dict(f) for f in p.frames],
    }


def _serialize_block(b: BlockLike) -> dict[str, Any]:
    return {"type": b.type, "data": dict(b.data)}


def _serialize_story(s: StoryLike) -> dict[str, Any]:
    return {
        "id": s.id,
        "blocks": [_serialize_block(b) for b in s.blocks],
    }


def serialize_document(doc: DocumentLike) -> dict[str, Any]:
    """Serialize a Document-shaped object to the ``document.json`` dict.

    Stories are *not* embedded — they live in their own ZIP entries; the
    returned dict only carries the story IDs (read in order).
    """
    return {
        "meta": dict(doc.meta),
        "color_profiles": [_serialize_color_profile(p) for p in doc.color_profiles],
        "color_swatches": [_serialize_color_swatch(s) for s in doc.color_swatches],
        "paragraph_styles": [_serialize_style(s) for s in doc.paragraph_styles],
        "character_styles": [_serialize_style(s) for s in doc.character_styles],
        "object_styles": [_serialize_style(s) for s in doc.object_styles],
        "master_pages": [_serialize_master_page(m) for m in doc.master_pages],
        "pages": [_serialize_page(p) for p in doc.pages],
        "story_ids": [s.id for s in doc.stories],
        "assets": [_serialize_asset(a) for a in doc.assets],
    }


# --- Deserialization (JSON → in-memory mock objects) -----------------------
#
# We deliberately deserialize into the ``InMemory*`` shapes rather than the
# (not-yet-existing) production model. When unit 2 lands its real model, it
# can either (a) write a thin adapter that consumes these dicts directly or
# (b) replace this function. Either way the on-disk format stays stable.


def _deserialize_block(d: dict[str, Any]) -> InMemoryBlock:
    return InMemoryBlock(type=str(d["type"]), data=dict(d.get("data", {})))


def _deserialize_story(d: dict[str, Any]) -> InMemoryStory:
    return InMemoryStory(
        id=str(d["id"]),
        blocks=[_deserialize_block(b) for b in d.get("blocks", [])],
    )


def _deserialize_page(d: dict[str, Any]) -> InMemoryPage:
    return InMemoryPage(
        id=str(d["id"]),
        master_ref=d.get("master_ref"),
        frames=[dict(f) for f in d.get("frames", [])],
    )


def _deserialize_master_page(d: dict[str, Any]) -> InMemoryMasterPage:
    return InMemoryMasterPage(
        id=str(d["id"]),
        name=str(d["name"]),
        based_on=d.get("based_on"),
        frames=[dict(f) for f in d.get("frames", [])],
    )


def _deserialize_style(d: dict[str, Any]) -> InMemoryStyle:
    return InMemoryStyle(
        id=str(d["id"]),
        kind=str(d["kind"]),
        name=str(d["name"]),
        based_on=d.get("based_on"),
        attrs=dict(d.get("attrs", {})),
    )


def _deserialize_color_swatch(d: dict[str, Any]) -> InMemoryColorSwatch:
    return InMemoryColorSwatch(
        id=str(d["id"]),
        name=str(d["name"]),
        components=[float(c) for c in d.get("components", [])],
        profile_ref=d.get("profile_ref"),
    )


def deserialize_document(
    document_json: dict[str, Any],
    stories_json: dict[str, dict[str, Any]],
    asset_blobs: dict[str, bytes],
    profile_blobs: dict[str, bytes],
) -> InMemoryDocument:
    """Inverse of :func:`serialize_document`.

    ``asset_blobs`` and ``profile_blobs`` are id→bytes maps the caller
    extracted from ZIP entries.
    """
    profiles: list[InMemoryColorProfile] = []
    for p in document_json.get("color_profiles", []):
        pid = str(p["id"])
        profiles.append(
            InMemoryColorProfile(
                id=pid,
                name=str(p["name"]),
                kind=str(p["kind"]),
                data=profile_blobs.get(pid, b""),
            )
        )

    assets: list[InMemoryAsset] = []
    for a in document_json.get("assets", []):
        aid = str(a["id"])
        assets.append(
            InMemoryAsset(
                id=aid,
                sha256=str(a["sha256"]),
                ext=str(a["ext"]),
                kind=str(a["kind"]),
                data=asset_blobs.get(aid, b""),
            )
        )

    stories: list[InMemoryStory] = []
    for sid in document_json.get("story_ids", []):
        sid_str = str(sid)
        story_obj = stories_json.get(sid_str)
        if story_obj is None:
            raise ManifestError(f"document.json references story {sid_str!r} but no JSON found")
        stories.append(_deserialize_story(story_obj))

    return InMemoryDocument(
        meta=dict(document_json.get("meta", {})),
        color_profiles=profiles,
        color_swatches=[
            _deserialize_color_swatch(s) for s in document_json.get("color_swatches", [])
        ],
        paragraph_styles=[
            _deserialize_style(s) for s in document_json.get("paragraph_styles", [])
        ],
        character_styles=[
            _deserialize_style(s) for s in document_json.get("character_styles", [])
        ],
        object_styles=[_deserialize_style(s) for s in document_json.get("object_styles", [])],
        master_pages=[
            _deserialize_master_page(m) for m in document_json.get("master_pages", [])
        ],
        pages=[_deserialize_page(p) for p in document_json.get("pages", [])],
        stories=stories,
        assets=assets,
    )


# --- ZIP I/O ---------------------------------------------------------------


def _dump_json(obj: Any) -> bytes:
    """Single source of truth for our JSON encoding policy."""
    # ``ensure_ascii=False`` lets us keep RTL/Arabic content readable in
    # diffs; UTF-8 is the de-facto on-disk encoding.
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8")


#: Asset ``kind`` values that route to ``fonts/`` instead of ``assets/``.
#: Spec §8 splits embedded fonts into their own dir to keep font licensing
#: concerns visually separated when an archive is unzipped.
_FONT_KIND = "font"


def _asset_path_for(*, kind: str, sha256: str, ext: str) -> str:
    """Where an asset (or font) lands inside the ZIP."""
    folder = "fonts" if kind == _FONT_KIND else "assets"
    return f"{folder}/{sha256}.{ext}"


def _asset_archive_path(a: AssetLike) -> str:
    return _asset_path_for(kind=a.kind, sha256=a.sha256, ext=a.ext)


def _profile_archive_path(p: ColorProfileLike) -> str:
    # ICC profiles are content-addressed too, but we don't have a sha256
    # field on ColorProfileLike; use the stable id as the on-disk name.
    return f"assets/profile-{p.id}.icc"


def write_msdoc(document: DocumentLike, path: str | os.PathLike[str]) -> None:
    """Write ``document`` to ``path`` as a ``.msdoc`` ZIP archive.

    Atomic: writes to a temp file in the same directory and ``os.replace``s
    it onto ``path`` only after the ZIP is fully closed and fsynced. A
    crash mid-write leaves the original file (if any) untouched.
    """
    # Lazy import: ``msword.model.document`` pulls in PySide6/Qt; keeping
    # the import here lets the InMemoryDocument path stay headless.
    from msword.model.document import Document as _MasterDocument

    if isinstance(document, _MasterDocument):
        _write_msdoc_master(document, path)
        return

    target = Path(path)
    target_dir = target.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    # Same-directory tmp file → ``os.replace`` is atomic on POSIX (and on
    # Windows with the standard library's implementation, ≥3.3).
    tmp = target_dir / f"{target.name}.tmp-{os.getpid()}"

    locale = str(document.meta.get("locale", "en"))
    document_json = serialize_document(document)

    # Compute the entries list up front so the manifest can advertise it.
    entries: list[str] = ["document.json"]
    for s in document.stories:
        entries.append(f"stories/{s.id}.json")
    for a in document.assets:
        entries.append(_asset_archive_path(a))
    for p in document.color_profiles:
        entries.append(_profile_archive_path(p))

    manifest = build_manifest(
        format_version=MSDOC_FORMAT_VERSION,
        blocks_schema_version=BLOCKS_SCHEMA_VERSION,
        locale=locale,
        entries=entries,
    )

    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Manifest first — readers can validate before scanning the rest.
            zf.writestr("manifest.json", _dump_json(manifest))
            zf.writestr("document.json", _dump_json(document_json))

            for s in document.stories:
                zf.writestr(f"stories/{s.id}.json", _dump_json(_serialize_story(s)))

            # De-dupe by archive path: two assets with the same sha256 +
            # ext share one ZIP entry (content-addressed storage).
            seen_paths: set[str] = set()
            for a in document.assets:
                ap = _asset_archive_path(a)
                if ap in seen_paths:
                    continue
                seen_paths.add(ap)
                zf.writestr(ap, a.data)
            for p in document.color_profiles:
                pp = _profile_archive_path(p)
                if pp in seen_paths:
                    continue
                seen_paths.add(pp)
                zf.writestr(pp, p.data)

        # fsync the tmp file before rename — on a crash, the kernel might
        # otherwise rename a not-yet-flushed file into place, defeating
        # atomicity.
        with open(tmp, "rb") as fp:
            os.fsync(fp.fileno())

        os.replace(tmp, target)
    except BaseException:
        # Don't leak the half-written tmp file. ``BaseException`` so we
        # also clean up on KeyboardInterrupt / SystemExit.
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise


def read_msdoc(path: str | os.PathLike[str]) -> Any:
    """Read a ``.msdoc`` archive at ``path``.

    Validates ``format_version`` (raises :class:`UnsupportedFormatError`)
    and ``blocks_schema_version`` (raises
    :class:`BlocksSchemaMismatchError`) *before* parsing the heavier
    document/story payloads.

    Returns the master ``Document`` model when the archive was written
    from one (detected via the ``schema_kind`` marker on
    ``document.json``); otherwise an :class:`InMemoryDocument`.
    """
    src = Path(path)
    if not src.is_file():
        raise FileNotFoundError(f"no .msdoc archive at {src}")

    with zipfile.ZipFile(src, "r") as zf:
        names = set(zf.namelist())

        if "manifest.json" not in names:
            raise ManifestError("archive is missing manifest.json")
        try:
            raw_manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ManifestError(f"manifest.json is not valid JSON: {e}") from e

        # Validates and *raises* on version mismatches. We do this before
        # reading document.json so a forward-incompat file fails fast and
        # cheaply.
        validate_manifest(
            raw_manifest,
            supported_format_version=MSDOC_FORMAT_VERSION,
            supported_blocks_schema_version=BLOCKS_SCHEMA_VERSION,
        )

        if "document.json" not in names:
            raise ManifestError("archive is missing document.json")
        try:
            document_json = json.loads(zf.read("document.json").decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ManifestError(f"document.json is not valid JSON: {e}") from e

        if not isinstance(document_json, dict):
            raise ManifestError("document.json must be a JSON object")

        if document_json.get("schema_kind") == _MASTER_SCHEMA_KIND:
            return _read_msdoc_master(zf, names, document_json)

        stories_json: dict[str, dict[str, Any]] = {}
        for sid in document_json.get("story_ids", []):
            sid_str = str(sid)
            story_path = f"stories/{sid_str}.json"
            if story_path not in names:
                raise ManifestError(f"archive missing story file: {story_path}")
            try:
                story_obj = json.loads(zf.read(story_path).decode("utf-8"))
            except json.JSONDecodeError as e:
                raise ManifestError(f"{story_path} is not valid JSON: {e}") from e
            if not isinstance(story_obj, dict):
                raise ManifestError(f"{story_path} must be a JSON object")
            stories_json[sid_str] = story_obj

        asset_blobs: dict[str, bytes] = {}
        for a in document_json.get("assets", []):
            aid = str(a["id"])
            ap = _asset_path_for(
                kind=str(a.get("kind", "image")),
                sha256=str(a["sha256"]),
                ext=str(a["ext"]),
            )
            if ap not in names:
                raise ManifestError(f"archive missing asset file: {ap}")
            asset_blobs[aid] = zf.read(ap)

        profile_blobs: dict[str, bytes] = {}
        for p in document_json.get("color_profiles", []):
            pid = str(p["id"])
            pp = f"assets/profile-{pid}.icc"
            if pp not in names:
                raise ManifestError(f"archive missing profile file: {pp}")
            profile_blobs[pid] = zf.read(pp)

    return deserialize_document(document_json, stories_json, asset_blobs, profile_blobs)


# --- Master Document path ---------------------------------------------------
#
# The original :class:`InMemoryDocument` path predates :mod:`msword.model.document`
# and uses a structurally different schema. Documents authored against the
# real model carry a ``schema_kind`` marker on ``document.json`` so the reader
# round-trips them back to the master shape rather than the in-memory mock.

_MASTER_SCHEMA_KIND = "msword.model.document.Document"


def _write_msdoc_master(document: Any, path: str | os.PathLike[str]) -> None:
    target = Path(path)
    target_dir = target.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    tmp = target_dir / f"{target.name}.tmp-{os.getpid()}"

    document_payload = document.to_dict()
    # Stories live in their own ZIP entries; replace the embedded copy with a
    # list of references so a roundtrip can rehydrate them in order.
    story_dicts = [s.to_dict() for s in document.stories]
    document_payload["stories"] = [{"id": s["id"]} for s in story_dicts]
    document_payload["schema_kind"] = _MASTER_SCHEMA_KIND

    locale = str(document.meta.locale or "en")

    entries: list[str] = ["document.json"]
    for s in story_dicts:
        entries.append(f"stories/{s['id']}.json")
    asset_entries: list[tuple[str, bytes]] = []
    for asset in document.assets:
        ext = _master_asset_ext(asset.mime_type, asset.original_filename)
        archive_path = _asset_path_for(kind=asset.kind, sha256=asset.sha256, ext=ext)
        asset_entries.append((archive_path, asset.data))
        entries.append(archive_path)

    manifest = build_manifest(
        format_version=MSDOC_FORMAT_VERSION,
        blocks_schema_version=BLOCKS_SCHEMA_VERSION,
        locale=locale,
        entries=entries,
    )

    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", _dump_json(manifest))
            zf.writestr("document.json", _dump_json(document_payload))
            for s in story_dicts:
                zf.writestr(f"stories/{s['id']}.json", _dump_json(s))
            seen_paths: set[str] = set()
            for archive_path, blob in asset_entries:
                if archive_path in seen_paths:
                    continue
                seen_paths.add(archive_path)
                zf.writestr(archive_path, blob)
        with open(tmp, "rb") as fp:
            os.fsync(fp.fileno())
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise


def _read_msdoc_master(
    zf: zipfile.ZipFile, names: set[str], document_json: dict[str, Any]
) -> Any:
    from msword.model.block import BlockRegistry
    from msword.model.document import Document as _MasterDocument
    from msword.model.story import Story

    story_dicts: list[dict[str, Any]] = []
    for ref in document_json.get("stories", []):
        sid = str(ref["id"])
        story_path = f"stories/{sid}.json"
        if story_path not in names:
            raise ManifestError(f"archive missing story file: {story_path}")
        try:
            story_obj = json.loads(zf.read(story_path).decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ManifestError(f"{story_path} is not valid JSON: {e}") from e
        if not isinstance(story_obj, dict):
            raise ManifestError(f"{story_path} must be a JSON object")
        story_dicts.append(story_obj)

    payload = dict(document_json)
    payload.pop("schema_kind", None)
    # Replace the slim story refs with the full dicts so ``Document.from_dict``
    # restores per-story metadata (language, default styles, blocks).
    payload["stories"] = []
    doc = _MasterDocument.from_dict(payload)
    for sd in story_dicts:
        # ``Story.from_dict`` is typed against the unit-5 ``BlockProto``; the
        # real ``BlockRegistry`` returns concrete ``Block`` subclasses that
        # satisfy the protocol structurally.
        block_factory: Any = BlockRegistry.resolve
        story = Story.from_dict(sd, block_factory=block_factory)
        doc.stories.append(story)

    for asset_meta in document_json.get("assets", []):
        sha = str(asset_meta.get("sha256", ""))
        if not sha:
            continue
        ext = _master_asset_ext(
            str(asset_meta.get("mime_type", "")),
            str(asset_meta.get("original_filename", "")),
        )
        kind = str(asset_meta.get("kind", "image"))
        archive_path = _asset_path_for(kind=kind, sha256=sha, ext=ext)
        if archive_path not in names:
            raise ManifestError(f"archive missing asset file: {archive_path}")
        data = zf.read(archive_path)
        doc.assets.add(
            data=data,
            kind=kind,  # type: ignore[arg-type]
            mime_type=str(asset_meta.get("mime_type", "")),
            original_filename=str(asset_meta.get("original_filename", "")),
        )

    return doc


def _master_asset_ext(mime_type: str, filename: str) -> str:
    """Best-effort filename extension for an asset; falls back to "bin"."""
    if "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    if "/" in mime_type:
        return mime_type.split("/", 1)[1].lower()
    return "bin"
