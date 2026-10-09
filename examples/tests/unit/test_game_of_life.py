# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0

#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for the Conway's Game of Life core business logic.

Expectations are derived from the rules and the pattern catalogue of Conway's
Game of Life, not from the current behaviour of the module under test. A naive
reference implementation (:func:`reference_next_generation`) is used as an
independent oracle for the vectorized engine.
"""

from typing import Optional

import numpy as np
import pytest

from saf.solutions.examples.solution.logic.game_of_life import (
    GameOfLifeEngine,
    Pattern,
    PatternCategory,
    PatternLibrary,
    SimulationController,
    SimulationState,
)

# =================================================== [Constants] =================================================== #

#: Every pattern the library is expected to expose, with its category.
#: The catalogue holds evolving patterns only; still lives are deliberately absent.
EXPECTED_PATTERNS = {
    "blinker": PatternCategory.OSCILLATOR,
    "toad": PatternCategory.OSCILLATOR,
    "beacon": PatternCategory.OSCILLATOR,
    "pulsar": PatternCategory.OSCILLATOR,
    "glider": PatternCategory.SPACESHIP,
    "lwss": PatternCategory.SPACESHIP,
    "gosper_glider_gun": PatternCategory.SPACESHIP,
}

OSCILLATOR_NAMES = sorted(name for name, cat in EXPECTED_PATTERNS.items() if cat is PatternCategory.OSCILLATOR)
SPACESHIP_NAMES = sorted(name for name, cat in EXPECTED_PATTERNS.items() if cat is PatternCategory.SPACESHIP)
ALL_PATTERN_NAMES = sorted(EXPECTED_PATTERNS)

#: Grid size used by ``GameOfLifeStep``; small enough to expose clipping issues.
BACKEND_GRID_SIZE = (20, 20)

# ==================================================== [Helpers] ==================================================== #


def reference_next_generation(grid: np.ndarray) -> np.ndarray:
    """Compute the next generation with a naive, independent implementation.

    Serves as the test oracle for the vectorized engine. Cells outside the grid
    are considered permanently dead (no wrap-around).

    Parameters
    ----------
    grid : np.ndarray
        Current grid state.

    Returns
    -------
    np.ndarray
        Next generation of the grid.
    """
    rows, cols = grid.shape
    next_grid = np.zeros_like(grid, dtype=np.int8)

    for row in range(rows):
        for col in range(cols):
            neighbors = 0
            for delta_row in (-1, 0, 1):
                for delta_col in (-1, 0, 1):
                    if delta_row == 0 and delta_col == 0:
                        continue
                    neighbor_row, neighbor_col = row + delta_row, col + delta_col
                    if 0 <= neighbor_row < rows and 0 <= neighbor_col < cols:
                        neighbors += int(grid[neighbor_row, neighbor_col])
            alive = grid[row, col] == 1
            next_grid[row, col] = 1 if neighbors == 3 or (alive and neighbors == 2) else 0

    return next_grid


def live_cell_set(grid: np.ndarray) -> set:
    """Return the coordinates of the live cells of ``grid``."""
    return {(int(row), int(col)) for row, col in zip(*np.nonzero(grid))}


def translation_offset(before: np.ndarray, after: np.ndarray) -> Optional[tuple]:
    """Return the ``(row, col)`` shift if ``after`` is a pure translation of ``before``.

    Parameters
    ----------
    before : np.ndarray
        Grid state at the beginning of the observation window.
    after : np.ndarray
        Grid state at the end of the observation window.

    Returns
    -------
    Optional[tuple]
        The translation vector, or ``None`` if ``after`` is not a rigid
        translation of ``before``.
    """
    cells_before, cells_after = live_cell_set(before), live_cell_set(after)
    if not cells_before or len(cells_before) != len(cells_after):
        return None

    delta_row = min(row for row, _ in cells_after) - min(row for row, _ in cells_before)
    delta_col = min(col for _, col in cells_after) - min(col for _, col in cells_before)

    shifted = {(row + delta_row, col + delta_col) for row, col in cells_before}
    return (delta_row, delta_col) if shifted == cells_after else None


def embed(pattern: np.ndarray, grid_shape: tuple, position: tuple = (5, 5)) -> np.ndarray:
    """Return a grid of ``grid_shape`` with ``pattern`` written at ``position``."""
    grid = np.zeros(grid_shape, dtype=np.int8)
    rows, cols = pattern.shape
    start_row, start_col = position
    grid[start_row : start_row + rows, start_col : start_col + cols] = pattern
    return grid


def advance(grid: np.ndarray, generations: int) -> np.ndarray:
    """Advance ``grid`` by ``generations`` steps using the engine under test."""
    for _ in range(generations):
        grid = GameOfLifeEngine.compute_next_generation(grid)
    return grid


# =================================================== [Fixtures] ==================================================== #


@pytest.fixture
def library() -> PatternLibrary:
    """Return a freshly built pattern library."""
    return PatternLibrary()


@pytest.fixture
def controller() -> SimulationController:
    """Return a controller on a small grid, initialized with a blinker."""
    simulation = SimulationController(grid_size=(10, 10))
    simulation.initialize("blinker")
    return simulation


# =========================================== [PatternCategory / Pattern] =========================================== #


def test_pattern_category_exposes_only_evolving_categories() -> None:
    """Verify the category enumeration holds no still-life category."""
    assert {category.value for category in PatternCategory} == {
        "oscillator",
        "spaceship",
        "random",
    }


def test_pattern_period_defaults_to_none() -> None:
    """Verify non-periodic patterns can be declared without a period."""
    pattern = Pattern(
        name="Glider",
        category=PatternCategory.SPACESHIP,
        description="A pattern that moves diagonally across the grid",
        pattern=np.array([[0, 1, 0], [0, 0, 1], [1, 1, 1]], dtype=np.int8),
    )

    assert pattern.period is None


def test_pattern_stores_every_field() -> None:
    """Verify the dataclass keeps all provided attributes."""
    cells = np.array([[1, 1, 1]], dtype=np.int8)

    pattern = Pattern(
        name="Blinker",
        category=PatternCategory.OSCILLATOR,
        description="A period-2 oscillator",
        pattern=cells,
        period=2,
    )

    assert pattern.name == "Blinker"
    assert pattern.category is PatternCategory.OSCILLATOR
    assert pattern.description == "A period-2 oscillator"
    assert pattern.period == 2
    np.testing.assert_array_equal(pattern.pattern, cells)


# ================================================ [PatternLibrary] ================================================= #


def test_library_exposes_exactly_the_expected_patterns(library: PatternLibrary) -> None:
    """Verify the catalogue offered to the UI."""
    assert sorted(library.get_pattern_list()) == ALL_PATTERN_NAMES


def test_get_pattern_list_does_not_expose_internal_state(library: PatternLibrary) -> None:
    """Verify mutating the returned list cannot corrupt the library."""
    returned = library.get_pattern_list()
    returned.append("not_a_pattern")

    assert "not_a_pattern" not in library.get_pattern_list()


@pytest.mark.parametrize("pattern_name", ALL_PATTERN_NAMES)
def test_get_pattern_returns_a_named_pattern(library: PatternLibrary, pattern_name: str) -> None:
    """Verify every catalogued pattern is retrievable and properly described."""
    pattern = library.get_pattern(pattern_name)

    assert isinstance(pattern, Pattern)
    assert pattern.name
    assert pattern.description
    assert pattern.category is EXPECTED_PATTERNS[pattern_name]


def test_get_pattern_raises_key_error_for_unknown_pattern(library: PatternLibrary) -> None:
    """Verify the error names the missing pattern and lists the valid ones."""
    with pytest.raises(KeyError) as error:
        library.get_pattern("spaceship_enterprise")

    message = str(error.value)
    assert "spaceship_enterprise" in message
    assert "glider" in message


@pytest.mark.parametrize("pattern_name", ALL_PATTERN_NAMES)
def test_patterns_are_two_dimensional_binary_int8_arrays(library: PatternLibrary, pattern_name: str) -> None:
    """Verify pattern payloads are well-formed and non-empty."""
    cells = library.get_pattern(pattern_name).pattern

    assert cells.ndim == 2
    assert cells.dtype == np.int8
    assert set(np.unique(cells)).issubset({0, 1})
    assert cells.sum() > 0


@pytest.mark.parametrize(
    ("category", "expected_names"),
    [
        (PatternCategory.OSCILLATOR, OSCILLATOR_NAMES),
        (PatternCategory.SPACESHIP, SPACESHIP_NAMES),
        (PatternCategory.RANDOM, []),
    ],
)
def test_get_patterns_by_category(
    library: PatternLibrary,
    category: PatternCategory,
    expected_names: list,
) -> None:
    """Verify category filtering, including the empty ``RANDOM`` category."""
    selected = library.get_patterns_by_category(category)

    assert sorted(selected) == sorted(expected_names)
    assert all(pattern.category is category for pattern in selected.values())


@pytest.mark.parametrize("pattern_name", OSCILLATOR_NAMES)
def test_oscillators_declare_a_period(library: PatternLibrary, pattern_name: str) -> None:
    """Verify oscillators expose the period the UI displays."""
    assert library.get_pattern(pattern_name).period is not None


@pytest.mark.parametrize("pattern_name", SPACESHIP_NAMES)
def test_spaceship_patterns_do_not_declare_a_period(library: PatternLibrary, pattern_name: str) -> None:
    """Verify spaceships are not advertised as oscillators."""
    assert library.get_pattern(pattern_name).period is None


def test_library_offers_no_still_life_category() -> None:
    """Verify the still-life category is gone from the enumeration."""
    assert not hasattr(PatternCategory, "STILL_LIFE")
    assert "still_life" not in {category.value for category in PatternCategory}


@pytest.mark.parametrize("pattern_name", ALL_PATTERN_NAMES)
def test_every_catalogued_pattern_belongs_to_an_evolving_category(
    library: PatternLibrary,
    pattern_name: str,
) -> None:
    """Verify only oscillators and spaceships are catalogued."""
    assert library.get_pattern(pattern_name).category in (
        PatternCategory.OSCILLATOR,
        PatternCategory.SPACESHIP,
    )


# ============================================ [Pattern dynamic behaviour] ========================================== #


@pytest.mark.parametrize("pattern_name", ALL_PATTERN_NAMES)
def test_no_catalogued_pattern_is_a_still_life(library: PatternLibrary, pattern_name: str) -> None:
    """Verify every offered pattern actually evolves, so the UI always animates."""
    grid = embed(library.get_pattern(pattern_name).pattern, (60, 90), position=(10, 10))

    assert not np.array_equal(GameOfLifeEngine.compute_next_generation(grid), grid)


@pytest.mark.parametrize("pattern_name", OSCILLATOR_NAMES)
def test_oscillators_return_to_their_initial_state_after_one_declared_period(
    library: PatternLibrary,
    pattern_name: str,
) -> None:
    """Verify each oscillator repeats itself after its declared period."""
    pattern = library.get_pattern(pattern_name)
    grid = embed(pattern.pattern, (30, 30), position=(8, 8))

    np.testing.assert_array_equal(advance(grid, pattern.period), grid)


@pytest.mark.parametrize("pattern_name", OSCILLATOR_NAMES)
def test_oscillators_do_not_repeat_before_their_declared_period(
    library: PatternLibrary,
    pattern_name: str,
) -> None:
    """Verify the declared period is the minimal one, i.e. the pattern truly moves."""
    pattern = library.get_pattern(pattern_name)
    grid = embed(pattern.pattern, (30, 30), position=(8, 8))

    current = grid
    for generation in range(1, pattern.period):
        current = GameOfLifeEngine.compute_next_generation(current)
        assert not np.array_equal(current, grid), f"repeated at generation {generation}"


def test_glider_moves_one_cell_diagonally_every_four_generations(library: PatternLibrary) -> None:
    """Verify the glider is a rigid diagonal spaceship of speed c/4."""
    grid = embed(library.get_pattern("glider").pattern, (30, 30))

    assert translation_offset(grid, advance(grid, 4)) == (1, 1)


def test_lwss_moves_two_cells_orthogonally_every_four_generations(library: PatternLibrary) -> None:
    """Verify the lightweight spaceship is a rigid orthogonal spaceship of speed c/2."""
    grid = embed(library.get_pattern("lwss").pattern, (30, 30), position=(10, 10))

    offset = translation_offset(grid, advance(grid, 4))

    assert offset is not None, "LWSS did not translate rigidly over one period"
    delta_row, delta_col = offset
    assert delta_row * delta_col == 0, f"LWSS moved diagonally by {offset}"
    assert abs(delta_row) + abs(delta_col) == 2, f"LWSS moved by {offset} instead of two cells"


def test_gosper_glider_gun_keeps_emitting_gliders(library: PatternLibrary) -> None:
    """Verify the gun releases one five-cell glider every 30 generations.

    A working Gosper glider gun has period 30 and emits a glider each period,
    so the live-cell count must keep growing while the gliders stay on the grid.
    """
    grid = embed(library.get_pattern("gosper_glider_gun").pattern, (60, 90), position=(5, 5))

    population = [int(advance(grid, generation).sum()) for generation in (0, 30, 60)]

    assert population[1] == population[0] + 5, f"no glider emitted after 30 generations: {population}"
    assert population[2] == population[0] + 10, f"no second glider emitted after 60 generations: {population}"


# ============================================= [place_pattern_on_grid] ============================================= #


def test_place_pattern_centers_the_pattern_by_default() -> None:
    """Verify a pattern with no position is centered on the grid."""
    grid = np.zeros((7, 7), dtype=np.int8)
    pattern = np.ones((3, 3), dtype=np.int8)

    result = PatternLibrary.place_pattern_on_grid(grid, pattern)

    assert live_cell_set(result) == {(row, col) for row in (2, 3, 4) for col in (2, 3, 4)}


def test_place_pattern_uses_the_requested_position() -> None:
    """Verify the position is the top-left corner of the pattern."""
    grid = np.zeros((6, 6), dtype=np.int8)
    pattern = np.array([[1, 1, 1]], dtype=np.int8)

    result = PatternLibrary.place_pattern_on_grid(grid, pattern, position=(4, 2))

    assert live_cell_set(result) == {(4, 2), (4, 3), (4, 4)}


def test_place_pattern_does_not_mutate_the_input_grid() -> None:
    """Verify the caller's grid is left untouched."""
    grid = np.zeros((5, 5), dtype=np.int8)

    PatternLibrary.place_pattern_on_grid(grid, np.ones((2, 2), dtype=np.int8), position=(0, 0))

    assert grid.sum() == 0


