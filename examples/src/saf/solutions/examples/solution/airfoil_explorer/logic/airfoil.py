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

"""Airfoil geometry using NACA 4-digit series formulas."""

import numpy as np


def airfoil_thickness(x_coord, thickness_max, chord_length):
    """Calculate the half thickness of a NACA 4-digit airfoil at a given x coordinate.

    input:
        x_coord: x coordinate of center line, float
        thickness_max: maximum thickness, in fraction of chord length, float
        chord_length: chord length, float
    output:
        half thickness of airfoil at corresponding x coordinate
    """
    x_bar = x_coord / chord_length
    return (
        5
        * thickness_max
        * (0.2969 * np.sqrt(x_bar) - 0.1260 * x_bar - 0.3516 * x_bar**2 + 0.2843 * x_bar**3 - 0.1036 * x_bar**4)
    )


def airfoil_yc(x_coord, camber_max, camber_pos, chord_length):
    """Calculate the y coordinate of the center line of a NACA 4-digit airfoil at a given x coordinate.

    input:
        x_coord: x coordinate of center line, float
        camber_max: the maximum camber (100 m is the first of the four digits), float
        camber_pos: location of maximum camber (10 p is the second digit), float
        chord_length: chord length, float
    output:
        y coordinate of center line at corresponding x coordinate
    """
    if x_coord <= camber_pos * chord_length:
        return camber_max * x_coord * (2 * camber_pos - x_coord / chord_length) / camber_pos**2
    else:
        return (
            camber_max
            * (chord_length - x_coord)
            * (1 + x_coord / chord_length - 2 * camber_pos)
            / (1 - camber_pos) ** 2
        )


def airfoil_theta(x_coord, camber_max, camber_pos, chord_length):
    """Calculate the angle between the center line and horizontal line of a NACA 4-digit \
    airfoil at a given x coordinate.

    input:
        x_coord: x coordinate of center line, float
        camber_max: the maximum camber (100 m is the first of the four digits), float
        camber_pos: location of maximum camber (10 p is the second digit), float
        chord_length: chord lrngth, float
    output:
        angle between center and horizontal line at corresponding x coordinate
    """
    if x_coord <= camber_pos * chord_length:
        return np.arctan(2 * camber_max * (camber_pos - x_coord / chord_length) / camber_pos**2)
    else:
        return np.arctan(2 * camber_max * (camber_pos - x_coord / chord_length) / (1 - camber_pos) ** 2)


def airfoil_surface(x_array, thickness_max, sign, camber_max, camber_pos, chord_length):
    """Construct upper (+1) or lower (-1) surface coordinates for a NACA 4-digit airfoil.

    input:
        x_array: x coordinate of center line, float
        thickness_max: maximum thickness, in fraction of chord length, float
        sign: indicate upper (1) or lower (-1) surface of airfoil
        camber_max: the maximum camber (100 m is the first of the four digits), float
        camber_pos: location of maximum camber (10 p is the second digit), float
        chord_length: chord lrngth, float
    output:
        x, y coordinates on airfoil surface at corresponding
        center line x coordinate
    """
    xs = []
    ys = []

    for xi in x_array:
        yt = airfoil_thickness(xi, thickness_max, chord_length)
        if camber_max == 0 or camber_pos == 0:
            xs.append(xi)
            ys.append(sign * yt)
        else:
            theta = airfoil_theta(xi, camber_max, camber_pos, chord_length)
            yc = airfoil_yc(xi, camber_max, camber_pos, chord_length)

            xs.append(xi - sign * yt * np.sin(theta))
            ys.append(yc + sign * yt * np.cos(theta))

    return np.array(xs), np.array(ys)
