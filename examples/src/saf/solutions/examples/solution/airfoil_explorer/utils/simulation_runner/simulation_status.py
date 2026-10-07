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

"""Simulation status definitions for tracking job progress."""

from enum import Enum


class SimulationStatus(str, Enum):
    """Enumeration of possible simulation states.

    This unifies UI presentation states, local execution states,
    and HPS job evaluation states into a single source of truth.
    """

    # General / UI States
    IDLE = "idle"
    INITIALIZING = "initializing"
    RESULTS_READY = "results_ready"

    # Local & HPS Common Execution States
    QUEUED = "queued"
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    # HPS-Specific Job Evaluation States
    PROLOG = "prolog"
    EVALUATED = "evaluated"
    ABORTED = "aborted"
    TIMEOUT = "timeout"
