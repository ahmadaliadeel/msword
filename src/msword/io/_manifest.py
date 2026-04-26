"""Internal helpers for ``manifest.json`` inside ``.msdoc`` archives.

The manifest is the first file every reader consults: it carries the
container format version, the block-schema version, locale, and a flat
listing of the other entries in the archive. Keeping it small and explicit
means a reader can fail fast (with a precise error) before touching the
heavier ``document.json`` / story / asset payloads.

This module is intentionally I/O-free — it only constructs and validates the
in-memory manifest dict. ``io.msdoc`` is the only module that reads/writes
ZIP entries.
"""

from __future__ import annotations

from typing import Any

# --- Errors -----------------------------------------------------------------


class MsdocFormatError(Exception):
    """Base for all ``.msdoc`` read errors."""


class UnsupportedFormatError(MsdocFormatError):
    """Raised when the container's ``format_version`` is not understood.

    Either the file was written by a newer msword (forward-incompat) or it
    isn't an msword archive at all.
    """


class BlocksSchemaMismatchError(MsdocFormatError):
    """Raised when ``blocks_schema_version`` is newer than this build supports.

    Distinct from :class:`UnsupportedFormatError`: the *container* is fine,
    but the block JSON inside uses a schema this build can't decode.
    """


class ManifestError(MsdocFormatError):
    """Raised when the manifest itself is malformed (missing keys, bad types)."""


# --- Required keys ----------------------------------------------------------

_REQUIRED_KEYS: tuple[str, ...] = (
    "format_version",
    "blocks_schema_version",
    "locale",
    "entries",
)


def build_manifest(
    *,
    format_version: int,
    blocks_schema_version: int,
    locale: str,
    entries: list[str],
) -> dict[str, Any]:
    """Build the canonical manifest dict written to ``manifest.json``.

    ``entries`` is the sorted list of *other* archive members (relative
    paths, forward-slash separated). It exists to let a reader detect a
    truncated archive without scanning every ZIP entry.
    """
    return {
        "format_version": int(format_version),
        "blocks_schema_version": int(blocks_schema_version),
        "locale": str(locale),
        "entries": sorted(entries),
    }


def validate_manifest(
    raw: object,
    *,
    supported_format_version: int,
    supported_blocks_schema_version: int,
) -> dict[str, Any]:
    """Validate a parsed manifest and return it (typed) on success.

    Raises:
        ManifestError: Manifest is missing required keys or has wrong types.
        UnsupportedFormatError: ``format_version`` is not equal to
            ``supported_format_version``. (We don't yet have a
            backward-compat surface; the first format bump will introduce
            "supports range" semantics here.)
        BlocksSchemaMismatchError: ``blocks_schema_version`` is greater
            than ``supported_blocks_schema_version``.
    """
    if not isinstance(raw, dict):
        raise ManifestError("manifest.json must be a JSON object")

    for key in _REQUIRED_KEYS:
        if key not in raw:
            raise ManifestError(f"manifest.json missing required key: {key!r}")

    fmt = raw["format_version"]
    if not isinstance(fmt, int) or isinstance(fmt, bool):
        raise ManifestError("manifest.json 'format_version' must be an int")
    if fmt != supported_format_version:
        raise UnsupportedFormatError(
            f"unsupported .msdoc format_version={fmt} "
            f"(this build supports {supported_format_version})"
        )

    schema = raw["blocks_schema_version"]
    if not isinstance(schema, int) or isinstance(schema, bool):
        raise ManifestError("manifest.json 'blocks_schema_version' must be an int")
    if schema > supported_blocks_schema_version:
        raise BlocksSchemaMismatchError(
            f"file uses blocks_schema_version={schema}, "
            f"this build supports up to {supported_blocks_schema_version}"
        )

    if not isinstance(raw["locale"], str):
        raise ManifestError("manifest.json 'locale' must be a string")

    entries = raw["entries"]
    if not isinstance(entries, list) or not all(isinstance(e, str) for e in entries):
        raise ManifestError("manifest.json 'entries' must be a list of strings")

    # Return a fresh, well-typed copy so callers don't accidentally mutate
    # the parsed JSON object underneath.
    return {
        "format_version": fmt,
        "blocks_schema_version": schema,
        "locale": raw["locale"],
        "entries": list(entries),
    }


__all__ = [
    "BlocksSchemaMismatchError",
    "ManifestError",
    "MsdocFormatError",
    "UnsupportedFormatError",
    "build_manifest",
    "validate_manifest",
]
