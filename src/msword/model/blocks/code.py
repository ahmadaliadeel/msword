"""CodeBlock — fenced code block with language, theme, and optional line numbers."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, ClassVar

from msword.model.block import Block, BlockRegistry, ParagraphSpec
from msword.model.run import Run

CODE_PARAGRAPH_STYLE = "Code"
CODE_FONT_REF = "mono"


@dataclass
class CodeBlock(Block):
    kind: ClassVar[str] = "code"

    id: str
    text: str = ""
    language: str = ""
    theme: str = "default"
    show_line_numbers: bool = False

    def iter_paragraphs(self) -> Iterator[ParagraphSpec]:
        # Empty text still yields one (empty) paragraph so the block has a visible
        # extent on the page; otherwise an empty code block would collapse.
        lines = self.text.split("\n") if self.text else [""]
        for line in lines:
            yield ParagraphSpec(
                runs=(Run(text=line, font_ref=CODE_FONT_REF),),
                paragraph_style_ref=CODE_PARAGRAPH_STYLE,
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "language": self.language,
            "text": self.text,
            "theme": self.theme,
            "show_line_numbers": self.show_line_numbers,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CodeBlock:
        return cls(
            id=data["id"],
            language=data.get("language", ""),
            text=data.get("text", ""),
            theme=data.get("theme", "default"),
            show_line_numbers=data.get("show_line_numbers", False),
        )


BlockRegistry.register(CodeBlock)
