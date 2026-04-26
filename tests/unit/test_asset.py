"""Unit tests for `msword.model.asset` — see spec §4 (Data model)."""

from __future__ import annotations

import hashlib

import pytest

from msword.model.asset import Asset, AssetRegistry


def test_asset_hash_equality_by_sha256() -> None:
    """Two Assets with the same sha256 are equal and hash equal."""
    a = Asset(
        sha256="abc",
        kind="image",
        mime_type="image/png",
        data=b"hello",
        original_filename="a.png",
    )
    b = Asset(
        sha256="abc",
        kind="image",
        mime_type="image/png",
        data=b"different-payload",
        original_filename="b.png",
    )
    assert a == b
    assert hash(a) == hash(b)


def test_registry_dedupes_same_bytes() -> None:
    """Adding identical bytes twice yields a single registry entry."""
    reg = AssetRegistry()
    payload = b"image-bytes-fixture"
    expected_sha = hashlib.sha256(payload).hexdigest()

    a1 = reg.add(payload, kind="image", mime_type="image/png", original_filename="x.png")
    a2 = reg.add(payload, kind="image", mime_type="image/png", original_filename="y.png")

    assert a1 is a2
    assert a1.sha256 == expected_sha
    assert len(reg) == 1
    assert expected_sha in reg


def test_registry_signals_fire() -> None:
    """`asset_added` fires once on first insert, `asset_removed` fires on remove."""
    reg = AssetRegistry()
    added: list[str] = []
    removed: list[str] = []
    reg.asset_added.connect(added.append)
    reg.asset_removed.connect(removed.append)

    payload = b"font-bytes"
    asset = reg.add(payload, kind="font", mime_type="font/otf", original_filename="f.otf")

    # Duplicate add must NOT re-fire `asset_added`.
    reg.add(payload, kind="font", mime_type="font/otf", original_filename="dup.otf")
    assert added == [asset.sha256]

    returned = reg.remove(asset.sha256)
    assert returned is asset
    assert removed == [asset.sha256]
    assert len(reg) == 0


def test_registry_remove_missing_returns_none() -> None:
    reg = AssetRegistry()
    assert reg.remove("does-not-exist") is None


def test_registry_iteration_and_get() -> None:
    reg = AssetRegistry()
    a = reg.add(b"one", kind="image", mime_type="image/jpeg", original_filename="1.jpg")
    b = reg.add(b"two", kind="image", mime_type="image/jpeg", original_filename="2.jpg")

    by_sha = {asset.sha256: asset for asset in reg}
    assert by_sha == {a.sha256: a, b.sha256: b}
    assert reg.get(a.sha256) is a
    assert reg.get("missing") is None


def test_asset_to_dict_omits_bytes() -> None:
    """Asset.to_dict serializes metadata only — bytes live in the ZIP payload."""
    asset = Asset(
        sha256="deadbeef",
        kind="image",
        mime_type="image/png",
        data=b"binary-blob",
        original_filename="logo.png",
    )
    d = asset.to_dict()
    assert d == {
        "sha256": "deadbeef",
        "kind": "image",
        "mime_type": "image/png",
        "original_filename": "logo.png",
    }
    assert "data" not in d


def test_asset_is_immutable() -> None:
    asset = Asset(
        sha256="x",
        kind="image",
        mime_type="image/png",
        data=b"",
        original_filename="x.png",
    )
    with pytest.raises((AttributeError, TypeError)):
        asset.kind = "font"  # type: ignore[misc]
