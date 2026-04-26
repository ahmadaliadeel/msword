"""Pure find/replace engine — Bidi-aware, logical-order, NFC-normalized.

Per spec §12 unit 31: the engine is a pure function over `Document`. It
walks story → block → run, concatenates each block's run text in *logical*
order (which is the correct order for Arabic / Urdu — visual order is a
rendering concern, never a search concern), runs `re.finditer` (or a
literal scan) over the NFC-normalized text, and maps every match offset
back to `(story_id, block_id, run_index, char_start, char_end)`.

The engine never mutates the document. Mutations go through commands — see
`replace_all`, which returns a `MacroCommand` of `ReplaceTextInRunCommand`s.
The caller pushes the macro onto the undo stack.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from msword.commands import Command, MacroCommand, ReplaceTextInRunCommand
from msword.commands.base import Document as CommandDocument
from msword.model.document import Document
from msword.model.run import Run

Scope = Literal["document", "story", "selection"]


@dataclass(frozen=True)
class Match:
    """A located occurrence inside the document.

    Coordinates are in NFC-normalized character offsets. `run_index` and
    char offsets are local to the run that contains the match's *start*;
    a match that spans multiple runs is represented by `extra_runs` —
    additional `(run_index, char_start, char_end)` tuples in logical order
    that together cover the rest of the match.
    """

    story_id: str
    block_id: str
    run_index: int
    char_start: int
    char_end: int
    extra_runs: tuple[tuple[int, int, int], ...] = field(default_factory=tuple)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _build_pattern(
    query: str,
    *,
    case_sensitive: bool,
    whole_word: bool,
    regex: bool,
) -> re.Pattern[str]:
    """Compile the user query into a regex pattern.

    Empty queries raise `ValueError` — searching for "" is meaningless and
    would generate infinite zero-width matches.
    """
    if query == "":
        raise ValueError("query must be non-empty")

    # NFC-normalize literal queries so composed/decomposed forms match.
    # Regex queries are passed through as-is — normalising would mangle the
    # syntax (e.g. character classes, escapes).
    pattern_str = query if regex else re.escape(_normalize(query))
    if whole_word:
        pattern_str = rf"\b(?:{pattern_str})\b"

    flags = re.IGNORECASE if not case_sensitive else 0
    return re.compile(pattern_str, flags)


@dataclass
class _RunSpan:
    """Maps a slice of the concatenated block text back to a run."""

    run_index: int
    text_start: int  # offset within the concatenated block text
    text_end: int  # exclusive
    run: Run


def _iter_text_blocks(blocks: list[Any]) -> Iterator[Any]:
    """Walk a block tree yielding only blocks that own a `runs: list[Run]`.

    Recurses into container blocks (callouts, quotes, lists, tables) so
    text inside them is searchable. Blocks without a runs list (dividers,
    images, code, embeds) are skipped — code blocks store text as a
    single `str`, not as runs, and replacing into them would require a
    different mutation shape.
    """
    for block in blocks:
        runs = getattr(block, "runs", None)
        if isinstance(runs, list):
            yield block
            continue
        # Container shapes: CalloutBlock / QuoteBlock have `blocks: list[Block]`.
        nested = getattr(block, "blocks", None)
        if isinstance(nested, list):
            yield from _iter_text_blocks(nested)
            continue
        # ListBlock has `items: list[ListItem]`, each with `blocks`.
        items = getattr(block, "items", None)
        if isinstance(items, list):
            for item in items:
                item_blocks = getattr(item, "blocks", None)
                if isinstance(item_blocks, list):
                    yield from _iter_text_blocks(item_blocks)
            continue
        # TableBlock cells live in `cells: dict[(r, c), BlockCell]`.
        cells = getattr(block, "cells", None)
        if isinstance(cells, dict):
            for cell in cells.values():
                cell_blocks = getattr(cell, "blocks", None)
                if isinstance(cell_blocks, list):
                    yield from _iter_text_blocks(cell_blocks)


def _block_runs_with_spans(block: Any) -> tuple[str, list[_RunSpan]]:
    """Concatenate `block.runs` text (NFC) and record each run's span.

    Logical order matters — runs are already stored in logical order by the
    model, which is also the correct order for Arabic/Urdu searching.
    """
    parts: list[str] = []
    spans: list[_RunSpan] = []
    cursor = 0
    for idx, run in enumerate(block.runs):
        run_text = _normalize(run.text)
        parts.append(run_text)
        spans.append(
            _RunSpan(
                run_index=idx,
                text_start=cursor,
                text_end=cursor + len(run_text),
                run=run,
            )
        )
        cursor += len(run_text)
    return "".join(parts), spans


def _spans_for_range(
    spans: list[_RunSpan], match_start: int, match_end: int
) -> list[tuple[_RunSpan, int, int]]:
    """Slice the spans covered by [match_start, match_end) into per-run pieces."""
    pieces: list[tuple[_RunSpan, int, int]] = []
    for span in spans:
        if span.text_end <= match_start:
            continue
        if span.text_start >= match_end:
            break
        local_start = max(match_start, span.text_start) - span.text_start
        local_end = min(match_end, span.text_end) - span.text_start
        if local_end > local_start:
            pieces.append((span, local_start, local_end))
    return pieces


def find_all(
    doc: Document,
    query: str,
    *,
    case_sensitive: bool = False,
    whole_word: bool = False,
    regex: bool = False,
    scope: Scope = "document",
    story_id: str | None = None,
) -> list[Match]:
    """Locate every occurrence of `query` in `doc`.

    `scope`:
      * `"document"` — every story (default).
      * `"story"`    — single story; pass `story_id`.
      * `"selection"` — currently treated as document scope; the selection
        model is owned by the canvas/text-tool unit and will plug a range
        restriction in once it lands. The signature is stable.
    """
    pattern = _build_pattern(
        query,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        regex=regex,
    )

    if scope == "story":
        if story_id is None:
            raise ValueError("scope='story' requires story_id")
        story = doc.find_story(story_id)
        stories = [story] if story is not None else []
    else:
        stories = list(doc.stories)

    results: list[Match] = []
    for story in stories:
        for block in _iter_text_blocks(story.blocks):
            text, spans = _block_runs_with_spans(block)
            if not text or not spans:
                continue
            for re_match in pattern.finditer(text):
                m_start, m_end = re_match.start(), re_match.end()
                if m_end == m_start:
                    # Skip zero-width regex matches (e.g. r"\b") — they
                    # can't be replaced and would loop forever.
                    continue
                pieces = _spans_for_range(spans, m_start, m_end)
                if not pieces:
                    continue
                first_span, first_local_start, first_local_end = pieces[0]
                extra: list[tuple[int, int, int]] = [
                    (sp.run_index, ls, le) for sp, ls, le in pieces[1:]
                ]
                results.append(
                    Match(
                        story_id=story.id,
                        block_id=block.id,
                        run_index=first_span.run_index,
                        char_start=first_local_start,
                        char_end=first_local_end,
                        extra_runs=tuple(extra),
                    )
                )
    return results


def replace_all(
    doc: Document,
    matches: list[Match],
    replacement: str,
) -> MacroCommand:
    """Build the undoable replacement macro for `matches`.

    The replacement string is inserted in full at the *start* of the match
    (in the first run), and any extra-run pieces are deleted. This keeps
    the operation undoable as a single macro and avoids splitting the
    replacement arbitrarily across runs.

    The caller is responsible for pushing the returned `MacroCommand` onto
    the undo stack — the engine does not mutate `doc` directly.
    """
    cdoc = cast(CommandDocument, doc)
    children: list[Command] = []

    # Group matches by (story_id, block_id) so we can apply per-block from
    # the *end* — that way earlier offsets don't shift under our feet.
    by_block: dict[tuple[str, str], list[Match]] = {}
    for match in matches:
        by_block.setdefault((match.story_id, match.block_id), []).append(match)

    for (story_id, block_id), block_matches in by_block.items():
        story = doc.find_story(story_id)
        if story is None:
            continue
        block = _find_text_block(story.blocks, block_id)
        if block is None:
            continue
        # Apply right-to-left within the block so prior offsets stay valid.
        block_matches.sort(key=lambda m: (m.run_index, m.char_start), reverse=True)
        for match in block_matches:
            children.extend(_commands_for_match(cdoc, block, match, replacement))

    return MacroCommand(cdoc, children, text=f"Replace {len(matches)} match(es)")


def _find_text_block(blocks: list[Any], block_id: str) -> Any | None:
    """Locate the text-bearing block whose `id == block_id` anywhere in the tree."""
    for block in _iter_text_blocks(blocks):
        if block.id == block_id:
            return block
    return None


def _commands_for_match(
    doc: CommandDocument, block: Any, match: Match, replacement: str
) -> list[Command]:
    """Translate a Match into per-run ReplaceTextInRunCommands.

    Strategy:
      * The first run gets `replacement` substituted in at
        `[char_start, char_end)`.
      * Each extra run has its covered slice deleted (replacement="").
    Right-to-left iteration over a block keeps offsets stable across calls.
    """
    cmds: list[Command] = []
    if match.run_index >= len(block.runs):
        return cmds
    cmds.append(
        ReplaceTextInRunCommand(
            doc,
            block,
            match.run_index,
            match.char_start,
            match.char_end,
            replacement,
        )
    )
    # Process extras in reverse so deletions don't shift earlier extras.
    for run_index, lo, hi in reversed(match.extra_runs):
        if run_index >= len(block.runs):
            continue
        cmds.append(
            ReplaceTextInRunCommand(
                doc,
                block,
                run_index,
                lo,
                hi,
                "",
            )
        )
    return cmds


__all__ = ["Match", "Scope", "find_all", "replace_all"]
