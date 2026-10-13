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

import atexit
import ctypes
import logging
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

import psutil
from pydantic import BaseModel

from ansys.bdm.api import NO_ENTITY, EntityHandle
from ansys.saf.glow.solution import (
    BadRequestError,
    SolutionConfiguration,
    StepModel,
    StepSpec,
    long_running,
    transaction,
)

LOGGING_DEBUG_TESTING_STRING = "Debug logged for testing purposes."
LOGGING_INFO_TESTING_STRING = "Info logged for testing purposes."
LOGGING_ERROR_TESTING_STRING = "Error logged for testing purposes."
LOGGING_WARNING_TESTING_STRING = "Warning logged for testing purposes."
TEXT_FILE_DUMMY_STRING = "Hello World"
INPUT_PRODUCT_FILE = Path("./tests/mocks/solution_end_to_end/method_assets/Transformer_leakage_inductance.aedt")


logger = logging.getLogger(__name__)


def start_process() -> int:
    child_process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1000)"])
    return child_process.pid


class SubprocessManager:
    """Launches a subprocess on init and registers an atexit handler to terminate it, as HPS Client does.

    This is used to test that we allow code to gracefully tear down during a long-running transaction,
    and child process cleanup is only done afterwards.
    """

    def __init__(self) -> None:
        self.process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1000)"])
        self.pid = self.process.pid
        atexit.register(self._terminate)

    def _terminate(self) -> None:
        logger.info(f"Gracefully terminating subprocess with PID {self.pid}")
        self.process.terminate()
        self.process.wait()


class CustomTypeXYZ(BaseModel):
    x: int
    y: int
    z: int

    def __eq__(self, other: "CustomTypeXYZ") -> bool:  # type: ignore
        return self.x == other.x and self.y == other.y and self.z == other.z


class CustomTypeABC(BaseModel):
    a: int
    b: CustomTypeXYZ
    c: int

    def __eq__(self, other: "CustomTypeABC") -> bool:  # type: ignore
        return self.a == other.a and self.b == other.b and self.c == other.c

    def sum_all(self) -> float:
        """Returns the sum of all fields."""
        return self.a + self.b.x + self.c


class CustomTypeWithEntityHandle(BaseModel):
    label: str = ""
    file: EntityHandle = NO_ENTITY


class CustomTypeWithEntityHandleCollections(BaseModel):
    files: list[EntityHandle] = []
    file_map: dict[str, EntityHandle] = {}
    nested: CustomTypeWithEntityHandle = CustomTypeWithEntityHandle()


