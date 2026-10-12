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

from typing import Any
from unittest.mock import patch

from ansys.platform.instancemanagement.exceptions import (  # pyright: ignore[reportMissingTypeStubs]
    UnsupportedProductError,
)
import grpc
import pytest

from ansys.saf.glow._core.instance.hps_system import TaskDefinition
from ansys.saf.glow._core.instance.iinstance_system import (
    IProductInstance,
    IProductInstanceSystem,
)
from ansys.saf.glow._core.instance.manager import JOB_DEFAULT_MAX_RUNNING_TIME
from ansys.saf.testing.solution.const import TestProductInstanceSystemType
from tests.integration.conftest import assert_instance, assert_instance_deleted

MAX_EXECUTION_TIME = 60


@pytest.mark.parametrize(
    "instance_system_type",
    [pytest.param("PIM", marks=pytest.mark.use_pim), pytest.param("HPS", marks=pytest.mark.use_hps), "_MOCK"],
    indirect=True,
)
@pytest.mark.parametrize("product_name", ["custom-grpc-product", "custom-http-product", "custom-tcp-product"])
class TestProductInstanceSystem:
    def test_product_instance_system_can_run_single_instance(
        self,
        product_name: str,
        product_instance_system: IProductInstanceSystem,
    ):
        try:
            instance = product_instance_system.create_instance(
                product_name,
                JOB_DEFAULT_MAX_RUNNING_TIME,
            )
            try:
                assert_instance(instance, product_name)
            finally:
                instance.delete()
                assert_instance_deleted(instance, product_name)
        finally:
            product_instance_system.close()

    def test_product_instance_system_can_run_specific_version(
        self,
        product_name: str,
        product_instance_system: IProductInstanceSystem,
    ):
        try:
            instance = product_instance_system.create_instance(
                product_name,
                JOB_DEFAULT_MAX_RUNNING_TIME,
                product_version="2",
            )
            try:
                assert_instance(instance, product_name, product_version="2")
            finally:
                instance.delete()
                assert_instance_deleted(instance, product_name)
        finally:
            product_instance_system.close()

    def test_product_instance_system_can_find_created_instance(
        self,
        product_instance_system: IProductInstanceSystem,
        product_name: str,
    ):
        try:
            instance = product_instance_system.create_instance(
                product_name,
                JOB_DEFAULT_MAX_RUNNING_TIME,
            )
            retrieved_instance = product_instance_system.get_instance(instance.name)
            assert retrieved_instance
            assert instance.name == retrieved_instance.name
            assert instance.definition_name == retrieved_instance.definition_name
            instance.delete()
            assert_instance_deleted(instance, product_name)
        finally:
            product_instance_system.close()

    def test_product_instance_system_can_delete_not_found_instance(
        self,
        product_instance_system: IProductInstanceSystem,
        product_name: str,
        instance_system_type: TestProductInstanceSystemType,
    ):
        try:
            instance = product_instance_system.create_instance(
                product_name,
                JOB_DEFAULT_MAX_RUNNING_TIME,
            )
            instance.delete()
            assert_instance_deleted(instance, product_name)
            # We can delete twice if we use the flag missing_ok
            instance.delete(missing_ok=True)
            match instance_system_type:
                case TestProductInstanceSystemType._MOCK:  # pyright: ignore[reportPrivateUsage]
                    expected_exception = FileNotFoundError
                case TestProductInstanceSystemType.HPS:
                    expected_exception = RuntimeError
                case TestProductInstanceSystemType.PIM:
                    expected_exception = grpc.RpcError
            with pytest.raises(expected_exception):
                instance.delete()
        finally:
            product_instance_system.close()

    def test_product_instance_system_cannot_find_a_deleted_instance(
        self,
        product_instance_system: IProductInstanceSystem,
        product_name: str,
    ):
        try:
            instance = product_instance_system.create_instance(
                product_name,
                JOB_DEFAULT_MAX_RUNNING_TIME,
            )
            instance_name = instance.name
            instance.delete()
            assert_instance_deleted(instance, product_name)
            assert product_instance_system.get_instance(instance_name) is None
        finally:
            product_instance_system.close()

    def test_product_instance_system_can_run_two_concurrent_instances(
        self,
        product_instance_system: IProductInstanceSystem,
        product_name: str,
    ):
        instance1 = product_instance_system.create_instance(
            product_name,
            JOB_DEFAULT_MAX_RUNNING_TIME,
        )
        try:
            instance2 = product_instance_system.create_instance(
                product_name,
                JOB_DEFAULT_MAX_RUNNING_TIME,
            )
            try:
                assert_instance(instance1, product_name)
                assert_instance(instance2, product_name)
            finally:
                instance2.delete()
                assert_instance_deleted(instance2, product_name)
        finally:
            instance1.delete()
            assert_instance_deleted(instance1, product_name)
            product_instance_system.close()

    def test_instance_max_execution_time(
        self,
        product_instance_system: IProductInstanceSystem,
        instance_system_type: TestProductInstanceSystemType,
        product_name: str,
    ):
        if instance_system_type != TestProductInstanceSystemType.HPS:
            pytest.skip(f"{instance_system_type.value} doesn't support max_execution_time yet.")
        original_task_definition_init = TaskDefinition.__init__  # type: ignore

        def mock_task_definition_init(*args: Any, **kwargs: Any):
            assert kwargs.get("max_execution_time") == MAX_EXECUTION_TIME
            original_task_definition_init(*args, **kwargs)

        with patch.object(TaskDefinition, "__init__", mock_task_definition_init):
            instance: IProductInstance | None = None
            try:
                instance = product_instance_system.create_instance(
                    product_name,
                    MAX_EXECUTION_TIME,
                )
                assert_instance(instance, product_name)
            finally:
                if instance:
                    instance.delete()
                    assert_instance_deleted(instance, product_name)
                product_instance_system.close()


@pytest.mark.parametrize(
    "instance_system_type",
    [pytest.param("PIM", marks=pytest.mark.use_pim), pytest.param("HPS", marks=pytest.mark.use_hps), "_MOCK"],
    indirect=True,
)
class TestProductInstanceSystemWrongInputs:
    def test_product_instance_system_raises_error_for_unsupported_product(
        self,
        product_instance_system: IProductInstanceSystem,
    ):
        try:
            with pytest.raises(RuntimeError, match="No configuration matches product fake-product"):
                product_instance_system.create_instance(
                    "fake-product",
                    JOB_DEFAULT_MAX_RUNNING_TIME,
                )
        finally:
            product_instance_system.close()

    def test_product_instance_system_raises_error_for_unsupported_version(
        self,
        product_instance_system: IProductInstanceSystem,
        instance_system_type: TestProductInstanceSystemType,
    ):
        match instance_system_type:
            case TestProductInstanceSystemType._MOCK:  # pyright: ignore[reportPrivateUsage]
                expected_error_class = ValueError
                expected_error_msg = (
                    "The product instance system does not support custom-grpc-product in version 0. "
                    "Available versions: 1, 2, 222."
                )
            case TestProductInstanceSystemType.HPS:
                expected_error_class = TimeoutError
                expected_error_msg = "Timed out waiting for instance instances/custom-grpc-product"
            case TestProductInstanceSystemType.PIM:
                expected_error_class = UnsupportedProductError
                expected_error_msg = "The remote server does not support custom-grpc-product in version 0."

        try:
            with pytest.raises(expected_error_class, match=expected_error_msg):
                product_instance_system.create_instance(
                    "custom-grpc-product",
                    JOB_DEFAULT_MAX_RUNNING_TIME,
                    product_version="0",
                )
        finally:
            product_instance_system.close()
