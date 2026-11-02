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

# ©2026, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.

"""Backend of the game of life step."""

from ansys.saf.glow.solution import StepModel, StepSpec, long_running, transaction

from saf.solutions.examples.solution.logic.game_of_life import SimulationController


class GameOfLifeStep(StepModel):
    """Step definition of the game of life step."""

    grid_size: int = 20
    selected_pattern: str = "beacon"
    max_iterations: int = 10

    initial_grid_state: list[list[int]] = []
    grid_states: list[list[list[int]]] = []

    @transaction(
        self=StepSpec(upload=["initial_grid_state"], download=["selected_pattern", "grid_size"]),
        enable_termination_event=True,
    )
    def display_initial_state(self) -> None:
        """Display the initial state of the Game of Life simulation."""
        controller = SimulationController(grid_size=(self.grid_size, self.grid_size))
        controller.initialize(self.selected_pattern)
        state = controller.get_current_state()
        self.initial_grid_state = state.grid.tolist()

    @transaction(
        self=StepSpec(
            upload=["grid_states"],
            download=["selected_pattern", "grid_size", "max_iterations"],
        ),
        enable_termination_event=True,
    )
    @long_running
    def simulate(self) -> None:
        """Run the Game of Life simulation."""
        controller = SimulationController(grid_size=(self.grid_size, self.grid_size))
        controller.initialize(self.selected_pattern)
        state = controller.get_current_state()
        self.grid_states = []
        self.grid_states.append(state.grid.tolist())
        self.transaction.raise_event(
            message={"grid": state.grid.tolist(), "iteration": 0},
            stream_name="my-stream",
        )

        iterations = 0
        while state.live_cells > 0 and iterations < self.max_iterations:
            iterations += 1
            controller.step_forward()
            state = controller.get_current_state()
            self.grid_states.append(state.grid.tolist())
            self.transaction.raise_event(
                message={"grid": state.grid.tolist(), "iteration": iterations},
                stream_name="my-stream",
            )
