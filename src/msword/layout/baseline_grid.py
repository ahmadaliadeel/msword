"""Baseline grid model and snapping helpers.

A baseline grid is a uniformly spaced set of horizontal positions (Y coordinates,
typically in points) used by professional layout engines to align the baselines
of paragraphs across columns and pages. When a paragraph style has the
"align to baseline grid" flag enabled, the layout pipeline (per spec §5) calls
into here to adjust line baselines onto the nearest grid position.

This module is intentionally pure-Python and Qt-free; layout consumers convert
between their internal units (px, EMU, etc.) and points before/after calling.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from math import floor


class BaselineSnapOverflowError(Exception):
    """Raised when snapping a baseline sequence overshoots the allowed budget.

    The caller (frame composer) is expected to catch this and fall back to
    greedy positioning for the affected paragraph rather than push subsequent
    content off the page.
    """


@dataclass(slots=True, frozen=True)
class BaselineGrid:
    """A uniformly spaced baseline grid.

    Attributes:
        origin_pt: Y position (in points, relative to page top) of the first
            grid line. Grid lines exist at ``origin_pt + k * increment_pt`` for
            every integer ``k`` (negative as well as non-negative).
        increment_pt: Spacing between consecutive grid lines, in points. Must
            be strictly positive.
    """

    origin_pt: float
    increment_pt: float

    def __post_init__(self) -> None:
        if self.increment_pt <= 0:
            raise ValueError(
                f"BaselineGrid.increment_pt must be > 0; got {self.increment_pt!r}"
            )

    def nearest(self, y: float) -> float:
        """Return the grid Y closest to ``y`` (ties round up to the next line)."""
        offset = y - self.origin_pt
        k = floor(offset / self.increment_pt + 0.5)
        return self.origin_pt + k * self.increment_pt

    def next_at_or_after(self, y: float) -> float:
        """Return the smallest grid Y that is >= ``y``."""
        offset = y - self.origin_pt
        k = -floor(-offset / self.increment_pt)
        return self.origin_pt + k * self.increment_pt

    def iter_in_range(self, y_min: float, y_max: float) -> Iterator[float]:
        """Yield every grid Y in the closed range ``[y_min, y_max]`` in order."""
        if y_max < y_min:
            return
        # Compute the integer index of the first grid line in range, then derive
        # each Y by multiplication to avoid float-error accumulation across long
        # ranges (incremental += would drift over thousands of lines).
        offset = y_min - self.origin_pt
        k_start = -floor(-offset / self.increment_pt)
        k = k_start
        while True:
            y = self.origin_pt + k * self.increment_pt
            if y > y_max:
                return
            yield y
            k += 1


def snap_baselines_to_grid(
    baselines: Sequence[float],
    grid: BaselineGrid,
    *,
    max_overshoot_pt: float = 0.0,
) -> list[float]:
    """Snap each baseline forward onto ``grid``, preserving monotonicity.

    Args:
        baselines: Original line baselines (Y positions, in order, in points).
        grid: The baseline grid.
        max_overshoot_pt: If > 0, raise :class:`BaselineSnapOverflowError` when
            the last snapped baseline exceeds the original last baseline by
            more than this many points. (0 disables the check.)

    Returns:
        New baselines, one per input, each on a grid line, monotonically
        increasing by at least ``grid.increment_pt``.

    Raises:
        BaselineSnapOverflowError: If ``max_overshoot_pt > 0`` and the snap
            pushes the final baseline past ``baselines[-1] + max_overshoot_pt``.
    """
    if not baselines:
        return []

    snapped: list[float] = []
    prev: float | None = None
    for original in baselines:
        candidate = grid.next_at_or_after(original)
        if prev is not None:
            min_allowed = prev + grid.increment_pt
            if candidate < min_allowed:
                candidate = grid.next_at_or_after(min_allowed)
        snapped.append(candidate)
        prev = candidate

    if max_overshoot_pt > 0:
        overshoot = snapped[-1] - baselines[-1]
        if overshoot > max_overshoot_pt:
            raise BaselineSnapOverflowError(
                f"baseline snap overshoot {overshoot:.3f}pt exceeds "
                f"budget {max_overshoot_pt:.3f}pt"
            )

    return snapped


def compute_grid_for_column(
    column_top: float,
    column_bottom: float,
    leading_pt: float,
) -> BaselineGrid:
    """Pick a sensible grid origin/increment for a column when none is set.

    The first grid line sits one leading below the column top (so the first
    line of text has its baseline at ``column_top + leading_pt``), and grid
    lines repeat every ``leading_pt`` thereafter.

    Args:
        column_top: Y of the column's top edge.
        column_bottom: Y of the column's bottom edge (must be > ``column_top``).
        leading_pt: Line leading in points (must be > 0).

    Returns:
        A :class:`BaselineGrid`.
    """
    if leading_pt <= 0:
        raise ValueError(f"leading_pt must be > 0; got {leading_pt!r}")
    if column_bottom <= column_top:
        raise ValueError(
            f"column_bottom ({column_bottom!r}) must be > column_top ({column_top!r})"
        )
    return BaselineGrid(origin_pt=column_top + leading_pt, increment_pt=leading_pt)


__all__ = [
    "BaselineGrid",
    "BaselineSnapOverflowError",
    "compute_grid_for_column",
    "snap_baselines_to_grid",
]
