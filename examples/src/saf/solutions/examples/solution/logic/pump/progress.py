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

"""Human-readable stage labels derived from a transaction progress fraction."""


def stage_label(stages: tuple[tuple[float, str], ...], fraction: float) -> str:
    """Return the label of the last stage whose threshold ``fraction`` has reached.

    Parameters
    ----------
    stages : tuple[tuple[float, str], ...]
        Ascending ``(threshold, label)`` pairs.
    fraction : float
        Progress fraction, normally between 0 and 1.

    Returns
    -------
    str
        Label of the active stage.
    """
    label = stages[0][1]
    for threshold, candidate in stages:
        if fraction >= threshold:
            label = candidate
    return label
