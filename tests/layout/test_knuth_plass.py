"""Tests for the Knuth-Plass paragraph composer."""

from __future__ import annotations

import time

from msword.layout.knuth_plass import (
    INFINITY,
    Box,
    Breakpoint,
    Glue,
    Penalty,
    find_breakpoints,
    paragraph_to_items,
)


class FixedMetrics:
    """Every glyph has the same width.  Handy as a deterministic test fixture."""

    def __init__(self, char_width: float) -> None:
        self.char_width = char_width

    def width(self, s: str) -> float:
        return float(self.char_width * len(s))


def _line_text(items: list[object], a: int, b: int) -> str:
    chars: list[str] = []
    for k in range(a, b + 1):
        item = items[k]
        if isinstance(item, Box):
            chars.append(item.char)
        elif isinstance(item, Glue):
            chars.append(" ")
    return "".join(chars).strip()


def test_quick_brown_fox_breaks_into_three_lines() -> None:
    metrics = FixedMetrics(char_width=10.0)
    text = "The quick brown fox jumps"
    items = paragraph_to_items(text, metrics)

    breaks = find_breakpoints(items, line_widths=100.0, tolerance=2.0)

    # Sanity: at 100px line width with 10px chars, "The quick" (9 chars + space)
    # fits, then "brown fox" fits, then "jumps" finishes the paragraph.
    lines: list[str] = []
    prev = -1
    for bp in breaks:
        lines.append(_line_text(items, prev + 1, bp))
        prev = bp
    # Drop empty lines (the sentinel forced break sits after a 0-width glue).
    lines = [line for line in lines if line]

    assert lines == ["The quick", "brown fox", "jumps"]


def test_forced_break_at_newline() -> None:
    metrics = FixedMetrics(char_width=10.0)
    text = "hello\nworld"
    items = paragraph_to_items(text, metrics)

    breaks = find_breakpoints(items, line_widths=200.0, tolerance=2.0)

    lines: list[str] = []
    prev = -1
    for bp in breaks:
        chunk = _line_text(items, prev + 1, bp)
        if chunk:
            lines.append(chunk)
        prev = bp

    assert lines == ["hello", "world"]


def test_tolerance_escalates_for_too_wide_word() -> None:
    """A single word wider than the line forces tolerance escalation."""
    metrics = FixedMetrics(char_width=10.0)
    # 'unbreakableword' is 15 chars at 10px each = 150 px, but line is 80.
    items = paragraph_to_items("hi unbreakableword end", metrics)

    breaks = find_breakpoints(items, line_widths=80.0, tolerance=1.0)

    # We must get *some* result back even though strict tolerance fails.
    assert breaks, "tolerance escalation should still produce break positions"
    # And the final break covers the whole paragraph.
    assert breaks[-1] == len(items) - 1


def test_thousand_word_paragraph_under_50ms() -> None:
    metrics = FixedMetrics(char_width=8.0)
    word = "lorem"
    text = " ".join([word] * 1000)
    items = paragraph_to_items(text, metrics)

    start = time.perf_counter()
    breaks = find_breakpoints(items, line_widths=400.0, tolerance=2.0)
    elapsed = time.perf_counter() - start

    assert breaks, "must produce breaks"
    assert elapsed < 0.050, f"Knuth-Plass too slow: {elapsed * 1000:.2f} ms"


def test_breakpoints_chain_back_to_paragraph_start() -> None:
    metrics = FixedMetrics(char_width=10.0)
    items = paragraph_to_items("alpha beta gamma delta epsilon", metrics)

    breaks = find_breakpoints(items, line_widths=120.0, tolerance=2.0)

    assert breaks
    # Each break index is in range and strictly increasing.
    last = -1
    for bp in breaks:
        assert 0 <= bp < len(items)
        assert bp > last
        last = bp


def test_empty_input_returns_empty_breaks() -> None:
    assert find_breakpoints([], line_widths=100.0) == []


def test_breakpoint_dataclass_fields() -> None:
    """Spec requires a specific shape for Breakpoint."""
    bp = Breakpoint(
        position=3,
        line=1,
        fitness_class=1,
        total_width=10.0,
        total_stretch=2.0,
        total_shrink=1.0,
        total_demerits=42.0,
        previous=None,
    )
    assert bp.position == 3
    assert bp.line == 1
    assert 0 <= bp.fitness_class <= 3
    assert bp.previous is None


def test_glue_and_penalty_construction() -> None:
    """Item types accept the documented constructor signatures."""
    box = Box(width=10.0, char="x")
    glue = Glue(width=5.0, stretch=2.0, shrink=1.0)
    pen = Penalty(width=0.0, penalty=-INFINITY, flagged=False)
    assert box.char == "x"
    assert glue.stretch == 2.0
    assert pen.penalty <= -INFINITY


def test_per_line_widths_supported() -> None:
    """A list of per-line widths is honoured."""
    metrics = FixedMetrics(char_width=10.0)
    items = paragraph_to_items("aaaa bbbb cccc dddd", metrics)

    # First line short, then wider.
    breaks = find_breakpoints(items, line_widths=[40.0, 200.0], tolerance=3.0)
    assert breaks
    assert breaks[-1] == len(items) - 1
