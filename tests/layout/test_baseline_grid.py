"""Tests for the baseline grid model and snapping helpers (unit 15)."""

from __future__ import annotations

import pytest

from msword.layout.baseline_grid import (
    BaselineGrid,
    BaselineSnapOverflowError,
    compute_grid_for_column,
    snap_baselines_to_grid,
)

# --------------------------------------------------------------------------- #
# BaselineGrid.nearest
# --------------------------------------------------------------------------- #


def test_nearest_rounds_down_when_closer_to_lower_line() -> None:
    assert BaselineGrid(0, 12).nearest(13) == 12


def test_nearest_rounds_up_when_closer_to_upper_line() -> None:
    assert BaselineGrid(0, 12).nearest(18.1) == 24


def test_nearest_exact_grid_line_is_idempotent() -> None:
    assert BaselineGrid(0, 12).nearest(12) == 12
    assert BaselineGrid(0, 12).nearest(0) == 0


def test_nearest_respects_origin_offset() -> None:
    # Grid lines: 5, 17, 29, 41, ...
    grid = BaselineGrid(origin_pt=5, increment_pt=12)
    assert grid.nearest(5) == 5
    assert grid.nearest(10) == 5  # closer to 5 than to 17
    assert grid.nearest(12) == 17  # 12 - 5 = 7 vs 17 - 12 = 5 → 17 closer


def test_nearest_handles_negative_y() -> None:
    # Grid lines: ..., -24, -12, 0, 12, ...
    grid = BaselineGrid(0, 12)
    assert grid.nearest(-5) == 0  # closer to 0 than to -12
    assert grid.nearest(-7) == -12


# --------------------------------------------------------------------------- #
# BaselineGrid.next_at_or_after
# --------------------------------------------------------------------------- #


def test_next_at_or_after_returns_y_when_y_is_on_grid() -> None:
    assert BaselineGrid(0, 12).next_at_or_after(12) == 12


def test_next_at_or_after_returns_next_line_when_y_off_grid() -> None:
    assert BaselineGrid(0, 12).next_at_or_after(13) == 24


def test_next_at_or_after_handles_origin_offset() -> None:
    grid = BaselineGrid(origin_pt=5, increment_pt=12)
    assert grid.next_at_or_after(5) == 5
    assert grid.next_at_or_after(6) == 17
    assert grid.next_at_or_after(17) == 17


def test_next_at_or_after_handles_below_origin() -> None:
    grid = BaselineGrid(origin_pt=0, increment_pt=12)
    assert grid.next_at_or_after(-5) == 0
    assert grid.next_at_or_after(-12) == -12
    assert grid.next_at_or_after(-13) == -12


# --------------------------------------------------------------------------- #
# BaselineGrid.iter_in_range
# --------------------------------------------------------------------------- #


def test_iter_in_range_basic() -> None:
    grid = BaselineGrid(0, 12)
    assert list(grid.iter_in_range(0, 50)) == [0, 12, 24, 36, 48]


def test_iter_in_range_inclusive_at_endpoints() -> None:
    grid = BaselineGrid(0, 12)
    assert list(grid.iter_in_range(12, 36)) == [12, 24, 36]


def test_iter_in_range_starts_at_first_grid_line_at_or_after_y_min() -> None:
    grid = BaselineGrid(0, 12)
    assert list(grid.iter_in_range(1, 25)) == [12, 24]


def test_iter_in_range_empty_when_max_below_min() -> None:
    grid = BaselineGrid(0, 12)
    assert list(grid.iter_in_range(50, 0)) == []


def test_iter_in_range_empty_when_no_grid_lines_in_range() -> None:
    grid = BaselineGrid(0, 12)
    # Between 13 and 23 the only candidate would be 12 (excluded) or 24 (excluded).
    assert list(grid.iter_in_range(13, 23)) == []


def test_iter_in_range_with_origin_offset() -> None:
    # Grid lines: 5, 17, 29, 41
    grid = BaselineGrid(origin_pt=5, increment_pt=12)
    assert list(grid.iter_in_range(0, 45)) == [5, 17, 29, 41]


