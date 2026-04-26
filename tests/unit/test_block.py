"""Tests for the Block base, BlockRegistry, and schema-version constant."""

from __future__ import annotations

import pytest

import msword.model.blocks  # noqa: F401  (imports register the four block types)
from msword.model.block import (
    BLOCKS_SCHEMA_VERSION,
    BlockRegistry,
    UnknownBlockKindError,
)


def test_schema_version_is_int() -> None:
    assert isinstance(BLOCKS_SCHEMA_VERSION, int)
    assert BLOCKS_SCHEMA_VERSION >= 1


def test_registry_has_core_kinds() -> None:
    kinds = BlockRegistry.kinds()
    for expected in ("paragraph", "heading", "divider", "embed"):
        assert expected in kinds


def test_resolve_unknown_kind_raises() -> None:
    with pytest.raises(UnknownBlockKindError):
        BlockRegistry.resolve({"kind": "unknown"})


def test_resolve_missing_kind_raises() -> None:
    with pytest.raises(UnknownBlockKindError):
        BlockRegistry.resolve({})
