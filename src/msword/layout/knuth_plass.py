"""Knuth-Plass optimal line-breaking for paragraph composition.

Pure-Python implementation of the dynamic-programming line-breaking algorithm
from Knuth & Plass, "Breaking Paragraphs into Lines" (1981). Used as an opt-in
alternative to the greedy line-breaker driven by ``QTextLayout``.

The classic three item kinds are:

* :class:`Box`     - inseparable content (a glyph cluster, a word, etc.).
* :class:`Glue`    - stretchable / shrinkable whitespace between boxes.
* :class:`Penalty` - a candidate breakpoint with an associated cost.

A :class:`Breakpoint` records the optimal predecessor for a given item index
under a particular fitness class.  After running the active-list DP,
:func:`find_breakpoints` walks the chain back to produce the list of item
indices at which to break the paragraph.

This module is intentionally framework-free: it knows nothing about Qt, fonts,
or shaping.  Callers project their own width information through the protocol
:class:`FontMetricsProto` (anything implementing ``width(s) -> float`` works).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

__all__ = [
    "INFINITY",
    "Box",
    "Breakpoint",
    "FontMetricsProto",
    "Glue",
    "Item",
    "Penalty",
    "find_breakpoints",
    "paragraph_to_items",
]


# A penalty value greater than or equal to this is treated as a forbidden break;
# a value less than or equal to ``-INFINITY`` is treated as a forced break.
INFINITY: float = 10_000.0


@dataclass(frozen=True)
class Box:
    """An inseparable run of content of fixed width."""

    width: float
    char: str = ""


@dataclass(frozen=True)
class Glue:
    """Stretchable / shrinkable whitespace.

    ``stretch`` and ``shrink`` are non-negative.  At an adjustment ratio ``r``
    the glue's effective width is ``width + r*stretch`` (when ``r >= 0``) or
    ``width + r*shrink`` (when ``r < 0``).
    """

    width: float
    stretch: float = 0.0
    shrink: float = 0.0


@dataclass(frozen=True)
class Penalty:
    """A candidate (or forced) break with an associated cost.

    * ``penalty <= -INFINITY`` is a forced break.
    * ``penalty >=  INFINITY`` forbids breaking here.
    * ``flagged`` items add ``flagged_demerit`` when two such breaks are
      consecutive (Knuth-Plass discourages two hyphenated lines in a row).
    """

    width: float
    penalty: float
    flagged: bool = False


Item = Box | Glue | Penalty


class FontMetricsProto(Protocol):
    """Anything that can measure the typeset width of a string."""

    def width(self, s: str) -> float:  # pragma: no cover - protocol
        ...


@dataclass
class Breakpoint:
    """A node in the active list / final break chain.

    ``previous`` points at the optimal predecessor; ``None`` marks the
    paragraph start.  All ``total_*`` fields are running sums *up to* this
    item, used to cheaply compute the adjustment ratio of any candidate line
    starting at the next item.
    """

    position: int
    line: int
    fitness_class: int  # 0..3, per Knuth-Plass
    total_width: float
    total_stretch: float
    total_shrink: float
    total_demerits: float
    previous: Breakpoint | None = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_forced_break(item: Item) -> bool:
    return isinstance(item, Penalty) and item.penalty <= -INFINITY


def _is_feasible_break(items: list[Item], i: int) -> bool:
    """Knuth-Plass break-legality predicate at item index ``i``."""
    item = items[i]
    if isinstance(item, Penalty):
        return item.penalty < INFINITY
    if isinstance(item, Glue):
        # Glue is a legal break only if preceded by a Box.
        return i > 0 and isinstance(items[i - 1], Box)
    return False


def _line_width(line_widths: list[float] | float, line: int) -> float:
    if isinstance(line_widths, (int, float)):
        return float(line_widths)
    if line < len(line_widths):
        return float(line_widths[line])
    return float(line_widths[-1])


def _compute_sums(items: list[Item]) -> list[tuple[float, float, float]]:
    """Prefix sums of (width, stretch, shrink) up to *and including* index k.

    Penalties contribute nothing to the running totals; their width is added
    only at the candidate break itself in :func:`_measure_line`.
    """
    sums: list[tuple[float, float, float]] = []
    w = st = sh = 0.0
    for item in items:
        if isinstance(item, Box):
            w += item.width
        elif isinstance(item, Glue):
            w += item.width
            st += item.stretch
            sh += item.shrink
        sums.append((w, st, sh))
    return sums


def _measure_line(
    items: list[Item],
    sums: list[tuple[float, float, float]],
    a: int,
    b: int,
) -> tuple[float, float, float]:
    """Line measurement from break point ``a`` to break point ``b``.

    Glue immediately after the previous break is dropped (``a+1`` is where
    the new line starts) and a trailing ``Penalty`` at ``b`` contributes only
    its width (its stretch/shrink are zero by construction).
    """
    # Width up to and including item b.
    if b < 0:
        wb = stb = shb = 0.0
    else:
        wb, stb, shb = sums[b]
    # Width up to and including item a (i.e. the prior break point).
    if a < 0:
        wa = sta = sha = 0.0
    else:
        wa, sta, sha = sums[a]
    width = wb - wa
    stretch = stb - sta
    shrink = shb - sha
    # If the candidate break b is a Penalty, add its width (penalties don't
    # accumulate in the prefix sums).
    if 0 <= b < len(items):
        item_b = items[b]
        if isinstance(item_b, Penalty):
            width += item_b.width
    return width, stretch, shrink


def _adjustment_ratio(
    line_w: float, width: float, stretch: float, shrink: float
) -> float:
    diff = line_w - width
    if diff > 0:
        if stretch > 0:
            return diff / stretch
        return INFINITY  # line is short and cannot stretch
    if diff < 0:
        if shrink > 0:
            return diff / shrink
        return -INFINITY  # line is long and cannot shrink
    return 0.0


def _fitness_class(r: float) -> int:
    """Knuth-Plass four-bucket classification of adjustment ratios."""
    if r < -0.5:
        return 0  # tight
    if r <= 0.5:
        return 1  # normal
    if r <= 1.0:
        return 2  # loose
    return 3  # very loose


def _badness(r: float) -> float:
    """Knuth-Plass badness function (scaled cube of the adjustment ratio)."""
    if r < -1:
        return INFINITY
    return 100.0 * abs(r) ** 3


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------


def _find_breakpoints_at_tolerance(
    items: list[Item],
    line_widths: list[float] | float,
    tolerance: float,
    fit_diff_demerit: float,
    flagged_demerit: float,
    line_penalty: float,
) -> Breakpoint | None:
    """Single-pass active-list DP.  Returns the best terminal node, or ``None``."""
    if not items:
        return None

    sums = _compute_sums(items)

    # The active list seeds with a synthetic "before-the-paragraph" node.
    start = Breakpoint(
        position=-1,
        line=0,
        fitness_class=1,
        total_width=0.0,
        total_stretch=0.0,
        total_shrink=0.0,
        total_demerits=0.0,
        previous=None,
    )
    active: list[Breakpoint] = [start]
    best_terminal: Breakpoint | None = None

    for b in range(len(items)):
        if not _is_feasible_break(items, b):
            continue
        item_b = items[b]

        # Best-of-fitness-class buckets, refreshed for *every* break candidate.
        # (This keeps multiple equally-good predecessors instead of only one.)
        candidates: list[tuple[Breakpoint, float, int]] = []  # (active, demerits, fc)

        # Iterate over a snapshot so we can mutate `active` mid-loop.
        for a in list(active):
            line_no = a.line + 1
            line_w = _line_width(line_widths, line_no - 1)
            width, stretch, shrink = _measure_line(items, sums, a.position, b)
            r = _adjustment_ratio(line_w, width, stretch, shrink)

            # Drop any active node that can no longer reach a feasible break:
            # the line is so over-long that even shrinking can't help, *or* we
            # encountered a forced break.
            if (r < -1 or _is_forced_break(item_b)) and a in active:
                active.remove(a)

            if -1 <= r <= tolerance:
                # Compute demerits.
                p_pen = item_b.penalty if isinstance(item_b, Penalty) else 0.0
                bad = _badness(r)
                if p_pen >= 0:
                    base = (line_penalty + bad + p_pen) ** 2
                elif p_pen > -INFINITY:
                    base = (line_penalty + bad) ** 2 - p_pen * p_pen
                else:
                    base = (line_penalty + bad) ** 2

                # Flagged-pair demerit (two consecutive flagged Penalties).
                prev_item = items[a.position] if a.position >= 0 else None
                if (
                    isinstance(item_b, Penalty)
                    and item_b.flagged
                    and isinstance(prev_item, Penalty)
                    and prev_item.flagged
                ):
                    base += flagged_demerit

                fc = _fitness_class(r)
                if abs(fc - a.fitness_class) > 1:
                    base += fit_diff_demerit

                total = a.total_demerits + base
                candidates.append((a, total, fc))

        if candidates:
            # For each fitness class keep only the best predecessor.
            by_fc: dict[int, tuple[Breakpoint, float, int]] = {}
            for a, total, fc in candidates:
                if fc not in by_fc or total < by_fc[fc][1]:
                    by_fc[fc] = (a, total, fc)

            # Cumulative measurements at this break for the new active node.
            wb, stb, shb = sums[b]
            new_nodes: list[Breakpoint] = []
            for a, total, fc in by_fc.values():
                node = Breakpoint(
                    position=b,
                    line=a.line + 1,
                    fitness_class=fc,
                    total_width=wb,
                    total_stretch=stb,
                    total_shrink=shb,
                    total_demerits=total,
                    previous=a,
                )
                new_nodes.append(node)
                if b == len(items) - 1 and (
                    best_terminal is None or total < best_terminal.total_demerits
                ):
                    best_terminal = node

            if _is_forced_break(item_b):
                # A mid-paragraph forced break terminates all prior in-flight
                # active nodes; the new nodes (which all end at this break)
                # become the only continuations.
                active = new_nodes
            else:
                active.extend(new_nodes)

        if not active:
            return None

    if best_terminal is None:
        # Pick the cheapest still-active node as the terminal.
        active.sort(key=lambda n: n.total_demerits)
        if active and active[0].position >= 0:
            best_terminal = active[0]
    return best_terminal


def find_breakpoints(
    items: list[Item],
    line_widths: list[float] | float,
    *,
    tolerance: float = 1.0,
    fit_diff_demerit: float = 100,
    flagged_demerit: float = 100,
    line_penalty: float = 10,
) -> list[int]:
    """Compute optimal line-break positions for ``items``.

    Returns a list of indices into ``items`` at which the paragraph should
    break.  If no feasible solution exists at the requested ``tolerance`` we
    automatically escalate (1, 4, 10, +inf) before giving up and emitting the
    natural break (the final item).

    ``line_widths`` may be a scalar (uniform) or a per-line list (the last
    entry is used for any further lines).
    """
    if not items:
        return []

    tolerances = [tolerance, max(tolerance * 4.0, 4.0), 10.0, INFINITY]
    seen: set[float] = set()
    for tol in tolerances:
        if tol in seen:
            continue
        seen.add(tol)
        terminal = _find_breakpoints_at_tolerance(
            items,
            line_widths,
            tol,
            fit_diff_demerit,
            flagged_demerit,
            line_penalty,
        )
        if terminal is not None:
            chain: list[int] = []
            node: Breakpoint | None = terminal
            while node is not None and node.position >= 0:
                chain.append(node.position)
                node = node.previous
            chain.reverse()
            return chain

    # Total fallback: a single break at the last item.
    return [len(items) - 1]


# ---------------------------------------------------------------------------
# Convenience: paragraph -> item stream
# ---------------------------------------------------------------------------


def paragraph_to_items(text: str, font_metrics: FontMetricsProto) -> list[Item]:
    """Tokenise ``text`` into a Knuth-Plass item stream.

    Conventions:

    * Spaces become :class:`Glue` with ``stretch = space/3``, ``shrink = space/6``.
    * ``\\n`` becomes a forced break (penalty :class:`Penalty` of ``-INFINITY``)
      preceded by a finishing infinite-stretch glue, per Knuth-Plass.
    * ``-`` becomes a flagged :class:`Penalty` (cost ``50``) immediately after
      its host word, marking the soft hyphen as a candidate break.
    * Every other character is a :class:`Box` of its measured width.

    The stream is terminated with the conventional finishing glue + forced
    Penalty so the algorithm always sees a sentinel break.
    """
    items: list[Item] = []
    space_w = font_metrics.width(" ")
    hyphen_w = font_metrics.width("-")
    glue = Glue(width=space_w, stretch=space_w / 3.0, shrink=space_w / 6.0)
    finishing_glue = Glue(width=0.0, stretch=INFINITY, shrink=0.0)
    forced_break = Penalty(width=0.0, penalty=-INFINITY, flagged=False)

    for ch in text:
        if ch == "\n":
            items.append(finishing_glue)
            items.append(forced_break)
        elif ch == " ":
            items.append(glue)
        elif ch == "-":
            items.append(Box(width=hyphen_w, char="-"))
            items.append(Penalty(width=0.0, penalty=50, flagged=True))
        else:
            items.append(Box(width=font_metrics.width(ch), char=ch))

    # Always finish with a sentinel so the last line has a forced break.
    if not items or not _is_forced_break(items[-1]):
        items.append(finishing_glue)
        items.append(forced_break)
    return items
