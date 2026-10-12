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

import logging
from pathlib import Path
import shutil
from typing import Literal
import uuid

import ansys.optislang.core.examples as examples  # pyright: ignore[reportMissingTypeStubs]

from ansys.saf.glow.solution import (
    NO_ENTITY,
    EntityHandle,
    StepModel,
    StepSpec,
    create_instance,
    instance,
    long_running,
    transaction,
)
from ansys.saf.product_manager.optislang_wrapper import OslManager

logger = logging.getLogger(__name__)


class OptislangWrapperStep(StepModel):
    version: str = "252"
    project_file: EntityHandle = NO_ENTITY
    properties_file: EntityHandle = NO_ENTITY
    input_files: list[EntityHandle] = []
    log_level: str = "INFO"
    objective: str = ""
    files_content: dict[str, str] = {}
    instance_running: bool = False

    op_mode: Literal["temp_files", "stream_bytes"] = "temp_files"

    @transaction(self=StepSpec(download=["op_mode"], upload=["project_file"]))
    def download_example_file(self) -> None:
        example_path: Path = Path(examples.get_files("ten_bar_truss")[1][0])  # type: ignore
        if self.op_mode == "temp_files":
            file_on_scope = self.storage_scope.get_storage_root() / "proj.opf"
            shutil.copy2(example_path, file_on_scope)
            logger.info(f"Storing temp file {file_on_scope=}.")
            self.project_file = self.storage_scope.store(file_on_scope)
        else:
            self.project_file = self.storage_scope.store_stream(
                example_path.read_bytes(),
                relative_location=Path("proj.opf"),
            )
            logger.info("Storing streamed bytes.")

    @transaction(self=StepSpec(download=["op_mode"], upload=["properties_file"]))
    def write_properties_file(self) -> None:
        properties_file_json = rb"""
        {
            "placeholders" :
            {
                "placeholder_definitions" :
                {
                    "source" :
                    {
                        "description" : "",
                        "range" : "",
                        "type" :
                        {
                            "enum" :
                            [
                                "unknown",
                                "string",
                                "split_path",
                                "relative_split_path",
                                "path",
                                "uint",
                                "int",
                                "string_list",
                                "real",
                                "bool",
                                "provided_path"
                            ],
                            "value" : "string"
                        },
                        "user_level" :
                        {
                            "enum" : [ "computation_engineer", "flow_engineer" ],
                            "value" : "flow_engineer"
                        }
                    }
                },
                "placeholder_values" :
                {
                    "source" : "print(\"using external project properties\")"
                }
            },
            "registered_files" :
            [
                {
                    "action" : "none",
                    "action_point" : "manual",
                    "auto_generated" : false,
                    "comment" : "",
                    "embedded" : false,
                    "existence" : "dontcare",
                    "external_location" : "",
                    "filename_regex" : "",
                    "ident" : "project",
                    "local_location" :
                    {
                        "base_path_mode" :
                        {
                            "enum" :
                            [
                                "working_dir_relative",
                                "project_relative",
                                "project_working_dir_relative",
                                "reference_files_dir_relative",
                                "absolute_path"
                            ],
                            "value" : "project_relative"
                        },
                        "split_path" :
                        {
                            "head" : "",
                            "tail" : "project.opf"
                        }
                    },
                    "properties" : {},
                    "remove_on_reset" : false,
                    "revision" : "",
                    "tag" : "a3532a37-ab30-4c62-9599-ac37258bd262",
                    "type" : "filesystem",
                    "usage" : "undetermined",
                    "use_regex_for_filename" : false,
                    "wait_for_file" : false
                }
            ]
        }"""
        if self.op_mode == "temp_files":
            file_on_scope = self.storage_scope.get_storage_root() / "properties_file.json"
            file_on_scope.write_bytes(properties_file_json)
            logger.info(f"Storing temp file {file_on_scope=}.")
            self.properties_file = self.storage_scope.store(file_on_scope)
        else:
            self.properties_file = self.storage_scope.store_stream(properties_file_json)
            logger.info("Storing streamed bytes.")

    @transaction(self=StepSpec(upload=["input_files", "files_content"]))
    def write_input_files(self) -> None:
        self.files_content = {}
        self.input_files = []

        file_group_dir = self.storage_scope.get_storage_root() / "mydir"
        file_group_dir.mkdir(exist_ok=True, parents=True)

        for i in range(3):
            file_relative_path = f"file_{str(i)}.txt"
            file_content = str(uuid.uuid4())
            file_path = file_group_dir / file_relative_path
            file_path.write_text(file_content)
            self.input_files.append(self.storage_scope.store(file_path))
            self.files_content[file_relative_path] = file_content

    @long_running
    @transaction(
        self=StepSpec(
            download=[
                "input_files",
                "project_file",
                "properties_file",
                "version",
                "log_level",
            ],
            upload=["instance_running"],
        ),
    )
    @create_instance("osl_manager", OslManager)
    def start_osl_project(self, osl_manager: OslManager) -> None:
        osl_manager.initialize(version=self.version)

        project_file = osl_manager.storage_scope.get_cached(self.project_file)
        logger.info(f"Cached {self.project_file=} blob to path {project_file}")

        properties_files = osl_manager.storage_scope.get_cached(self.properties_file)
        logger.info(f"Cached {self.properties_file=} blob to path {properties_files}")

        input_files = [osl_manager.storage_scope.get_cached(file) for file in self.input_files]
        for i in range(len(input_files)):
            logger.info(f"Cached {self.input_files[i]=} blob to path {input_files[i]}")

        logger.info("Starting instance...")
        osl_manager.instance.start(
            project_path=project_file,
            project_properties_file=properties_files,
            input_files=input_files,
            osl_version=self.version,
            loglevel=self.log_level,
        )
        logger.info("Instance successfully started.")

        self.instance_running = True

    @transaction(self=StepSpec(download=["log_level"], upload=["objective"]))
    @instance("osl_manager")
    def evaluate_design(self, osl_manager: OslManager) -> None:
        with osl_manager.instance.optislang_client(self.log_level) as osl:
            project = osl.application.project
            # Evaluate reference design
            root_system = project.root_system  # type: ignore
            design = root_system.get_reference_design()
            evaluated_design = root_system.evaluate_design(design)
            self.objective = str(evaluated_design.objectives[0].value)  # type: ignore

    @transaction(self=StepSpec(download=["log_level"]))
    @instance("osl_manager")
    def get_files(self, osl_manager: OslManager) -> list[Path] | None:
        with osl_manager.instance.optislang_client(self.log_level) as osl:
            project = osl.application.project
            assert project
            return [file.path for file in project.get_registered_files()]

    @long_running
    @transaction(self=StepSpec(upload=["instance_running"]))
    @instance("osl_manager")
    def shutdown_optislang(self, osl_manager: OslManager) -> None:
        osl_manager.shutdown()
        self.instance_running = False