def test_place_pattern_keeps_live_cells_outside_the_pattern_footprint() -> None:
    """Verify placement only rewrites the region covered by the pattern."""
    grid = np.zeros((6, 6), dtype=np.int8)
    grid[5, 5] = 1

    result = PatternLibrary.place_pattern_on_grid(grid, np.ones((2, 2), dtype=np.int8), position=(0, 0))

    assert live_cell_set(result) == {(0, 0), (0, 1), (1, 0), (1, 1), (5, 5)}


def test_place_pattern_clips_a_pattern_overflowing_the_bottom_right_corner() -> None:
    """Verify the part of the pattern beyond the grid is dropped, not wrapped."""
    grid = np.zeros((4, 4), dtype=np.int8)
    pattern = np.ones((3, 3), dtype=np.int8)

    result = PatternLibrary.place_pattern_on_grid(grid, pattern, position=(3, 3))

    assert live_cell_set(result) == {(3, 3)}


def test_place_pattern_larger_than_the_grid_keeps_the_visible_window() -> None:
    """Verify an oversized pattern is centered and clipped, not silently dropped."""
    grid = np.zeros((5, 5), dtype=np.int8)
    pattern = np.array(
        [
            [1, 0, 0, 0, 0, 0, 1],
            [0, 1, 0, 1, 0, 1, 0],
            [0, 0, 1, 1, 1, 0, 0],
            [0, 1, 1, 1, 1, 1, 0],
            [0, 0, 1, 1, 1, 0, 0],
            [0, 1, 0, 1, 0, 1, 0],
            [1, 0, 0, 0, 0, 0, 1],
        ],
        dtype=np.int8,
    )

    result = PatternLibrary.place_pattern_on_grid(grid, pattern)

    assert result.sum() > 0, "oversized pattern was dropped entirely"
    np.testing.assert_array_equal(result, pattern[1:6, 1:6])


