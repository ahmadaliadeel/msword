"""Asset model — content-addressed storage for images and embedded fonts.

Per spec §4 (Data model) the `Document` keeps an `assets/` registry; assets are
deduplicated by SHA-256 of their bytes. The registry emits Qt signals so views
(thumbnail palettes, etc.) can react to additions/removals without polling.

This module is part of the *pure* model package: no Qt widgets, no rendering,
no I/O — `QObject` is used purely to carry `Signal`s on the change bus, as
allowed by the unit-2 anchor invariants.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal

from PySide6.QtCore import QObject, Signal

AssetKind = Literal["image", "font"]


@dataclass(frozen=True, slots=True)
class Asset:
    """Immutable, content-addressed asset (image or font).

    Identity is the SHA-256 of `data`; equality and hashing follow `sha256`
    only. Two `Asset` instances with the same bytes are interchangeable.
    """

    sha256: str
    kind: AssetKind
    mime_type: str
    data: bytes
    original_filename: str

    def __hash__(self) -> int:  # pragma: no cover - trivial
        return hash(self.sha256)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Asset):
            return NotImplemented
        return self.sha256 == other.sha256

    def to_dict(self) -> dict[str, Any]:
        """Serialize metadata only.

        Asset bytes live in the `.msdoc` ZIP under `assets/<sha256>` and are
        not embedded in JSON; the registry rehydrates `data` from disk on load.
        """
        return {
            "sha256": self.sha256,
            "kind": self.kind,
            "mime_type": self.mime_type,
            "original_filename": self.original_filename,
        }


class AssetRegistry(QObject):
    """Content-addressed asset store with Qt change signals.

    Adding the same bytes twice yields the same `sha256` and a single stored
    entry — `len()` does not grow on duplicate input.
    """

    asset_added = Signal(str)
    asset_removed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._assets: dict[str, Asset] = {}

    @staticmethod
    def _hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def add(
        self,
        data: bytes,
        kind: AssetKind,
        mime_type: str,
        original_filename: str,
    ) -> Asset:
        """Register `data`, deduplicating by SHA-256.

        If an asset with the same hash already exists the existing instance is
        returned and no `asset_added` signal is emitted.
        """
        sha = self._hash(data)
        existing = self._assets.get(sha)
        if existing is not None:
            return existing
        asset = Asset(
            sha256=sha,
            kind=kind,
            mime_type=mime_type,
            data=data,
            original_filename=original_filename,
        )
        self._assets[sha] = asset
        self.asset_added.emit(sha)
        return asset

    def get(self, sha256: str) -> Asset | None:
        return self._assets.get(sha256)

    def remove(self, sha256: str) -> Asset | None:
        """Remove and return the asset, or `None` if it was not registered."""
        asset = self._assets.pop(sha256, None)
        if asset is not None:
            self.asset_removed.emit(sha256)
        return asset

    def __iter__(self) -> Iterator[Asset]:
        return iter(self._assets.values())

    def __len__(self) -> int:
        return len(self._assets)

    def __contains__(self, sha256: object) -> bool:
        return isinstance(sha256, str) and sha256 in self._assets
