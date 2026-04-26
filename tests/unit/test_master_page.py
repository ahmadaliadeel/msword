"""Unit tests for `msword.model.master_page` — see spec §4."""

from __future__ import annotations

import pytest

from msword.model.master_page import MasterPage


def test_resolve_parent_chain_root_first() -> None:
    """Chain A -> B -> C resolves root-first to [A, B, C]."""
    a = MasterPage(id="A", name="A-Master")
    b = MasterPage(id="B", name="B-Master", parent_master_id="A")
    c = MasterPage(id="C", name="C-Master", parent_master_id="B")

    chain = c.resolve_parent_chain([a, b, c])
    assert [m.id for m in chain] == ["A", "B", "C"]


def test_resolve_parent_chain_single_root() -> None:
    a = MasterPage(id="A", name="A-Master")
    chain = a.resolve_parent_chain([a])
    assert chain == [a]


def test_resolve_parent_chain_accepts_mapping() -> None:
    a = MasterPage(id="A", name="A-Master")
    b = MasterPage(id="B", name="B-Master", parent_master_id="A")
    chain = b.resolve_parent_chain({a.id: a, b.id: b})
    assert [m.id for m in chain] == ["A", "B"]


def test_resolve_parent_chain_self_reachable_without_explicit_listing() -> None:
    """`self` is always reachable even if not present in the masters arg."""
    a = MasterPage(id="A", name="A-Master")
    b = MasterPage(id="B", name="B-Master", parent_master_id="A")
    chain = b.resolve_parent_chain([a])  # b not in the iterable
    assert [m.id for m in chain] == ["A", "B"]


def test_resolve_parent_chain_cycle_raises() -> None:
    """A direct cycle (A -> B -> A) raises ValueError."""
    a = MasterPage(id="A", name="A-Master", parent_master_id="B")
    b = MasterPage(id="B", name="B-Master", parent_master_id="A")
    with pytest.raises(ValueError, match=r"[Cc]ycle"):
        a.resolve_parent_chain([a, b])


def test_resolve_parent_chain_self_cycle_raises() -> None:
    """A master pointing at itself is a cycle."""
    a = MasterPage(id="A", name="A-Master", parent_master_id="A")
    with pytest.raises(ValueError, match=r"[Cc]ycle"):
        a.resolve_parent_chain([a])


def test_resolve_parent_chain_missing_parent_raises() -> None:
    a = MasterPage(id="A", name="A-Master", parent_master_id="MISSING")
    with pytest.raises(ValueError, match="missing"):
        a.resolve_parent_chain([a])


def test_master_page_roundtrip() -> None:
    m = MasterPage(
        id="A",
        name="A-Master",
        parent_master_id=None,
        width_pt=612.0,
        height_pt=792.0,
    )
    restored = MasterPage.from_dict(m.to_dict())
    assert restored.id == m.id
    assert restored.name == m.name
    assert restored.parent_master_id == m.parent_master_id
    assert restored.width_pt == m.width_pt
    assert restored.height_pt == m.height_pt