def test_place_pattern_at_a_negative_position_keeps_the_on_grid_part() -> None:
    """Verify a partially off-grid placement keeps the cells that do fit."""
    grid = np.zeros((5, 5), dtype=np.int8)
    pattern = np.ones((3, 3), dtype=np.int8)

    result = PatternLibrary.place_pattern_on_grid(grid, pattern, position=(-1, -1))

    assert result.sum() > 0, "partially off-grid pattern was dropped entirely"
    assert live_cell_set(result) == {(0, 0), (0, 1), (1, 0), (1, 1)}


# ================================================ [count_neighbors] ================================================ #


def test_count_neighbors_counts_the_eight_surrounding_cells() -> None:
    """Verify a fully surrounded cell has eight neighbours."""
    grid = np.ones((3, 3), dtype=np.int8)

    assert GameOfLifeEngine.count_neighbors(grid, 1, 1) == 8


def test_count_neighbors_ignores_the_cell_itself() -> None:
    """Verify the cell under inspection is excluded from its own count."""
    grid = np.zeros((3, 3), dtype=np.int8)
    grid[1, 1] = 1

    assert GameOfLifeEngine.count_neighbors(grid, 1, 1) == 0


def test_count_neighbors_returns_zero_on_an_empty_grid() -> None:
    """Verify a dead neighbourhood counts as zero."""
    grid = np.zeros((4, 4), dtype=np.int8)

    assert GameOfLifeEngine.count_neighbors(grid, 2, 2) == 0


