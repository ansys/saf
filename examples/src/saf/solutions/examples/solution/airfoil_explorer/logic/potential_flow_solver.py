# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Solver for potential flow around airfoil using finite difference method."""
import numpy as np

from .grid import solve_a_b_c, solve_equation


def solve_potential_flow(Nxi, Neta, AOA, Vinf, x, y):
    """Solve potential flow around airfoil using finite difference method."""
    # initialize stream functions
    stream = np.zeros((Nxi, Neta))

    # set up the BCs on the outer boundary
    stream[:, -1] = -x[:, -1] * np.sin(AOA) * Vinf + y[:, -1] * np.cos(AOA) * Vinf

    # solve the PDE by iterative method
    iters = 0
    while True:

        iters += 1

        stream_n = stream.copy()

        # apply periodic BC on dividing line
        temp = np.append([stream[-2, :].copy()], stream[:2, :].copy(), 0)
        tempx = np.append([x[-2, :].copy()], x[:2, :].copy(), 0)
        tempy = np.append([y[-2, :].copy()], y[:2, :].copy(), 0)
        a, b, c = solve_a_b_c(tempx, tempy)
        stream[0, 1:-1] = solve_equation(a, b, c, temp)
        stream[-1, :] = stream[0, :].copy()

        # apply Kutta condition
        # and set the value of stream function on the airfoil surface
        stream[:, 0] = stream[0, 1]

        # solve interior
        a, b, c = solve_a_b_c(x, y)
        stream[1:-1, 1:-1] = solve_equation(a, b, c, stream)

        # calculate difference between current and the last result
        err = np.abs(stream - stream_n)

        # adjudge whether the iteration should stop
        if err.max() <= 1e-6:
            break

    return stream
