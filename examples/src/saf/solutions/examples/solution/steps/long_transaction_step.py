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

# ©2023, ANSYS Inc. Unauthorized use, distribution or duplication is prohibited.

"""Long transaction example step model."""
import datetime
import time

from ansys.saf.glow.solution import StepModel, StepSpec, long_running, transaction

PROGRESS_STREAM_NAME = "long-transaction-progress"
"""Name of the event stream carrying the progress updates of the ``stream_updates`` method."""

TERMINATION_STREAM_NAME = "stream-updates"
"""Name of the event stream carrying the termination event of the ``stream_updates`` method.

The termination event stream is named after the transaction method, with underscores replaced by hyphens.
"""


class LongTransactionStep(StepModel):
    """Long transaction example step model."""

    status: str = "[]"
    number_of_increments: int = 30
    current_increment: int = -1

    @long_running
    @transaction(
        self=StepSpec(
            download=["number_of_increments"],
            upload=["status", "current_increment"],
        ),
        enable_termination_event=True,
    )
    def stream_updates(self) -> None:
        """Stream progress updates to the frontend through backend events."""
        for i in range(self.number_of_increments):
            self.status = f"Update {i} at {_now()}"
            self.current_increment = i
            self.transaction.raise_event(
                message={
                    "status": self.status,
                    "current_increment": self.current_increment,
                    "number_of_increments": self.number_of_increments,
                },
                stream_name=PROGRESS_STREAM_NAME,
            )
            # Progress and termination events travel on two independent streams, so they are not
            # ordered relative to each other. Pacing the progress events leaves the progress stream
            # enough time to drain before the transaction ends.
            time.sleep(1)
        self.status = f"Last updated at {_now()}"


def _now():
    return datetime.datetime.now().strftime("%H:%M:%S")