@pytest.mark.parametrize(
    ("row", "col", "expected"),
    [
        (0, 0, 3),
        (0, 2, 3),
        (2, 0, 3),
        (2, 2, 3),
        (0, 1, 5),
        (1, 0, 5),
        (1, 1, 8),
    ],
)
def test_count_neighbors_clips_at_the_grid_boundaries(row: int, col: int, expected: int) -> None:
    """Verify out-of-bounds neighbours are treated as dead."""
    grid = np.ones((3, 3), dtype=np.int8)

    assert GameOfLifeEngine.count_neighbors(grid, row, col) == expected


def test_count_neighbors_does_not_wrap_around_the_grid() -> None:
    """Verify the grid boundaries are walls, not a torus."""
    grid = np.zeros((5, 5), dtype=np.int8)
    grid[0, :] = 1
    grid[:, 0] = 1

    assert GameOfLifeEngine.count_neighbors(grid, 4, 4) == 0


# ================================================== [apply_rules] ================================================== #


@pytest.mark.parametrize(
    ("neighbor_count", "expected"),
    [(0, 0), (1, 0), (2, 1), (3, 1), (4, 0), (5, 0), (6, 0), (7, 0), (8, 0)],
)
def test_apply_rules_for_a_live_cell(neighbor_count: int, expected: int) -> None:
    """Verify a live cell survives with two or three neighbours only."""
    assert GameOfLifeEngine.apply_rules(1, neighbor_count) == expected


