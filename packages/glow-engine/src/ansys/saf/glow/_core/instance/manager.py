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

from abc import ABC, abstractmethod
import logging
from pathlib import Path, PurePath
import random
import shutil
import string
from types import TracebackType
from typing import Any, Generic, Protocol, Self, TypeVar, cast, get_args

from pydantic import ValidationError

from ansys.bdm.api import EntityHandle, IStorageScope
from ansys.saf.glow._bdm.storage_contexts import PRODUCT_CONTEXT, PRODUCT_MANAGER_CONTEXT
from ansys.saf.glow._config.const import JOB_DEFAULT_MAX_RUNNING_TIME
from ansys.saf.glow._core.exceptions import SolutionLoadException
from ansys.saf.glow._core.instance.identification import (
    AbstractInstanceIdentificationClient,
    CreateInstanceRecord,
    InstanceRecord,
    UnsharedProductIdentificationClient,
    UpdateInstanceRecord,
)
from ansys.saf.glow._core.instance.iinstance_system import (
    IProductInstance,
    IProductInstanceService,
    IProductInstanceSystem,
)
from ansys.saf.glow._core.instance.recoverystate import TRecoveryStateInfo
from ansys.saf.glow._core.instance.storagescope import ProductStorageScope
from ansys.saf.glow._executor.local import transaction_local
from ansys.saf.glow._server.exceptions import BadRequestError, MalformedSolutionError

logger = logging.getLogger(__name__)

TProductClient = TypeVar("TProductClient")
TProductClient_cov = TypeVar("TProductClient_cov", covariant=True)


class IInstanceManager(Protocol, Generic[TProductClient_cov]):
    def __init__(self, **kwargs: Any) -> None:
        """The interface that is publicly exposed and consumed by solution developers for product instance management.
        This is the contract that must be shared by both the internal
        ``InstanceManager`` implementation and the public ``ProductInstanceManager``.
        """
        ...

    @property
    def instance(self) -> TProductClient_cov:
        """The underlying product client."""
        ...

    @classmethod
    def get_versions(cls) -> list[str]:
        """Return a list of versions of the product that are available in this deployment
        that can be accessed as product instances.

        Returns
        -------
        ``list of str``
            Return a list of versions of the product that are available in this deployment
            that can be accessed as shared product instances. Any value in the list can be passed
            to the ``initialize`` method (on a derived class) to indicate the version of the instance to be created.
        """
        ...

    @property
    def product_version(self) -> str:
        """Get the version of the current running product instance."""
        ...

    def shutdown(self) -> None:
        """Shut the product instance down."""
        ...

    def is_instance_healthy(self) -> bool:
        """Return if the instance is healthy."""
        ...


