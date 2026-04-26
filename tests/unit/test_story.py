from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from msword.model.run import Run
from msword.model.story import BlockProto, ParagraphSpec, Story


@dataclass(slots=True)
class FakeBlock:
    """Minimal BlockProto stand-in for tests (unit-5 provides the real registry)."""

    block_id: str
    text: str = ""
    paragraph_style_ref: str | None = None
    kind: str = "fake"
    paragraphs: tuple[ParagraphSpec, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.paragraphs:
            self.paragraphs = (
                ParagraphSpec(
                    runs=(Run(text=self.text),),
                    paragraph_style_ref=self.paragraph_style_ref,
                    block_id=self.block_id,
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "block_id": self.block_id,
            "text": self.text,
            "paragraph_style_ref": self.paragraph_style_ref,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FakeBlock:
        return cls(
            block_id=data["block_id"],
            text=data.get("text", ""),
            paragraph_style_ref=data.get("paragraph_style_ref"),
            kind=data.get("kind", "fake"),
        )

    def iter_paragraphs(self) -> Iterable[ParagraphSpec]:
        return iter(self.paragraphs)


def test_fake_block_satisfies_block_proto() -> None:
    assert isinstance(FakeBlock(block_id="b0"), BlockProto)


def test_story_construction_defaults(qtbot) -> None:  # type: ignore[no-untyped-def]
    del qtbot  # the fixture is required to bring up QApplication; not used directly
    s = Story(id="s0")
    assert s.id == "s0"
    assert s.blocks == []
    assert s.language == "en-US"
    assert s.default_paragraph_style_ref is None
    assert s.default_character_style_ref is None


def test_add_block_in_order_and_signal(qtbot) -> None:  # type: ignore[no-untyped-def]
    s = Story(id="s1")
    blocks = [FakeBlock(block_id=f"b{i}", text=f"para {i}") for i in range(3)]
    indices: list[int] = []
    s.block_added.connect(indices.append)

    for b in blocks:
        s.add_block(b)

    assert [b.block_id for b in s.blocks] == ["b0", "b1", "b2"]  # type: ignore[attr-defined]
    assert indices == [0, 1, 2]


def test_add_block_with_explicit_index(qtbot) -> None:  # type: ignore[no-untyped-def]
    s = Story(id="s2")
    s.add_block(FakeBlock(block_id="a"))
    s.add_block(FakeBlock(block_id="c"))
    s.add_block(FakeBlock(block_id="b"), index=1)
    assert [b.block_id for b in s.blocks] == ["a", "b", "c"]  # type: ignore[attr-defined]


def test_remove_block_emits_and_returns(qtbot) -> None:  # type: ignore[no-untyped-def]
    s = Story(id="s3")
    a = FakeBlock(block_id="a")
    b = FakeBlock(block_id="b")
    s.add_block(a)
    s.add_block(b)

    removed_indices: list[int] = []
    s.block_removed.connect(removed_indices.append)

    removed = s.remove_block(0)
    assert removed is a
    assert [x.block_id for x in s.blocks] == ["b"]  # type: ignore[attr-defined]
    assert removed_indices == [0]


def test_changed_signal_fires_on_mutations(qtbot) -> None:  # type: ignore[no-untyped-def]
    s = Story(id="s4")
    fired: list[None] = []
    s.changed.connect(lambda: fired.append(None))
    s.add_block(FakeBlock(block_id="a"))
    s.add_block(FakeBlock(block_id="b"))
    s.remove_block(0)
    assert len(fired) == 3


def test_iter_paragraphs_yields_block_paragraphs_in_order(qtbot) -> None:  # type: ignore[no-untyped-def]
    s = Story(id="s5")
    s.add_block(FakeBlock(block_id="b0", text="alpha"))
    s.add_block(FakeBlock(block_id="b1", text="beta"))
    s.add_block(FakeBlock(block_id="b2", text="gamma"))

    paras = list(s.iter_paragraphs())
    assert [p.block_id for p in paras] == ["b0", "b1", "b2"]
    assert [p.runs[0].text for p in paras] == ["alpha", "beta", "gamma"]


def test_to_dict_from_dict_roundtrip(qtbot) -> None:  # type: ignore[no-untyped-def]
    s = Story(
        id="s6",
        default_paragraph_style_ref="ps-body",
        default_character_style_ref="cs-default",
        language="ar-SA",
    )
    s.add_block(FakeBlock(block_id="b0", text="hi", paragraph_style_ref="ps-body"))
    s.add_block(FakeBlock(block_id="b1", text="bye"))

    payload = s.to_dict()
    assert payload["id"] == "s6"
    assert payload["language"] == "ar-SA"
    assert payload["default_paragraph_style_ref"] == "ps-body"
    assert payload["default_character_style_ref"] == "cs-default"
    assert [b["block_id"] for b in payload["blocks"]] == ["b0", "b1"]

    s2 = Story.from_dict(payload, block_factory=FakeBlock.from_dict)
    assert s2.id == s.id
    assert s2.language == s.language
    assert s2.default_paragraph_style_ref == s.default_paragraph_style_ref
    assert s2.default_character_style_ref == s.default_character_style_ref
    assert [b.block_id for b in s2.blocks] == ["b0", "b1"]  # type: ignore[attr-defined]
    assert [b.text for b in s2.blocks] == ["hi", "bye"]  # type: ignore[attr-defined]


def test_paragraph_spec_is_frozen_value() -> None:
    p = ParagraphSpec(runs=(Run(text="x"),), paragraph_style_ref=None, block_id="b0")
    assert p.runs[0].text == "x"
    p2 = dataclasses.replace(p, block_id="b1")
    assert p2.block_id == "b1"
    assert p.block_id == "b0"