@pytest.mark.parametrize(
    ("neighbor_count", "expected"),
    [(0, 0), (1, 0), (2, 0), (3, 1), (4, 0), (5, 0), (6, 0), (7, 0), (8, 0)],
)
def test_apply_rules_for_a_dead_cell(neighbor_count: int, expected: int) -> None:
    """Verify a dead cell is born with exactly three neighbours."""
    assert GameOfLifeEngine.apply_rules(0, neighbor_count) == expected


# ============================================ [compute_next_generation] ============================================ #


def test_blinker_flips_orientation_after_one_generation() -> None:
    """Verify the canonical period-2 oscillator rotates."""
    grid = np.zeros((5, 5), dtype=np.int8)
    grid[2, 1:4] = 1

    result = GameOfLifeEngine.compute_next_generation(grid)

    assert live_cell_set(result) == {(1, 2), (2, 2), (3, 2)}


def test_block_survives_unchanged() -> None:
    """Verify each cell of a block has exactly three neighbours and survives."""
    grid = np.zeros((5, 5), dtype=np.int8)
    grid[1:3, 1:3] = 1

    np.testing.assert_array_equal(GameOfLifeEngine.compute_next_generation(grid), grid)


def test_lone_cell_dies_of_underpopulation() -> None:
    """Verify a cell with no neighbours dies."""
    grid = np.zeros((3, 3), dtype=np.int8)
    grid[1, 1] = 1

    assert GameOfLifeEngine.compute_next_generation(grid).sum() == 0


def test_pair_of_cells_dies_of_underpopulation() -> None:
    """Verify two adjacent cells both have a single neighbour and die."""
    grid = np.zeros((4, 4), dtype=np.int8)
    grid[1, 1:3] = 1

    assert GameOfLifeEngine.compute_next_generation(grid).sum() == 0


def test_dead_cell_with_three_neighbors_is_born() -> None:
    """Verify reproduction on an L-shaped triple produces a block."""
    grid = np.zeros((4, 4), dtype=np.int8)
    grid[1, 1] = grid[1, 2] = grid[2, 1] = 1

    result = GameOfLifeEngine.compute_next_generation(grid)

    assert live_cell_set(result) == {(1, 1), (1, 2), (2, 1), (2, 2)}


def test_overpopulated_cells_die() -> None:
    """Verify only the corners of a fully alive grid survive."""
    grid = np.ones((5, 5), dtype=np.int8)

    result = GameOfLifeEngine.compute_next_generation(grid)

    assert live_cell_set(result) == {(0, 0), (0, 4), (4, 0), (4, 4)}


def test_compute_next_generation_does_not_mutate_the_input_grid() -> None:
    """Verify the current generation is left intact for callers holding it."""
    grid = np.zeros((5, 5), dtype=np.int8)
    grid[2, 1:4] = 1
    snapshot = grid.copy()

    GameOfLifeEngine.compute_next_generation(grid)

    np.testing.assert_array_equal(grid, snapshot)


def test_compute_next_generation_returns_a_new_array() -> None:
    """Verify the result is not an alias of the input."""
    grid = np.zeros((4, 4), dtype=np.int8)

    assert GameOfLifeEngine.compute_next_generation(grid) is not grid


@pytest.mark.parametrize("shape", [(1, 1), (1, 5), (5, 1), (3, 7), (7, 3), (20, 20)])
def test_compute_next_generation_preserves_shape_and_dtype(shape: tuple) -> None:
    """Verify square, rectangular and degenerate grids keep their geometry."""
    grid = np.zeros(shape, dtype=np.int8)

    result = GameOfLifeEngine.compute_next_generation(grid)

    assert result.shape == shape
    assert result.dtype == np.int8