class InstanceManagerBase(ABC, Generic[TRecoveryStateInfo]):
    """Internal generic class for internal implementation of product instances managers.

    Should not be used for implementing an internal instance manager. Use ``InstanceManager``, instead.

    |saf-docs-instance-management-ref|_ explains the concept of product
    instances in more detail.
    """

    _product_instance_system_cls: IProductInstanceSystem | None = None  # must only be used for classmethods
    recovery_state_info_type: type[TRecoveryStateInfo]

    def __init__(
        self,
        instance_identification: AbstractInstanceIdentificationClient[TRecoveryStateInfo],
        max_execution_time: int | None = None,
    ) -> None:
        self._identification_client = instance_identification
        self._project_directory_path_on_solution = transaction_local.project_directory
        self._max_execution_time = max_execution_time or JOB_DEFAULT_MAX_RUNNING_TIME
        self._record_cache: InstanceRecord[TRecoveryStateInfo] | None = None
        self._client: Any | None = None
        self._was_instance_shutdown: bool = False
        self._recovery_state_info: TRecoveryStateInfo | None = None
        self._instance: IProductInstance | None = None
        self._product_storage_scope: ProductStorageScope | None = None
        self._manager_storage_scope: IStorageScope | None = None
        self._settings = transaction_local.settings
        self._product_instance_system = transaction_local.instance_system_factory.create_system(
            self._settings.computed_glow_product_instance_system_uri,  # type: ignore
        )
        self._state_dirname: str = ""

        # Reload configurations since long running spawn new process
        # that doesn't have the context of the parent process.
        self._product_instance_system.load_configurations_from_solution(self._settings.computed_definition_module)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._was_instance_shutdown:
            # shutdown has already disposed the instance manager
            self._product_instance_system.close()
            return
        if exc_type is None:
            # Store state only if no exception was raised
            self.store_state()
        self.dispose()
        self._product_instance_system.close()

    def dispose(self) -> None:
        """Dispose the instance manager by resetting its data so that we are sure it cannot be reused
        without reinitializing it.
        This is called at the end of the transaction method."""
        self.close_client()
        self._instance = None
        self._client = None
        self._record_cache = None
        if self._product_storage_scope:
            self._product_storage_scope._exit()  # pyright: ignore[reportPrivateUsage]
        self._recovery_state_info = None

    def initialize_service(self, service_name: str, product_version: str | None = None) -> None:
        """Initialize the product instance manager and create the product instance.
        This method must be called within the ``initialize()`` implementation of the
        internal product instance manager subclass.

        Parameters
        ----------
        service_name: str
            This is the name of the service that is exposed by the saf product configuration
            that identifies it from other services.
            It should be consistent with the name used in the PIM light and HPS configurations.
            Typically its something simple like ``grpc`` or ``http``.
        product_version: str, optional
            The version of the product instance that must be used.
            If not specified, the latest version specified from the saf product configuration will be used.

        Notes
        -----
        It is the sole entry point to make the product instance manager fully functioning.
        Without calling it, you won't be able to interact with a product instance properly.

        If a product instance has already been running while this method is called,
        the product instance is restarted and its previous state is discarded.
        """
        self._record_cache = self._identification_client.get()
        if self._record_cache is not None:
            # an instance already exists
            if self._find_instance() is not None:
                # the instance is still running -> shutdown and clean up that product instance
                # (need to reconnect to instance to shut it down properly using the client etc...)
                self._reconnect(restart_if_instance_down=False)
                self._stop()
            else:
                self._restore_recovery_state_info()
            self._clean_state()
            self.dispose()

        self._instance = self._create_instance(self._max_execution_time, product_version)
        self._record_cache = self._identification_client.add(
            CreateInstanceRecord[self.recovery_state_info_type](
                pim_name=self._instance.name,
                service_name=service_name,
                product_version=self._instance.version,
                max_execution_time=self._max_execution_time,
            ),
        )
        alphabet = string.ascii_lowercase + string.digits
        self._state_dirname = f"is_{''.join(random.choices(alphabet, k=8))}"  # noqa: S311 #nosec
        self._set_product_storage_scopes()

    def _set_product_storage_scopes(self):
        if self._product_storage_scope is not None:
            self._product_storage_scope._exit()  # pyright: ignore[reportPrivateUsage]
        if self._manager_storage_scope is not None:
            self._manager_storage_scope.__exit__(None, None, None)
        storage_scope_factory = transaction_local.multiplexor_storage_factory
        product_storage_scope_on_solution = storage_scope_factory.create_storage_scope(
            PRODUCT_CONTEXT,
        ).__enter__()

        project_directory_path_on_product = self._get_project_directory_path_on_product()
        self._product_storage_scope = ProductStorageScope(
            storage_scope=product_storage_scope_on_solution,
            project_directory_path_on_solution=self._project_directory_path_on_solution,
            project_directory_path_on_product=project_directory_path_on_product,
            state_directory_name=self._state_dirname,
        )

        self._manager_storage_scope = storage_scope_factory.create_storage_scope(
            PRODUCT_MANAGER_CONTEXT,
        ).__enter__()

    def reconnect(self, instance_record: InstanceRecord[TRecoveryStateInfo] | None = None) -> None:
        """Connect the product instance manager to an already created product instance.

        (This is called internally before executing the @instance decorated transaction.)

        Parameters
        ----------
        restart_if_instance_down: bool
            Specifies whether the product instance must be restarted in case it is down.
        """
        pre_existing_record = instance_record or self._identification_client.get()
        if pre_existing_record is None:
            raise BadRequestError(
                "The method has been called out of sequence. "
                + "A shared product instance that this method uses has not been initialized.",
            )
        self._record_cache = pre_existing_record
        self._reconnect(restart_if_instance_down=instance_record is None)
        self._set_product_storage_scopes()

    def _reconnect(self, restart_if_instance_down: bool = False):
        instance = self._find_instance()
        need_restart = instance is None and restart_if_instance_down
        if need_restart:
            # Product instance is down (max_execution_time exceeded, crash etc..)
            # Let's restart it based on the information of the record.
            instance = self._restore_instance()
        self._instance = instance
        self._restore_recovery_state_info()
        self._set_product_storage_scopes()
        if need_restart:
            self.restore_state()

    def _create_instance(self, max_execution_time: int, product_version: str | None = None) -> IProductInstance:
        product_name = self.get_product_name_implement()
        instance = self._product_instance_system.create_instance(product_name, max_execution_time, product_version)
        return instance

    def _restore_instance(self) -> IProductInstance:
        instance = self._create_instance(
            self._record.max_execution_time,
            self._record.product_version,
        )
        self._record_cache = self._identification_client.update(
            UpdateInstanceRecord[self.recovery_state_info_type](pim_name=instance.name),
        )
        product_name = self.get_product_name_implement()
        logger.info(f"Restarting {product_name}-instance")
        return instance

    @property
    def _record(self) -> InstanceRecord[TRecoveryStateInfo]:
        if self._record_cache is None:
            raise RuntimeError("The product instance manager has not been initialized.")
        return self._record_cache

    @property
    def product_storage_scope(self) -> ProductStorageScope:
        """The storage scope of the remote product.
        Unlike the ``manager_storage_scope``, it resolves paths of entity handles from the product itself.
        Its methods use file paths that are only valid in the context of the product.
        For example the ``store`` method expects file paths returned by the product api and the ``get_cached``
        method returns file paths that can be passed to the product api.

        Notes
        -----
        Since the product instance manager itself is running within the solution,
        its product storage scope cannot be used to create files and directories on the remote product itself.

        If you need to create a file from the manager that is to be used from the remote product,
        you can do the following:
        - use the manager_storage_scope to create the file:
          >>> my_file = self.manager_storage_scope.get_storage_root() / "my_file.txt"
          >>> my_file.write_text("data")
        - store the file as entity handle on the manager_storage_scope
          >>> my_file_handle = self.manager_storage_scope.store(my_file)
        - access the file handle from the remote product using the product storage scope
          >>> my_file_on_product = self.product_storage_scope.get_cached(my_file_handle)
          >>> self.instance.use_file(my_file_on_product)
        """
        if self._product_storage_scope is None:
            raise RuntimeError("The product storage scope of the product instance manager has not been initialized.")
        return self._product_storage_scope

    @property
    def manager_storage_scope(self) -> IStorageScope:
        """The storage scope of the product instance manager.
        Unlike the ``product_storage_scope``, it resolves path of entity handles on the solution itself.

        Notes
        -----
        It can be used to create files and directories from the manager that are to be used from the remote product.
        (see note on ``product_storage_scope``)
        """
        if self._manager_storage_scope is None:
            raise RuntimeError("The manager storage scope of the product instance manager has not been initialized.")
        return self._manager_storage_scope

    def _get_project_directory_path_on_product(self) -> PurePath:
        service = self._get_service()
        if service.project_files_directory:
            project_files_directory = service.project_files_directory
            project_id = self._project_directory_path_on_solution.name
            product_path = project_files_directory / project_id
        else:
            logger.info(
                "Field `project_files_directory` not set by the product instance system. "
                + "Assuming that product process is in same environment as solution.",
            )
            product_path = PurePath(self._project_directory_path_on_solution)
        logger.info(f"path to project directory in Solution process: {product_path}")
        return product_path

    @property
    def product_version(self) -> str:
        """The version of the product instance used."""
        return self._record.product_version

    @property
    def recovery_state_info(self) -> TRecoveryStateInfo:
        """Get access to the stored recovery state information needed to restore a product instance.

        This can be used for example within ``load_state_implement`` to load the product instance
        with the same values that were passed

        Examples
        --------
        >>> class MyRecoveryStateInfo(RecoveryStateInfo):
        >>>     project_file: EntityHandle = NO_ENTITY
        >>>     product_value: int = 0

        >>> class InternalInstanceManager(InstanceManager[Product]):
        >>>    ...
        >>>
        >>>     def load_state_implement(self, protected_state_directory_path: str) -> None:
        >>>         # Re-opening the product instance with the values previously stored into the
        >>>         # recovery state info
        >>>         project_file_absolute_path = self.storage_scope.get_cached(self.recovery_state_info.project_file)
        >>>         self.instance.open(project_file_absolute_path, state_info.product_value)
        """
        if self._recovery_state_info is None:
            raise MalformedSolutionError("The recovery state info cannot be retrieved because it has not been set")
        return self._recovery_state_info

    @recovery_state_info.setter
    def recovery_state_info(self, state_info: TRecoveryStateInfo) -> None:
        """Set the state information that need to be persisted so that they can be reused when reloading
        a product instance.

        A good usage example is to use the recovery state info to store the values passed to the
        instance manager's ``initialized`` method so that the same values can be reused within
        the ``load_state_implement``.

        Examples
        --------
        >>> class MyRecoveryStateInfo(RecoveryStateInfo):
        >>>     project_file: EntityHandle = NO_ENTITY
        >>>     product_value: int = 0

        >>> class InternalInstanceManager(InstanceManager[Product]):
        >>>
        >>>     def initialize(
        >>>         self,
        >>>         project_file: EntityHandle
        >>>         product_value: int
        >>>     ):
        >>>         self.initialize_service(SERVICE_NAME, version)
        >>>
        >>>         # Store the values passed in initialize within the recovery state info model
        >>>         # so that it can be reused when restoring the product instance.
        >>>         self.recovery_state_info = MyStateInfo(
        >>>             product_value=product_value,
        >>>             project_file=project_file
        >>>         )
        """
        self._recovery_state_info = state_info
        self._recovery_state_info.product_instance_state_dirname = self._state_dirname
        (self._project_directory_path_on_solution / self._recovery_state_info.product_instance_state_dirname).mkdir(
            parents=True,
            exist_ok=True,
        )

    def store_state(self) -> None:
        """Store the state of the product instance.
        This calls the ``save_state_implement`` from the concrete instance manager implementation,
        and dumps the recovery state info.

        Notes
        -----
        This is called automatically on the completion of a transaction method.
        """
        if not self._was_instance_shutdown:
            self.save_state_implement()
            if self._recovery_state_info:
                # TODO: Only update recovery state info it has been modified from its previous state.
                self._record_cache = self._identification_client.update(
                    UpdateInstanceRecord[self.recovery_state_info_type](recovery_state_info=self._recovery_state_info),
                )

    @property
    def state_directory(self) -> PurePath:
        """The product instance state directory path of the remote product.
        This directory can be used to persist any data required to store/restore the state of an instance.

        Notes
        -----
        The path that is only valid in the context of the product and therefore cannot be used to store files
        directly from the solution side.
        Instead, this path needs to be passed to the product api in order to be used properly.
        For example, if the product has a method to save data to a specific directory, you can do the following:
        >>> self.instance.save_data(self.state_directory / "data_file.dat")

        In case you would like to store files from the solution side into that directory, you can use the
        ``copy_to_state_directory`` method instead.
        """
        return self._get_project_directory_path_on_product() / self.recovery_state_info.product_instance_state_dirname

    def copy_to_state_directory(self, source: EntityHandle | Path, target_relative_path: Path) -> None:
        """Save a copy of the file or directory from the solution to the product instance state directory.

        Parameters
        ----------
        source : ``EntityHandle | Path``
            The file or directory from the solution to be saved to the state directory.
        target_relative_path : ``Path``
            The relative path (within the product instance state directory) where the file or directory
            must be copied.

        Examples
        --------
        Let us consider a product instance manager allowing a project file to be used to initialize
        the product instance.
        In such case, you can use this method to copy the project file from the solution into the
        product instance state directory as follows:

        def initialize(
            self,
            project_file: EntityHandle,
            version: str | None = None,
        ) -> None:
            self.initialize_service(self.SERVICE_NAME, version)
            project_filename = "project.dat"
            recovery_state_info = MyRecoveryStateInfo(project_filename=project_filename, version=version)
            self.recovery_state_info = recovery_state_info
            # Now copy the project file from the solution into the product instance state directory
            self.copy_to_state_directory(project_file, project_filename)
        """
        if target_relative_path.is_absolute():
            raise ValueError("The target relative path must be a relative path.")
        target = (
            self._project_directory_path_on_solution
            / self.recovery_state_info.product_instance_state_dirname
            / target_relative_path
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(source, Path):
            shutil.copytree(source, target) if source.is_dir() else shutil.copyfile(source, target)
        else:
            self.manager_storage_scope.get_copy(source, target)

    def _restore_recovery_state_info(self) -> None:
        if self._record.recovery_state_info is not None:
            self._recovery_state_info = self._record.recovery_state_info
            self._state_dirname = self._recovery_state_info.product_instance_state_dirname

    def restore_state(self) -> None:
        """Restore the state of the product instance.
        This calls the ``load_state_implement`` from the concrete instance manager implementation,
        and restore the recovery state info.

        Notes
        -----
        This is called by the @instance decorator when the product instance needs to be restarted.
        """
        self._restore_recovery_state_info()
        self.load_state_implement()

    def _stop(self) -> None:
        if self._find_instance():
            self.shutdown_implement()
            # race condition, shutdown_implement may kill the instance itself, and find_instance() is executed
            # before the product instance manager has time to detect that the instance was killed
            # and clean everything up, so this .delete() fails to find the instance.
            self._delete_instance()

    def _clean_state(self):
        shutil.rmtree(
            self._project_directory_path_on_solution / self.recovery_state_info.product_instance_state_dirname,
            ignore_errors=True,
        )
        self._identification_client.delete()

    def _delete_instance(self):
        instance = self._find_instance()
        if instance is None:
            return
        instance.delete(missing_ok=True)

    def shutdown(self) -> None:
        """Shut the product instance down and dispose the product instance manager.
        This calls the ``shutdown_implement`` from the concrete instance manager implementation.
        """
        self._stop()
        self._clean_state()
        self.dispose()
        self._was_instance_shutdown = True

    @property
    def was_instance_shutdown(self) -> bool:
        """Specifies whether the product instance has been explicitly shutdown."""
        return self._was_instance_shutdown

    @abstractmethod
    def save_state_implement(self) -> None:
        """Save the state of the product instance.

        Subclasses must implement the logic required to store the state of the product instance.
        """
        raise NotImplementedError()

    @abstractmethod
    def load_state_implement(self) -> None:
        """Load the state of the product instance.

        Subclasses must implement the logic required to restore the state of the product instance.
        """
        raise NotImplementedError()

    @abstractmethod
    def shutdown_implement(self) -> None:
        """Gracefully terminates the product instance.

        Subclasses may implement the logic needed to properly shut down the product instance.
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def get_product_name_implement(cls) -> str:
        """Return the name of the product in the product instance system (PIM or HPS) environment."""
        raise NotImplementedError()

    @classmethod
    def _check_product_instance_system(cls) -> IProductInstanceSystem:
        if cls._product_instance_system_cls is None:
            cls._product_instance_system_cls = transaction_local.instance_system_factory.create_system(
                transaction_local.settings.computed_glow_product_instance_system_uri,  # type: ignore
            )
            # Reload configurations since long running spawn new process
            # that doesn't have the context of the parent process.
            cls._product_instance_system_cls.load_configurations_from_solution(
                transaction_local.settings.computed_definition_module,
            )
        return cls._product_instance_system_cls

    def _find_instance(self) -> IProductInstance | None:
        return self._product_instance_system.get_instance(self._record.pim_name)

    def _get_service(self) -> IProductInstanceService:
        service_name = self._record.service_name
        if self._instance is None:
            raise RuntimeError("The product instance manager has not been initialized.")
        return self._instance.services[service_name]

    def is_instance_healthy(self) -> bool:
        if instance := self._find_instance():
            return instance.is_healthy()
        return False

    def _create_client(self) -> Any:
        service = self._get_service()
        self._restore_recovery_state_info()
        client = self.get_untyped_client_object_for_base(service.host, service.port)
        return client

    def _get_or_create_client(self) -> Any:
        if self._was_instance_shutdown:
            raise RuntimeError("The product instance manager has been shutdown and cannot be used anymore.")
        if self._client is None:
            self._client = self._create_client()
        return self._client

    @abstractmethod
    def get_untyped_client_object_for_base(self, hostname: str, port: int) -> Any:
        raise NotImplementedError()

    @abstractmethod
    def close_client(self) -> None:
        """Close the product specific client object."""
        ...

    @classmethod
    def get_versions(cls) -> list[str]:
        """Return a list of versions of the product that are available in this deployment
        that can be accessed as product instances.

        Returns
        -------
        ``list of str``
            Return a list of versions of the product that are available in this deployment
            that can be accessed as product instances. Any value in the list can be passed
            to the ``initialize`` method (on a derived class) to indicate the version of the instance to be created.
        """
        definitions = cls._check_product_instance_system().list_definitions(cls.get_product_name_implement())
        return [definition.product_version for definition in definitions]


class InstanceManager(
    InstanceManagerBase[TRecoveryStateInfo],
    IInstanceManager[TProductClient],
    Generic[TProductClient, TRecoveryStateInfo],
):
    """Base class for all internal implementation of product instance managers.
    Derived classes provide facilities for creating and accessing product instances.
    The typevar ``TProductClient`` is the client class for the product managed by an ``InstanceManager`` derived class.
    This class must only be used for internal instance manager implementation but must not be exposed publicly to the
    solution.

    Parameters
    ----------
    instance_identification : ``AbstractInstanceIdentificationClient``
        Provides access to persisted data on a specific product instance.
    method_directory : ``AbstractStoragePath``, optional
        The method file space for the method that is being executed. If it is not set, then the manager will assume it
        is being used outside the context of a method.
    project_directory_path_on_solution : ``AbstractStoragePath``, optional
        The project files directory, which contains the product state directory. If it is not set, then the manager will
        assume it is being used in a desktop deployment.
    max_execution_time : int, optional
        Amount of time (in seconds) after which an instance managed by Ansys HPS will be shutdown.
        If not set, the value is set to 7200 seconds (2 hours).

    Notes
    -----
    It is not expected that GLOW transaction methods or GLOW clients will directly use the constructors of
    ``InstanceManager`` or classes derived from it. Instead, a class derived from ``ProductInstanceManager`` should
    be passed as an argument to each :py:func:`~ansys.saf.glow.solution.create_instance` decorator to
    indicate the type of product instance to create and the Client API to be used to access the created instance.

    By convention derived classes implement an ``initialize`` method that has arguments specific to a given product
    that allow the transaction method to determine the initial state of the product instance.

    |saf-docs-instance-management-ref|_ explains the concept of product
    instances in more detail.
    """

    def __init__(
        self,
        **kwargs: Any,
    ) -> None:
        _instance_identification = kwargs["_instance_identification"]
        _max_execution_time = kwargs.get("_max_execution_time")
        super().__init__(_instance_identification, _max_execution_time)

    def get_untyped_client_object_for_base(self, hostname: str, port: int) -> Any:
        return self.get_client_object_implement(hostname, port)

    @property
    def instance(self) -> TProductClient:
        """The product specific client object that provides the managed product's API.

        Returns
        -------
        ``TProductClient``
            The product specific client object that provides the managed product's API.
        """
        return cast("TProductClient", self._get_or_create_client())

    @abstractmethod
    def get_client_object_implement(self, hostname: str, port: int) -> TProductClient:
        """Return the product specific client object that provides the managed product's API.

        The client object is what will be exposed by the manager's ``instance`` property in
        a @transaction method. Subclasses must implement the logic to create a client exposing
        the product instance API.

        Parameters
        ----------
        hostname: str
            The hostname on which the product is running.
        port: int
            The port on which the product is running.
        """
        raise NotImplementedError()

    def close_client_object_implement(self) -> None:
        """Close the product specific client object.

        (Use ``self.instance`` to access the client from within this method)
        Subclasses may implement the logic needed to dispose the client object.
        This is particularly important for clients that can be created with the ``with`` statement,
        since it usually means that there is some disposal to do at the end. In this case, create the client
        without using the ``with`` in ``get_client_object_implement`` and call the dispose/close method here.

        Does not raise NotImplementedError() to avoid breaking changes with existing custom managers
        that would fail to be constructed otherwise.
        """

    def close_client(self) -> None:
        """Close the product client."""
        if self._client is not None:
            self.close_client_object_implement()


class ProductInstanceManager(ABC, IInstanceManager[TProductClient], Generic[TProductClient, TRecoveryStateInfo]):
    """A wrapper over an InstanceManager internal implementation for use as a public API.
    This is the API that is publicly exposed and consumed by solution developers for product instance management.
    A limited set of members of InstanceManager are exposed by ProductInstanceManager that are enough for
    ProductInstanceManager to implement the IInstanceManager interface.

    In order to create a custom product instance manager that can be used by solutions,
    create a class derived from ProductInstanceManager that specifies which InstanceManager implementation to use.
    This is done by providing the ``instance_manager_impl`` parameter in class kwargs.
    The ``instance_manager_impl`` parameter should be derived from ``InstanceManager[TProductClient]``.
    The derived class must define two methods: ``__init__`` and ``initialize``.
    Those methods are simply passing the parameters to the underlying internal InstanceManager implementation.
    The sole purpose of those methods is to define proper docstrings for solution developers.

    Since a ProductInstanceManager object can be created indirectly via the @instance decorator,
    or directly within a transaction method, it is not possible to overload __init__ with a different signature.

    To create an instance of ProductInstanceManager within a transaction,
    the exact same arguments that are passed to the ``initialize`` method are expected to be passed to the
    ProductInstanceManager constructor.
    For example, if ``def initialize(version: int)`` is implemented in a class derived from InstanceManager,
    then the corresponding ProductInstanceManager should have a constructor that has a ``version`` argument.
    For this reason, proper docstrings on ``__init__(**kwargs)`` to explain what arguments are expected
    is therefore highly recommended.

    Notes
    -----
    If ProductInstanceManager class requires additional members to be implemented
    to enable a derived class to be instantiated then please give an overview of those members here.


    Examples
    --------
    >>> class MyProductInstanceManager(
    >>>     ProductInstanceManager[MyProductClient],
    >>>     instance_manager_impl_type=InternalInstanceManagerImpl
    >>> ):
    >>>     def __init__(self, **kwargs: Any):
    >>>         '''Documentation describing what arguments are expected from this product instance.
    >>>         The arguments must be the same as the signature of the initialize method, i.e. version
    >>>         in this example
    >>>
    >>>         Parameters
    >>>         ----------
    >>>         version : int
    >>>             The version of the product to be used.
    >>>
    >>>         '''
    >>>         super().__init__(**kwargs)
    >>>
    >>>     def initialize(self, version: Optional[str] = None):
    >>>         '''Docstring for initialize. This must be the exact copy of the initialize method
    >>>         from the InstanceManager internal implementation.
    >>>         '''
    >>>         super().start(version=version)
    """

    _instance_manager_impl_type: type[InstanceManager[TProductClient, TRecoveryStateInfo]]
    _recovery_state_info_type: type[TRecoveryStateInfo]

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self._instance_manager_impl: InstanceManager[TProductClient, TRecoveryStateInfo]
        # An instance manager can be instantiated either within a transaction, where arguments passed to the constructor
        # are explicit, or via the @instance injection in which mode specific internal arguments are passed via kwargs.
        # In the first scenario, we load the directories from the method thread local var set in transaction() function.
        # In the second, we load it from the internal arguments.
        instance_identification = kwargs.get("_instance_identification")
        # NOTE: max_execution_time not set for unshared products. They should be used with a contextmanager and shutdown
        # when exiting the context. What if the time within the context exceeds the default max execution time?
        max_execution_time = kwargs.get("_max_execution_time")

        if not instance_identification:  # -> unshared product instance
            instance_identification = UnsharedProductIdentificationClient[self._recovery_state_info_type]()

        manager_impl_kwargs = {
            "_instance_identification": instance_identification,
            "_max_execution_time": max_execution_time,
        }
        self._instance_manager_impl = self._instance_manager_impl_type(**manager_impl_kwargs)

    def __init_subclass__(
        cls,
        instance_manager_impl_type: type[InstanceManager[TProductClient, TRecoveryStateInfo]],
        **kwargs: Any,
    ) -> None:
        """Customize the creation of derived classes by making sure they do not violate some constraints."""
        cls._instance_manager_impl_type = instance_manager_impl_type
        cls._recovery_state_info_type = get_args(cls.__orig_bases__[0])[1]  # type: ignore
        cls._instance_manager_impl_type.recovery_state_info_type = cls._recovery_state_info_type  # type: ignore
        instance_manager_impl_initialize_method = getattr(instance_manager_impl_type, "initialize", None)
        if instance_manager_impl_initialize_method is None:
            raise SolutionLoadException(f"{cls.__name__} must implement a 'initialize' method.")
        product_instance_manager_initialize_method = getattr(cls, "initialize", None)
        if product_instance_manager_initialize_method is None:
            raise SolutionLoadException(f"{cls.__name__} must implement a 'initialize' method.")
        if (
            instance_manager_impl_initialize_method.__annotations__
            != product_instance_manager_initialize_method.__annotations__
        ):
            raise SolutionLoadException(
                f"The signature of the 'initialize' method from {cls.__name__}"
                f" does not match the 'initialize' method from {instance_manager_impl_type.__name__}.",
            )
        try:
            cls._recovery_state_info_type()
        except ValidationError as exc:
            raise SolutionLoadException(
                f"{cls._recovery_state_info_type.__name__} must be instantiable without arguments: {str(exc)}",
            ) from None
        super().__init_subclass__(**kwargs)

    def __enter__(self):
        # unshared product instance
        self.start(**self.kwargs)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.shutdown()

    @property
    def instance(self) -> TProductClient:
        """The underlying product client."""
        return self._instance_manager_impl.instance

    def start(self, *args: Any, **kwargs: Any) -> None:
        """Start the instance. This must be called from the derived class within the initialize() method."""
        self._instance_manager_impl.initialize(*args, **kwargs)  # type: ignore

    @classmethod
    def get_versions(cls) -> list[str]:
        """Return a list of versions of the product that are available in this deployment
        that can be accessed as product instances.

        Returns
        -------
        ``list of str``
            Return a list of versions of the product that are available in this deployment
            that can be accessed as shared product instances. Any value in the list can be passed
            to the ``initialize`` method (on a derived class) to indicate the version of the instance to be created.
        """
        return cls._instance_manager_impl_type.get_versions()  # type: ignore

    @property
    def product_version(self) -> str:
        """Get the version of the current running product instance."""
        return self._instance_manager_impl.product_version

    def shutdown(self) -> None:
        """Shut the product instance down."""
        self._instance_manager_impl.shutdown()

    def is_instance_healthy(self) -> bool:
        """Return if the instance is healthy."""
        return self._instance_manager_impl.is_instance_healthy()

    @property
    def storage_scope(self) -> ProductStorageScope:
        return self._instance_manager_impl.product_storage_scope

    @property
    def state_directory(self) -> PurePath:
        """The product instance state directory path of the remote product.
        This directory is usually used by the product instance to save state and output files.

        Notes
        -----
        The return path is only valid in the context of the product and therefore cannot be used directly
        from the solution side.
        Instead, this path needs to be accessed from the product api or from the product storage scope
        within a @transaction method.
        For example, if the product has a method to save data to a specific directory, you can do the following:
        >>> self.product_mgr.instance.save_data(self.product_mgr.state_directory / "data_file.dat")
        Similarly, you can use the product storage scope to persist files within that directory as entity handles:
        >>> data_handle = self.product_mgr.storage_scope.store_from_state_directory(self.state_directory / "data.dat")
        """
        return self._instance_manager_impl.state_directory
