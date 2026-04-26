"""I/O package — native ``.msdoc`` and DOCX import/export.

Only modules in this package are allowed to perform disk I/O for documents.
Model and view code calls into here; never the reverse.
"""

from __future__ import annotations

from msword.io.msdoc import (
    BLOCKS_SCHEMA_VERSION,
    MSDOC_FORMAT_VERSION,
    BlocksSchemaMismatchError,
    ManifestError,
    MsdocFormatError,
    UnsupportedFormatError,
    read_msdoc,
    write_msdoc,
)

__all__ = [
    "BLOCKS_SCHEMA_VERSION",
    "MSDOC_FORMAT_VERSION",
    "BlocksSchemaMismatchError",
    "ManifestError",
    "MsdocFormatError",
    "UnsupportedFormatError",
    "read_msdoc",
    "write_msdoc",
]