def test_empty_grid_stays_empty() -> None:
    """Verify life is never created out of nothing."""
    grid = np.zeros((8, 8), dtype=np.int8)

    assert GameOfLifeEngine.compute_next_generation(grid).sum() == 0


def test_compute_next_generation_does_not_wrap_at_the_boundaries() -> None:
    """Verify a blinker on the top edge behaves as if surrounded by dead cells."""
    grid = np.zeros((5, 5), dtype=np.int8)
    grid[0, 1:4] = 1

    result = GameOfLifeEngine.compute_next_generation(grid)

    assert live_cell_set(result) == {(0, 2), (1, 2)}


@pytest.mark.parametrize("seed", [0, 1, 42, 1234])
@pytest.mark.parametrize("shape", [(20, 20), (13, 7)])
def test_compute_next_generation_matches_the_reference_implementation(seed: int, shape: tuple) -> None:
    """Verify the vectorized engine agrees with a naive rule-by-rule oracle."""
    rng = np.random.default_rng(seed)
    grid = rng.integers(0, 2, size=shape, dtype=np.int8)

    current_fast, current_reference = grid, grid
    for generation in range(5):
        current_fast = GameOfLifeEngine.compute_next_generation(current_fast)
        current_reference = reference_next_generation(current_reference)
        np.testing.assert_array_equal(
            current_fast,
            current_reference,
            err_msg=f"engine diverged from reference at generation {generation + 1}",
        )


def test_compute_next_generation_agrees_with_the_scalar_helpers() -> None:
    """Verify the vectorized path agrees with the module's own scalar helpers."""
    rng = np.random.default_rng(7)
    grid = rng.integers(0, 2, size=(12, 9), dtype=np.int8)

    result = GameOfLifeEngine.compute_next_generation(grid)

    expected = np.zeros_like(grid)
    for row in range(grid.shape[0]):
        for col in range(grid.shape[1]):
            neighbors = GameOfLifeEngine.count_neighbors(grid, row, col)
            expected[row, col] = GameOfLifeEngine.apply_rules(int(grid[row, col]), neighbors)

    np.testing.assert_array_equal(result, expected)


def test_compute_next_generation_handles_a_dense_grid_without_overflow() -> None:
    """Verify a large, fully alive grid is reduced to its four corners."""
    grid = np.ones((40, 40), dtype=np.int8)

    result = GameOfLifeEngine.compute_next_generation(grid)

    assert live_cell_set(result) == {(0, 0), (0, 39), (39, 0), (39, 39)}


# ================================================ [initialize_grid] ================================================ #


def test_initialize_grid_centers_the_requested_pattern(library: PatternLibrary) -> None:
    """Verify the initial grid holds the pattern, centered."""
    grid = GameOfLifeEngine.initialize_grid("blinker", (9, 9), library)

    assert live_cell_set(grid) == {(4, 3), (4, 4), (4, 5)}


@pytest.mark.parametrize("grid_size", [(20, 20), (50, 50), (30, 60)])
def test_initialize_grid_returns_an_int8_grid_of_the_requested_size(
    library: PatternLibrary,
    grid_size: tuple,
) -> None:
    """Verify the returned grid geometry follows the requested size."""
    grid = GameOfLifeEngine.initialize_grid("glider", grid_size, library)

    assert grid.shape == grid_size
    assert grid.dtype == np.int8


@pytest.mark.parametrize("pattern_name", ALL_PATTERN_NAMES)
def test_initialize_grid_keeps_every_pattern_cell_on_a_large_grid(
    library: PatternLibrary,
    pattern_name: str,
) -> None:
    """Verify no cell is lost when the pattern comfortably fits."""
    pattern = library.get_pattern(pattern_name).pattern

    grid = GameOfLifeEngine.initialize_grid(pattern_name, (60, 90), library)

    assert int(grid.sum()) == int(pattern.sum())


@pytest.mark.parametrize("pattern_name", ALL_PATTERN_NAMES)
def test_initialize_grid_is_never_empty_on_the_backend_grid_size(
    library: PatternLibrary,
    pattern_name: str,
) -> None:
    """Verify every catalogued pattern yields live cells on the default 20x20 grid.

    An all-dead initial grid can never evolve, which is what the UI reports as
    "the pattern does not update".
    """
    grid = GameOfLifeEngine.initialize_grid(pattern_name, BACKEND_GRID_SIZE, library)

    assert int(grid.sum()) > 0


