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

"""
Backend of the basic step.

This module defines the ``BasicStep`` step model, which gathers the fields and the
transaction methods used by the basic example pages: blocking and long-running processes,
file and log handling, table data generation, and the computation of the transcendental
butterfly curve.
"""

import time
from typing import Any
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont
from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import StepModel, StepSpec, long_running, transaction

from saf.solutions.examples.solution.logic.butterfly_curve import compute_butterfly_curve
from saf.solutions.examples.solution.logic.table_logic import generate_table_data


class BasicStep(StepModel):
    """
    Definition of the basic step.

    Attributes
    ----------
    result_files : list[EntityHandle]
        Handles of the images created by the ``create_images`` transaction method.
    log_file : EntityHandle
        Handle of the file written by the ``generate_process_logs`` transaction method.
    data_dict : dict[str, Any]
        Data displayed by the table example page.
    table_flag : bool
        Whether the table data has been generated.
    x_coords : list[float]
        ``x`` coordinates of the butterfly curve.
    y_coords : list[float]
        ``y`` coordinates of the butterfly curve.
    distance : list[float]
        Distance of each point of the butterfly curve to the origin.
    butterfly_wing_frequency : float
        Frequency of the cosine term that shapes the wings of the butterfly curve.
    butterfly_wing_amplitude : float
        Amplitude of the cosine term that shapes the wings of the butterfly curve.
    butterfly_twist : float
        Divider of the parameter in the sine term that twists the wings.
    butterfly_exponent : int
        Exponent applied to the sine term.
    butterfly_revolutions : float
        Number of half-turns of the butterfly curve.
    """

    result_files: list[EntityHandle] = []
    log_file: EntityHandle = NO_ENTITY

    # Table data
    data_dict: dict[str, Any] = {}
    table_flag: bool = False

    # Butterfly curve parameters
    x_coords: list[float] = []
    y_coords: list[float] = []
    distance: list[float] = []
    butterfly_wing_frequency: float = 4.0
    butterfly_wing_amplitude: float = 2.0
    butterfly_twist: float = 12.0
    butterfly_exponent: int = 5
    butterfly_revolutions: float = 12.0

    @transaction(self=StepSpec())
    def simple_blocking_process(self, wait_time: float) -> None:
        """
        Trigger a blocking process that waits for some time.

        The frontend waits for this transaction method to return before it can update.

        Parameters
        ----------
        wait_time : float
            Duration of the process, in seconds.
        """
        start_time = time.time()
        while (time.time() - start_time) < wait_time:
            time.sleep(0.5)

    @transaction(self=StepSpec())
    @long_running
    def simple_long_running_process(self, force_failure: bool, wait_time: float) -> None:
        """
        Trigger a non-blocking process that waits for some time and can be set to fail.

        The ``long_running`` decorator runs the process in the background, so the frontend
        stays responsive while it is executed.

        Parameters
        ----------
        force_failure : bool
            Whether to raise an exception at the end of the process. This is useful to
            show how a failed transaction is reported in the UI.
        wait_time : float
            Duration of the process, in seconds.

        Raises
        ------
        Exception
            If ``force_failure`` is ``True``.
        """
        start_time = time.time()
        while (time.time() - start_time) < wait_time:
            time.sleep(0.5)
        if force_failure:
            raise Exception("This is a forced failure.")

    @transaction(self=StepSpec(download=["log_file"], upload=["log_file"]), enable_termination_event=True)
    @long_running
    def generate_process_logs(self, wait_time: float) -> None:
        """
        Write the current time to a file every second for a certain amount of time.

        The new lines are appended to the existing ``log_file`` content, and each of them
        is also sent to the frontend through the ``generate-process-logs-update`` event
        stream. The transaction method can be terminated from the UI.

        Parameters
        ----------
        wait_time : float
            Duration of the process, in seconds.
        """
        try:
            log_file = self.storage_scope.get_cached(self.log_file)
            existing_logs = log_file.read_bytes()
        except Exception:
            existing_logs = b""
        start_time = time.time()
        while (time.time() - start_time) < wait_time:
            current_time = f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n"
            existing_logs += current_time.encode()
            self.log_file = self.storage_scope.store_stream(existing_logs)
            self.transaction.raise_event(message=current_time, stream_name="generate-process-logs-update")
            time.sleep(1)

    @transaction(self=StepSpec(upload=["log_file"]))
    def clear_logs(self) -> None:
        """Reset the ``log_file`` field so that the log page starts from an empty file."""
        self.log_file = NO_ENTITY

    @transaction(self=StepSpec(upload=["result_files"]))
    def create_images(self) -> None:
        """
        Mimic the creation of 3 png files by using the pillow library.

        The images are written in the storage root of the step and their handles are
        stored in the ``result_files`` field.
        """
        images_path = self.storage_scope.get_storage_root() / "images"
        images_path.mkdir()

        self.result_files = []
        for _ in range(3):
            image_name = f"Image_{str(uuid4())}.png"
            image_path = images_path / image_name
            image_with_background = Image.new("RGB", (400, 300), "grey")
            ImageDraw.Draw(image_with_background).text(  # pyright: ignore[reportUnknownMemberType]
                (20, 150), image_name, font=ImageFont.truetype("arial.ttf", size=20)
            )
            image_with_background.save(image_path)
            image_handle = self.storage_scope.store(image_path)
            self.result_files.append(image_handle)

    @transaction(self=StepSpec(upload=["data_dict", "table_flag"]))
    def generate_data(self) -> None:
        """Generate the data of the table and store it in the ``data_dict`` field."""
        data_dict = generate_table_data()
        self.data_dict = data_dict
        self.table_flag = True

    @transaction(
        self=StepSpec(
            upload=["x_coords", "y_coords", "distance"],
            download=[
                "butterfly_wing_frequency",
                "butterfly_wing_amplitude",
                "butterfly_twist",
                "butterfly_exponent",
                "butterfly_revolutions",
            ],
        )
    )
    def compute_butterfly_curve(self) -> None:
        """
        Compute the transcendental butterfly curve from the step parameters.

        The ``butterfly_*`` fields are downloaded and passed to the ``compute_butterfly_curve``
        business logic function. The resulting coordinates and distances to the origin are
        uploaded to the ``x_coords``, ``y_coords``, and ``distance`` fields, which the
        Plotly graph page displays.
        """
        self.x_coords, self.y_coords, self.distance = compute_butterfly_curve(
            wing_frequency=self.butterfly_wing_frequency,
            wing_amplitude=self.butterfly_wing_amplitude,
            twist=self.butterfly_twist,
            exponent=self.butterfly_exponent,
            revolutions=self.butterfly_revolutions,
        )