class TransactionVerificationStep(StepModel):
    # Basic types
    sleepy_seconds: float = 10
    field_1: float = 0
    field_2: float = 0
    result: float = 0
    text_content: str | None = ""
    text_file: EntityHandle = NO_ENTITY
    text_file_2: EntityHandle = NO_ENTITY
    # Logging
    exception_type: str = "Exception"
    exception_message: str = "Exception message"
    # Custom types
    custom_object: CustomTypeXYZ | None = None
    custom_object_y: int = 0
    custom_object2: CustomTypeXYZ = CustomTypeXYZ(x=1, y=0, z=0)
    custom_object2_x: int = 0
    compound_custom_object: CustomTypeABC = CustomTypeABC(a=0, b=CustomTypeXYZ(x=0, y=0, z=0), c=0)
    optional_compound_custom_object: CustomTypeABC | None = None
    multiple_types_attribute: CustomTypeABC | CustomTypeXYZ | int = CustomTypeXYZ(x=1, y=0, z=0)
    custom_object_for_events: CustomTypeABC | None = None
    # Process
    child_process_pid: int = -1
    child_process_is_running: bool = False
    # Entity Handles
    file_entity: EntityHandle = NO_ENTITY
    image_entity: EntityHandle = NO_ENTITY
    e2e_file_entity_api: EntityHandle = NO_ENTITY
    e2e_file_entity_ui: EntityHandle = NO_ENTITY
    # Entity handles nested in data structures
    entity_handle_list: list[EntityHandle] = []
    entity_handle_dict: dict[str, EntityHandle] = {}
    entity_handle_object: CustomTypeWithEntityHandle = CustomTypeWithEntityHandle()
    nested_entity_handle_list: list[list[EntityHandle]] = []
    nested_entity_handle_dict: dict[str, dict[str, EntityHandle]] = {}
    entity_handle_collections: CustomTypeWithEntityHandleCollections = CustomTypeWithEntityHandleCollections()
    lock_id: str = ""

    @transaction(self=StepSpec(upload=["field_1"]))
    def set_field_1_to_1(self) -> None:
        self.field_1 = 1

    @transaction(self=StepSpec(download=["field_1"], upload=["field_2"]))
    def copy_field_1_to_field_2(self) -> None:
        self.field_2 = self.field_1

    @transaction(self=StepSpec(upload=["result"], download=["field_1", "field_2"]))
    def get_field_1_and_2_and_set_the_sum_in_result(self) -> None:
        """Run the documented sync transaction."""
        self.result = self.field_1 + self.field_2

    @transaction(self=StepSpec())
    def sum_two_floats_with_inputs_and_output(self, field_1: float, field_2: float) -> float:
        # Do not add a docstring here, as this is a test for the default description generation in MCP server.
        return field_1 + field_2

    @transaction(self=StepSpec())
    def use_solution_configuration(self, solution_configuration: SolutionConfiguration) -> None:
        _ = solution_configuration.glow_schema_version

    @transaction(self=StepSpec(upload=["result"], download=["field_1", "field_2", "sleepy_seconds"]))
    @long_running
    def lr_get_field_1_and_2_and_set_the_sum_in_result(self) -> None:
        """Run the documented long-running transaction."""
        time.sleep(self.sleepy_seconds)
        self.result = self.field_1 + self.field_2

    @transaction(self=StepSpec(download=["sleepy_seconds"]))
    @long_running
    def lr_sum_two_floats_with_inputs_and_output(self, field_1: float, field_2: float) -> float:
        # Do not add a docstring here, as this is a test for the default description generation in MCP server.
        time.sleep(self.sleepy_seconds)
        return field_1 + field_2

    @transaction(self=StepSpec(download=["field_1", "field_2"], upload=["custom_object2_x", "child_process_pid"]))
    def offset_fields_into_multiple_outputs(self, offset_1: float, offset_2: float) -> None:
        # Do not add a docstring here, as this is a test for the default description generation in MCP server.
        self.custom_object2_x = int(self.field_1 + offset_1)
        self.child_process_pid = int(self.field_2 + offset_2)

    @transaction(self=StepSpec())
    @long_running
    def lr_use_solution_configuration(self, solution_configuration: SolutionConfiguration) -> None:
        _ = solution_configuration.glow_schema_version

    @transaction(self=StepSpec(upload=["result"], download=["field_1", "field_2", "sleepy_seconds"]))
    @long_running
    def long_running_dummy(self) -> None:
        result = self.field_1 + self.field_2
        time.sleep(self.sleepy_seconds)
        self.result = result

    @transaction(self=StepSpec(upload=["result"], download=["field_1", "field_2", "sleepy_seconds"]))
    def sleep_dummy(self) -> None:
        result = self.field_1 + self.field_2
        time.sleep(self.sleepy_seconds)
        self.result = result

    @transaction(self=StepSpec(upload=["text_file"]))
    def create_text_file(self) -> None:
        storage_root = self.storage_scope.get_storage_root()
        f = storage_root / "projectFiles" / "file.txt"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(TEXT_FILE_DUMMY_STRING)
        self.text_file = self.storage_scope.store(f)

    @transaction(self=StepSpec())
    def create_text_outside_storage_scope(self) -> None:
        storage_root = self.storage_scope.get_storage_root()
        f = storage_root.parent.parent / "projectFiles" / "file.txt"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(TEXT_FILE_DUMMY_STRING)

    @transaction(self=StepSpec(download=["sleepy_seconds", "text_file"], upload=["text_file"]))
    @long_running
    def upload_file_periodically(self) -> None:
        st_time = time.time()
        max_time = 5
        storage_root = self.storage_scope.get_storage_root()
        filepath = storage_root / "file.txt"
        while True:
            filepath.write_text(str(random.random()))
            self.text_file = self.storage_scope.store(filepath)
            self.transaction.upload(["text_file"])
            time.sleep(self.sleepy_seconds)
            if time.time() - st_time >= max_time:
                break

    @transaction(self=StepSpec(download=["text_file"], upload=["text_content"]))
    def read_text_file(self) -> str:
        return self.storage_scope.get_text(self.text_file)

    @transaction(self=StepSpec(download=["text_file", "text_content"], upload=["text_content"]))
    def read_text_file_upload_content(self) -> None:
        if self.text_content is None:
            self.text_content = ""
        self.text_content += "/"
        self.text_content += self.storage_scope.get_text(self.text_file)

    @transaction(self=StepSpec(download=["text_file"], upload=["text_file_2"]))
    def process_file(self) -> None:
        modified_file = self.storage_scope.get_storage_root() / "my_second_file.txt"
        modified_file.write_text(
            "NOT " + self.storage_scope.get_text(self.text_file),
        )
        self.text_file_2 = self.storage_scope.store(modified_file)

    @transaction(self=StepSpec())
    def log_an_error(self) -> None:
        logger.error(LOGGING_ERROR_TESTING_STRING)

    @transaction(self=StepSpec())
    def log_a_warning(self) -> None:
        logger.warning(LOGGING_WARNING_TESTING_STRING)

    @transaction(self=StepSpec())
    def log_some_debug(self) -> None:
        logger.debug(LOGGING_DEBUG_TESTING_STRING)

    @transaction(self=StepSpec())
    def log_some_info(self) -> None:
        logger.info(LOGGING_INFO_TESTING_STRING)

    @transaction(self=StepSpec(download=["exception_message", "exception_type"]))
    def raise_exception(self) -> None:
        if self.exception_type == "Exception":
            raise Exception(self.exception_message)
        elif self.exception_type == "RuntimeError":
            raise RuntimeError(self.exception_message)
        elif self.exception_type == "BadRequestError":
            raise BadRequestError(self.exception_message)
        elif self.exception_type == "ModuleNotFoundError":
            import wrong_module  # noqa: F401 # type: ignore

    @transaction(self=StepSpec(download=["exception_message", "exception_type", "sleepy_seconds"]))
    @long_running
    def lr_raise_exception(self) -> None:
        time.sleep(self.sleepy_seconds)
        if self.exception_type == "Exception":
            raise Exception(self.exception_message)
        elif self.exception_type == "RuntimeError":
            raise RuntimeError(self.exception_message)
        elif self.exception_type == "BadRequestError":
            raise BadRequestError(self.exception_message)
        elif self.exception_type == "ModuleNotFoundError":
            import wrong_module  # noqa: F401 # type: ignore

    @transaction(self=StepSpec(upload=["text_content"]))
    def read_asset_file(self) -> None:
        handle = self.transaction.get_asset_entity_handle("asset_file1.txt")
        self.text_content = self.storage_scope.get_text(handle)

    @transaction(self=StepSpec(upload=["text_content"]))
    def read_asset_encrypted_file(self) -> None:
        handle = self.transaction.get_asset_entity_handle("asset_encrypted_file1_e.txt")
        self.text_content = self.storage_scope.get_text(handle)

    @transaction(self=StepSpec(upload=["text_content"]))
    def read_asset_file_with_special_chars(self) -> None:
        handle = self.transaction.get_asset_entity_handle("special_chars.txt")
        self.text_content = self.storage_scope.get_text(handle)

    @transaction(self=StepSpec(upload=["text_content"]))
    def read_asset_encrypted_file_with_special_chars(self) -> None:
        handle = self.transaction.get_asset_entity_handle("special_chars.txt")
        self.text_content = self.storage_scope.get_text(handle)

    @transaction(self=StepSpec(download=["custom_object2"], upload=["custom_object2_x"]))
    def ct2_x_parse(self) -> None:
        self.custom_object2_x = self.custom_object2.x

    @transaction(self=StepSpec(upload=["custom_object"]))
    def ct_init(self) -> None:
        self.custom_object = CustomTypeXYZ(x=1, y=2, z=3)

    @transaction(self=StepSpec(upload=["compound_custom_object"]))
    def comp_obj(self) -> None:
        self.compound_custom_object.a = 1
        self.compound_custom_object.b = CustomTypeXYZ(x=1, y=0, z=0)
        self.compound_custom_object.c = 3

    @transaction(self=StepSpec(upload=["optional_compound_custom_object"]))
    def comp_obj_with_init(self) -> None:
        self.optional_compound_custom_object = CustomTypeABC(a=1, b=CustomTypeXYZ(x=1, y=0, z=0), c=3)

    @transaction(self=StepSpec(download=["optional_compound_custom_object"]))
    def run_custom_object(self) -> float:
        if self.optional_compound_custom_object is None:
            raise ValueError("optional_compound_custom_object is None")
        return self.optional_compound_custom_object.sum_all()

    @transaction(self=StepSpec(download=["compound_custom_object"], upload=["multiple_types_attribute"]))
    def switch_type(self) -> None:
        self.multiple_types_attribute = self.compound_custom_object

    @transaction(self=StepSpec(upload=["child_process_pid"]))
    def start_process(self) -> None:
        self.child_process_pid = start_process()
        # check that it's still running and will be left running once the transaction finishes.
        assert psutil.pid_exists(self.child_process_pid)

    @transaction(self=StepSpec(upload=["child_process_pid"]))
    @long_running
    def start_process_in_long_running_method(self) -> None:
        self.child_process_pid = start_process()
        # check that it's still running and will be left running once the transaction finishes.
        assert psutil.pid_exists(self.child_process_pid)

    @transaction(self=StepSpec(upload=["child_process_pid"]))
    @long_running
    def start_and_teardown_process_in_long_running_method(self) -> None:
        subprocess_manager = SubprocessManager()
        self.child_process_pid = subprocess_manager.pid
        assert psutil.pid_exists(subprocess_manager.pid)

    @transaction(self=StepSpec(download=["child_process_pid"], upload=["child_process_is_running"]))
    def check_child_process_is_running(self) -> None:
        self.child_process_is_running = psutil.pid_exists(self.child_process_pid)

    @transaction(self=StepSpec(download=["child_process_pid"]))
    def kill_process(self) -> None:
        psutil.Process(self.child_process_pid).kill()

    @transaction(self=StepSpec(download=["sleepy_seconds"]))
    def block_process(self) -> None:
        # Acquire the GIL and share the status
        gil_state = ctypes.pythonapi.PyGILState_Ensure()
        # hack to write a file within the project directory
        gil_lock_file = self.storage_scope.get_storage_root().parent.parent / "gil_lock.txt"
        gil_lock_file.write_text("GIL LOCKED")

        # Sleep for a few seconds
        if platform.system() != "Linux":
            sleep_functype = ctypes.PYFUNCTYPE(None, ctypes.c_uint)
            wrapped_sleep = sleep_functype(("Sleep", ctypes.windll.kernel32))  # type: ignore
            wrapped_sleep(int(self.sleepy_seconds) * 1000)
        else:
            libc = ctypes.PyDLL(None)
            libc.sleep(int(self.sleepy_seconds))

        # Release the GIL
        ctypes.pythonapi.PyGILState_Release(gil_state)

    @transaction(self=StepSpec(download=["sleepy_seconds"], upload=["text_content"]))
    @long_running
    def block_process_long_running(self) -> None:
        # Acquire the GIL and share the status
        gil_state = ctypes.pythonapi.PyGILState_Ensure()
        self.text_content = "GIL LOCKED"
        self.transaction.upload(["text_content"])

        # Sleep for a few seconds
        if platform.system() != "Linux":
            sleep_functype = ctypes.PYFUNCTYPE(None, ctypes.c_uint)
            wrapped_sleep = sleep_functype(("Sleep", ctypes.windll.kernel32))  # type: ignore
            wrapped_sleep(int(self.sleepy_seconds) * 1000)
        else:
            libc = ctypes.PyDLL(None)
            libc.sleep(int(self.sleepy_seconds))

        # Release the GIL
        ctypes.pythonapi.PyGILState_Release(gil_state)

    @transaction(self=StepSpec())
    def trigger_event(self) -> None:
        self.transaction.raise_event(message={"message": "testing!"}, stream_name="my-stream")

    @transaction(self=StepSpec(download=["field_1"]))
    def trigger_event_with_field_1(self) -> None:
        self.transaction.raise_event(message=self.field_1, stream_name="my-stream")

    @transaction(self=StepSpec(download=["custom_object_for_events"]))
    def stream_custom_data(self) -> None:
        self.transaction.raise_event(message=self.custom_object_for_events, stream_name="my-custom-data-stream")

    @transaction(self=StepSpec())
    def trigger_second_event(self) -> None:
        self.transaction.raise_event(message={"message": "testing_second!"}, stream_name="my-stream-second")

    @transaction(self=StepSpec())
    def trigger_multiple_events(self) -> None:
        for i in range(3):
            time.sleep(0.3)
            self.transaction.raise_event(message={"message": i}, stream_name="multiple-events-stream")

    @transaction(self=StepSpec())
    def another_trigger_event(self) -> None:
        self.transaction.raise_event(message={"message": "further testing!"}, stream_name="my-third-stream")

    @transaction(self=StepSpec(), enable_termination_event=True)
    def trigger_termination_event(self) -> None:
        return

    @transaction(self=StepSpec())
    def dont_trigger_termination_event(self) -> None:
        return

    @transaction(self=StepSpec(), enable_termination_event=True)
    @long_running
    def trigger_termination_event_long_running(self) -> None:
        return

    @transaction(self=StepSpec(), enable_termination_event=True)
    def trigger_failed_termination_event(self) -> None:
        raise ValueError("This transaction is forced to fail")

    @transaction(self=StepSpec(upload=["custom_object_y"]))
    def process_input_before_uploading(self, y: int) -> None:
        self.custom_object_y = y**2

    @transaction(self=StepSpec(download=["custom_object_y"]))
    def build_and_return_custom_type(self, x: int, z: int) -> CustomTypeXYZ:
        return CustomTypeXYZ(x=x, y=self.custom_object_y, z=z)

    @transaction(self=StepSpec(upload=["custom_object"]))
    def store_custom_type_from_client(self, ct: CustomTypeXYZ) -> None:
        self.custom_object = ct

    @transaction(self=StepSpec(upload=["file_entity"]))
    def store_file_entity_with_text(self, text: str) -> None:
        file_entity_path = self.storage_scope.get_storage_root() / "file.txt"
        file_entity_path.write_text(text)
        self.file_entity = self.storage_scope.store(file_entity_path)

    @transaction(self=StepSpec(upload=["image_entity"]))
    def store_image_entity(self, source_path: str) -> None:
        logo_path = self.storage_scope.get_storage_root() / "logo.png"
        logo_path.write_bytes(Path(source_path).read_bytes())
        self.image_entity = self.storage_scope.store(logo_path)

    @transaction(self=StepSpec(upload=["e2e_file_entity_api"]))
    def store_data_content_into_file_entity(self, file_content: bytes, file_name: str):
        file_entity_path = self.storage_scope.get_storage_root() / file_name
        file_entity_path.write_bytes(file_content)
        self.e2e_file_entity_api = self.storage_scope.store(file_entity_path)

    @transaction(
        self=StepSpec(download=["e2e_file_entity_api", "e2e_file_entity_ui"]),
    )
    def use_project_cached_at_ui(self) -> bool:
        return self.storage_scope.get_bytes(self.e2e_file_entity_api) == self.storage_scope.get_bytes(
            self.e2e_file_entity_ui,
        )

    @transaction(self=StepSpec())
    def launch_python_script(self) -> str:
        handle = self.transaction.get_asset_entity_handle("asset_script.py")
        script_path = self.storage_scope.get_cached(handle)
        return subprocess.check_output(["python", str(script_path)]).strip().decode()

    @transaction(self=StepSpec())
    def launch_encrypted_python_script(self) -> str:
        handle = self.transaction.get_asset_entity_handle("asset_encrypted_script.py")
        script_path = self.storage_scope.get_cached(handle)
        return subprocess.check_output(["python", str(script_path)]).strip().decode()

    @transaction(self=StepSpec())
    def is_glow_src_readable(self) -> bool:
        import inspect

        try:
            inspect.getsource(StepSpec)
        except OSError:
            return False
        else:
            return True

    @transaction(self=StepSpec())
    def get_env_var(self, var_name: str) -> str:
        return os.getenv(var_name, "")

    @transaction(self=StepSpec(upload=["text_content"]))
    @long_running
    def n_second_async(self, sleep_seconds: int = 1):
        time.sleep(sleep_seconds)
        self.text_content = str(sleep_seconds)

    @transaction(self=StepSpec(upload=["text_content"]))
    def n_second_sync(self, sleep_seconds: int = 1):
        time.sleep(sleep_seconds)
        self.text_content = str(sleep_seconds)

    @transaction(self=StepSpec(download=["field_1"]))
    def log_http_client_headers(self) -> None:
        for _ in range(10):
            http_auth_headers = str(self._http_client.headers.get("Authorization", "")).removeprefix("Bearer ")  # type: ignore
            graphql_auth_headers = self._graphql_client.access_token or ""  # type: ignore
            logger.warning(
                f"AUTH_HEADERS request_id={int(self.field_1)} http={http_auth_headers} graphql={graphql_auth_headers}",
            )
            time.sleep(0.25)

    @transaction(self=StepSpec(download=["field_1"]))
    @long_running
    def log_http_client_headers_long_running(self) -> None:
        for _ in range(10):
            http_auth_headers = str(self._http_client.headers.get("Authorization", "")).removeprefix("Bearer ")  # type: ignore
            graphql_auth_headers = self._graphql_client.access_token or ""  # type: ignore
            logger.warning(
                f"AUTH_HEADERS request_id={int(self.field_1)} http={http_auth_headers} graphql={graphql_auth_headers}",
            )
            time.sleep(0.25)

    @transaction()
    def return_http_client(self) -> str:  # type: ignore
        """Return the HTTP client associated with this transaction."""
        return str(self._http_client)  # type: ignore

    @transaction(
        enable_termination_event=True,
        self=StepSpec(download=["field_1", "field_2"]),
    )
    def trigger_events(self) -> float:
        result = self.field_1 + self.field_2
        self.transaction.raise_event(message={"message": "testing!"}, stream_name="my-stream")
        self.transaction.raise_event(message={"message": result}, stream_name="my-stream")
        return result