def test_initialize_grid_raises_for_an_unknown_pattern(library: PatternLibrary) -> None:
    """Verify an unknown pattern name is rejected."""
    with pytest.raises(KeyError):
        GameOfLifeEngine.initialize_grid("does_not_exist", (10, 10), library)


def test_initialize_grid_random_produces_a_binary_grid(library: PatternLibrary) -> None:
    """Verify the random initializer respects the grid contract."""
    np.random.seed(12345)

    grid = GameOfLifeEngine.initialize_grid("random", (40, 40), library)

    assert grid.shape == (40, 40)
    assert grid.dtype == np.int8
    assert set(np.unique(grid)).issubset({0, 1})


def test_initialize_grid_random_uses_roughly_thirty_percent_live_cells(library: PatternLibrary) -> None:
    """Verify the documented ~30% density of the random initializer."""
    np.random.seed(12345)

    grid = GameOfLifeEngine.initialize_grid("random", (200, 200), library)

    assert 0.27 < grid.mean() < 0.33


def test_initialize_grid_random_is_not_constant(library: PatternLibrary) -> None:
    """Verify successive random initializations differ."""
    np.random.seed(1)

    first = GameOfLifeEngine.initialize_grid("random", (30, 30), library)
    second = GameOfLifeEngine.initialize_grid("random", (30, 30), library)

    assert not np.array_equal(first, second)


# ================================================ [SimulationState] ================================================ #


def test_simulation_state_stores_every_field() -> None:
    """Verify the state payload handed to the UI keeps all attributes."""
    grid = np.ones((2, 2), dtype=np.int8)

    state = SimulationState(
        grid=grid,
        generation=7,
        live_cells=4,
        is_running=True,
        selected_pattern="blinker",
    )

    assert state.generation == 7
    assert state.live_cells == 4
    assert state.is_running is True
    assert state.selected_pattern == "blinker"
    np.testing.assert_array_equal(state.grid, grid)


# ============================================== [SimulationController] ============================================= #


def test_controller_defaults_to_a_fifty_by_fifty_grid() -> None:
    """Verify the documented default grid size."""
    assert SimulationController().grid_size == (50, 50)


def test_controller_state_before_initialization_is_empty() -> None:
    """Verify an uninitialized controller reports a dead grid instead of failing."""
    simulation = SimulationController(grid_size=(6, 8))

    state = simulation.get_current_state()

    assert state.grid.shape == (6, 8)
    assert state.grid.sum() == 0
    assert state.generation == 0
    assert state.live_cells == 0
    assert state.is_running is False
    assert state.selected_pattern == "glider"


def test_controller_grid_property_is_none_before_initialization() -> None:
    """Verify the grid accessor signals the uninitialized state."""
    assert SimulationController().grid is None


@pytest.mark.parametrize("method_name", ["step_forward", "start_simulation", "reset_simulation"])
def test_controller_operations_require_initialization(method_name: str) -> None:
    """Verify stepping, starting and resetting fail before initialization."""
    simulation = SimulationController(grid_size=(5, 5))

    with pytest.raises(RuntimeError, match="not initialized"):
        getattr(simulation, method_name)()


def test_controller_can_be_paused_before_initialization() -> None:
    """Verify pausing is always safe, so the UI can pause unconditionally."""
    simulation = SimulationController(grid_size=(5, 5))

    simulation.pause_simulation()

    assert simulation.is_running is False


def test_initialize_loads_the_pattern_and_resets_the_counters() -> None:
    """Verify initialization selects the pattern and starts from generation zero."""
    simulation = SimulationController(grid_size=(20, 20))

    simulation.initialize("toad")

    state = simulation.get_current_state()
    assert state.selected_pattern == "toad"
    assert state.generation == 0
    assert state.is_running is False
    assert state.live_cells == 6


def test_initialize_stops_a_running_simulation() -> None:
    """Verify loading a new pattern leaves the simulation paused."""
    simulation = SimulationController(grid_size=(10, 10))
    simulation.initialize("blinker")
    simulation.start_simulation()

    simulation.initialize("toad")

    assert simulation.is_running is False


def test_initialize_raises_for_an_unknown_pattern() -> None:
    """Verify an invalid selection is rejected up front."""
    simulation = SimulationController(grid_size=(10, 10))

    with pytest.raises(KeyError):
        simulation.initialize("not_a_pattern")


def test_step_forward_advances_the_generation_counter(controller: SimulationController) -> None:
    """Verify each step increments the generation number."""
    controller.step_forward()
    controller.step_forward()

    assert controller.generation == 2
    assert controller.get_current_state().generation == 2


