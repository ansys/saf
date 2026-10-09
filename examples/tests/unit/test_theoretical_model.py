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

"""Unit tests for the beam-bending theoretical model."""

import numpy as np
import pytest

from saf.solutions.examples.solution.scripts.beam_bending.theoretical_model import compute_beam_deflection


def test_compute_beam_deflection_matches_reference_profile() -> None:
    """Verify deflection coordinates and values for an asymmetric beam."""
    x_coordinates, deflection = compute_beam_deflection(
        a=100,
        b=200,
        d=10,
        E=200000,
        p=1000,
        n=5,
    )

    np.testing.assert_allclose(x_coordinates, [0, 75, 150, 225, 300])
    np.testing.assert_allclose(
        deflection,
        [
            0.0,
            -3.7666669865081897,
            -4.8807515881514565,
            -3.1565730379892574,
            0.0,
        ],
    )


@pytest.mark.parametrize("number_of_points", [1, 5, 25, 100])
def test_compute_beam_deflection_uses_requested_number_of_points(
    number_of_points: int,
) -> None:
    """Verify both returned arrays use the requested number of points."""
    x_coordinates, deflection = compute_beam_deflection(
        a=100,
        b=200,
        d=10,
        E=200000,
        p=1000,
        n=number_of_points,
    )

    assert len(x_coordinates) == number_of_points
    assert len(deflection) == number_of_points
    np.testing.assert_allclose(x_coordinates, np.linspace(0, 300, number_of_points))


def test_compute_beam_deflection_is_symmetric_for_centered_load() -> None:
    """Verify a centered load produces a symmetric deflection profile."""
    _, deflection = compute_beam_deflection(
        a=100,
        b=100,
        d=10,
        E=200000,
        p=1000,
        n=9,
    )

    np.testing.assert_allclose(deflection, deflection[::-1])
    assert np.argmin(deflection) == len(deflection) // 2
    assert deflection[0] == pytest.approx(0)
    assert deflection[-1] == pytest.approx(0)


def test_compute_beam_deflection_is_zero_when_load_is_zero() -> None:
    """Verify zero applied load produces zero deflection at every point."""
    _, deflection = compute_beam_deflection(
        a=100,
        b=200,
        d=10,
        E=200000,
        p=0,
        n=7,
    )

    np.testing.assert_allclose(deflection, np.zeros(7))