# --------------------------------------------------------------------------- #
# snap_baselines_to_grid
# --------------------------------------------------------------------------- #


def test_snap_baselines_basic() -> None:
    grid = BaselineGrid(0, 12)
    assert snap_baselines_to_grid([10, 22, 38], grid) == [12, 24, 48]


def test_snap_preserves_monotonicity_when_two_lines_would_collide() -> None:
    # [11, 13] both want grid line 12; the second must be pushed to 24.
    grid = BaselineGrid(0, 12)
    assert snap_baselines_to_grid([11, 13], grid) == [12, 24]


def test_snap_already_on_grid_is_noop() -> None:
    grid = BaselineGrid(0, 12)
    assert snap_baselines_to_grid([12, 24, 36], grid) == [12, 24, 36]


def test_snap_empty_input_returns_empty_list() -> None:
    grid = BaselineGrid(0, 12)
    assert snap_baselines_to_grid([], grid) == []


def test_snap_overshoot_within_budget_succeeds() -> None:
    grid = BaselineGrid(0, 12)
    # [10, 22] → [12, 24]; original last 22, snapped last 24, overshoot = 2.
    assert snap_baselines_to_grid([10, 22], grid, max_overshoot_pt=2.0) == [12, 24]


def test_snap_overshoot_exceeds_budget_raises() -> None:
    grid = BaselineGrid(0, 12)
    # overshoot = 24 - 22 = 2pt; budget = 1pt → overflow.
    with pytest.raises(BaselineSnapOverflowError):
        snap_baselines_to_grid([10, 22], grid, max_overshoot_pt=1.0)


def test_snap_zero_max_overshoot_disables_check() -> None:
    # max_overshoot_pt == 0 is the default and means "no check".
    grid = BaselineGrid(0, 12)
    assert snap_baselines_to_grid([10, 22], grid, max_overshoot_pt=0.0) == [12, 24]


def test_snap_long_run_with_collisions_pushes_each_forward() -> None:
    grid = BaselineGrid(0, 12)
    # All three want 12, must end up at 12, 24, 36.
    assert snap_baselines_to_grid([11, 11.5, 11.7], grid) == [12, 24, 36]


def test_snap_with_origin_offset_grid() -> None:
    # Grid lines: 5, 17, 29
    grid = BaselineGrid(origin_pt=5, increment_pt=12)
    assert snap_baselines_to_grid([6, 18, 30], grid) == [17, 29, 41]


# --------------------------------------------------------------------------- #
# BaselineGrid validation
# --------------------------------------------------------------------------- #


def test_baseline_grid_rejects_zero_increment() -> None:
    with pytest.raises(ValueError):
        BaselineGrid(0, 0)


def test_baseline_grid_rejects_negative_increment() -> None:
    with pytest.raises(ValueError):
        BaselineGrid(0, -1)


def test_baseline_grid_is_frozen() -> None:
    grid = BaselineGrid(0, 12)
    with pytest.raises((AttributeError, TypeError)):
        grid.increment_pt = 10  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# compute_grid_for_column
# --------------------------------------------------------------------------- #


def test_compute_grid_for_column_origin_is_top_plus_leading() -> None:
    grid = compute_grid_for_column(column_top=72, column_bottom=720, leading_pt=14)
    assert grid.origin_pt == 86  # 72 + 14
    assert grid.increment_pt == 14


def test_compute_grid_for_column_rejects_non_positive_leading() -> None:
    with pytest.raises(ValueError):
        compute_grid_for_column(column_top=0, column_bottom=100, leading_pt=0)
    with pytest.raises(ValueError):
        compute_grid_for_column(column_top=0, column_bottom=100, leading_pt=-1)


def test_compute_grid_for_column_rejects_inverted_column() -> None:
    with pytest.raises(ValueError):
        compute_grid_for_column(column_top=100, column_bottom=50, leading_pt=12)
    with pytest.raises(ValueError):
        compute_grid_for_column(column_top=100, column_bottom=100, leading_pt=12)