def test_step_forward_evolves_the_grid(controller: SimulationController) -> None:
    """Verify a step actually changes an oscillating grid."""
    before = controller.grid

    controller.step_forward()

    assert not np.array_equal(controller.grid, before)


def test_stepping_a_blinker_twice_restores_the_initial_grid(controller: SimulationController) -> None:
    """Verify the controller reproduces the period-2 behaviour end to end."""
    initial = controller.grid

    controller.step_forward()
    controller.step_forward()

    np.testing.assert_array_equal(controller.grid, initial)


def test_step_forward_matches_the_engine(controller: SimulationController) -> None:
    """Verify the controller delegates evolution to the engine unchanged."""
    expected = GameOfLifeEngine.compute_next_generation(controller.grid)

    controller.step_forward()

    np.testing.assert_array_equal(controller.grid, expected)


def test_start_and_pause_toggle_the_running_flag(controller: SimulationController) -> None:
    """Verify the running flag reported to the UI follows start and pause."""
    controller.start_simulation()
    assert controller.is_running is True
    assert controller.get_current_state().is_running is True

    controller.pause_simulation()
    assert controller.is_running is False
    assert controller.get_current_state().is_running is False


def test_reset_restores_the_initial_grid_and_generation(controller: SimulationController) -> None:
    """Verify reset returns the simulation to generation zero."""
    initial = controller.grid
    controller.step_forward()
    controller.start_simulation()

    controller.reset_simulation()

    np.testing.assert_array_equal(controller.grid, initial)
    assert controller.generation == 0
    assert controller.is_running is False


def test_reset_can_be_replayed_after_many_steps(controller: SimulationController) -> None:
    """Verify the initial grid is preserved, not overwritten while stepping."""
    initial = controller.grid
    for _ in range(7):
        controller.step_forward()
    controller.reset_simulation()

    for _ in range(3):
        controller.step_forward()
    controller.reset_simulation()

    np.testing.assert_array_equal(controller.grid, initial)


def test_reset_uses_the_most_recently_initialized_pattern(controller: SimulationController) -> None:
    """Verify re-initializing replaces the reset target."""
    controller.initialize("beacon")
    expected = controller.grid
    controller.step_forward()

    controller.reset_simulation()

    np.testing.assert_array_equal(controller.grid, expected)
    assert controller.get_current_state().selected_pattern == "beacon"


def test_get_current_state_returns_a_defensive_copy(controller: SimulationController) -> None:
    """Verify the UI cannot corrupt the simulation through the returned state."""
    state = controller.get_current_state()

    state.grid[:] = 1

    assert controller.get_current_state().live_cells == 3


def test_grid_property_returns_a_defensive_copy(controller: SimulationController) -> None:
    """Verify the grid accessor hands out a copy."""
    grid = controller.grid

    grid[:] = 1

    assert int(controller.grid.sum()) == 3


def test_live_cells_matches_the_grid_population() -> None:
    """Verify the live-cell counter stays in sync with the grid."""
    simulation = SimulationController(grid_size=(20, 20))
    simulation.initialize("pulsar")

    for _ in range(4):
        state = simulation.get_current_state()
        assert state.live_cells == int(state.grid.sum())
        simulation.step_forward()


def test_controller_pattern_list_is_sorted_and_offers_random() -> None:
    """Verify the dropdown content: every library pattern plus ``random``."""
    simulation = SimulationController(grid_size=(10, 10))

    patterns = simulation.get_pattern_list()

    assert patterns == sorted(ALL_PATTERN_NAMES + ["random"])


def test_controller_pattern_list_is_stable_across_calls() -> None:
    """Verify repeated calls do not accumulate duplicated entries."""
    simulation = SimulationController(grid_size=(10, 10))

    assert simulation.get_pattern_list() == simulation.get_pattern_list()


def test_controller_can_run_a_random_simulation() -> None:
    """Verify the random pattern is usable through the controller."""
    np.random.seed(99)
    simulation = SimulationController(grid_size=(30, 30))

    simulation.initialize("random")
    simulation.step_forward()

    assert simulation.generation == 1
    assert simulation.grid.shape == (30, 30)


@pytest.mark.parametrize("pattern_name", ALL_PATTERN_NAMES + ["random"])
def test_controller_runs_every_pattern_without_error(pattern_name: str) -> None:
    """Verify a short simulation of every selectable pattern completes."""
    np.random.seed(3)
    simulation = SimulationController(grid_size=BACKEND_GRID_SIZE)

    simulation.initialize(pattern_name)
    for _ in range(5):
        simulation.step_forward()

    state = simulation.get_current_state()
    assert state.generation == 5
    assert state.grid.shape == BACKEND_GRID_SIZE
