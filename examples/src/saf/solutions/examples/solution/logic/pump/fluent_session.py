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

"""Lifecycle helpers shared by the Fluent-driven steps of the workflow."""

from typing import Any

from ansys.fluent.core.fluent_connection import UnsupportedRemoteFluentInstance

from saf.solutions.examples.solution.logic.pump.constants import SOLVER_EXIT_WAIT_SECONDS


def shutdown_solver(solver: Any) -> None:
    """Exit Fluent and block until its local processes have released their files.

    Fluent runs with the GLOW method storage root as its working directory, and writes a
    ``fluent-<timestamp>-<pid>.trn`` transcript plus a cleanup script there. As soon as the
    transaction returns, the BDM garbage collector deletes every file in that root that is
    not referenced by a stored handle. ``Session.exit()`` only sends the exit request, so on
    Windows the sweep races the shutdown and fails with
    ``PermissionError: [WinError 32] The process cannot access the file because it is being
    used by another process`` on the still-open transcript. Waiting for the processes to go
    away makes the sweep deterministic.

    Parameters
    ----------
    solver : Any
        Live PyFluent session to close.
    """
    try:
        solver.exit(wait=SOLVER_EXIT_WAIT_SECONDS)
    except UnsupportedRemoteFluentInstance:
        # Remote sessions (PIM, HPS, containers) cannot be waited on, and they do not write
        # into the method storage root either, so there is nothing for the sweep to collide
        # with. PyFluent has already sent the exit request before raising.
        pass
