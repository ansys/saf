.. _instance_management_custom:

Create custom product managers and configurations
#################################################

If you want to use another software component in your solution as a product instance besides the one officially built-in in SAF GLOW Engine, you need to create your own custom product instance manager.
In order to create one, the product needs to comply with the following requirements:

- the product has a gRPC, HTTP or TCP based protocol;
- the product has a Python client for the gRPC, HTTP or TCP based protocol;
- the Python client supports product instance shutdown, deserialization of state, and serialization of state; and
- the product supports standard health check methods.

To be able to use a product instance across multiple transaction method invocations (that is a "shared product instance"), other requirements apply:
- the product can be started with its state loaded by deserialization;
- the product state can be serialized and deserialized (for example, save and load project files);

.. note::
    When removing a project, all of its associated instances are shutdown.

Creating a custom product manager consists of two tasks described in the following sections:

- Implementing a custom product instance manager
- Defining a configuration for the product instance manager

Example: Custom product
=======================

For the sake of example, let us consider a simple custom product exposing an HTTP API that allows to get and store a value.
The custom product exposes the following endpoints:

.. list-table::
    :header-rows: 1
    :widths: 30 65

    * - Endpoint
      - Action
    * - ``GET http://host:port/health``
      - Indicate whether the service is healthy or not. (IMPORTANT: this endpoint must be implemented by the product)
    * - ``GET http://host:port/``
      - Get the value stored by the custom product instance.
    * - ``PUT http://host:port/``
      - Update the value stored by the custom product instance.
    * - ``POST http://host:port/:save``
      - Persist the value into the file specified in the body of the request.
    * - ``POST http://host:port/:open``
      - Restore the persisted value from the file specified in the body of the request.


A simple FastAPI implementation of this product would look as follow:

.. code-block:: python
    :caption: ``src/ansys/solutions/my_solution/solution/custom_product_server.py``

    from pathlib import Path
    from fastapi import FastAPI, Body


    app = FastAPI()
    app.state.value = "default_value"


    @app.get("/health")
    def health():
        """For health check."""
        return "I am healthy!"


    @app.get("/")
    def get_value() -> str:
        """Retrieve the value from the current session."""
        return app.state.value


    @app.put("/")
    def set_value(new_value: str = Body(..., embed=True)) -> str:
        """Set the value to the current session."""
        app.state.value = new_value
        return app.state.value


    @app.post("/:save")
    def save(path: str = Body(..., embed=True)):
        """Save the current value to a file."""
        Path(path).write_text(app.state.value)


    @app.post("/:open")
    def open(path: str = Body(..., embed=True)):
        """Retrieve the value from a file."""
        app.state.value = Path(path).read_text()


To be able to manage instances of the custom product server, we need a Python client for the custom product:

.. code-block:: python
    :caption: ``src/ansys/solutions/my_solution/solution/custom_product_client.py``

    import httpx


    class CustomProductClient:
        def __init__(self, host: str, port: int):
            """The client for custom product."""
            self._client = httpx.Client(base_url=f"http://{host}:{port}")

        def get_value(self) -> str:
            """Retrieve the value."""
            response = self._client.get("/").raise_for_status()
            return response.json()

        def set_value(self, new_value: str) -> str:
            """Set the value."""
            response = self._client.put("/", json={"value": new_value}).raise_for_status()
            return response.json()

        def save(self, filepath: str) -> None:
            """Store the internal value of the product state in a given file."""
            response = self._client.post("/:save", json={"path": filepath})
            response.raise_for_status()

        def open(self, filepath: str) -> None:
            """Restore the value from a given file into the product state."""
            response = self._client.post("/:open", json={"path": filepath})
            response.raise_for_status()

        def close(self) -> None:
            """Close the initialized httpx.Client."""
            self._client.close()


Implement a new custom product instance manager
===============================================

The implementation of a custom product instance manager is done in three stages.

- The first step is to define a recovery state info model.
- The second step is to implement an internal custom product instance manager.
- The third step is to expose a public class that can be used within the solution.

The purpose of this architecture is to keep the implementation details away from its usage within a solution.
This prevents solutions from using prohibited methods and properties that must only be used internally by the custom product instance manager.

Recovery state info definition
------------------------------

The recovery state info is a Pydantic model that can be used to save and restore product instance state information.
In our custom product example, the product can save its state into a project file that can be used to restore the product instance.
Therefore, we want to keep the product file around as part of the solution, so that if we resume the solution project later while the product instance is down, it can be restored properly.

To specify what data needs to be used by the product for recovery, you need to create a new class derived from :py:class:`RecoveryStateInfo`.
The class is a Pydantic model, so you just need to specify fields with any standard Python or Pydantic types.
To define fields interacting with files or directories, you must used the ``EntityHandle`` |BDM-API|_ type.
Do not use ``Path`` or ``str`` to specify a filepath!
Back to our example, we want to be able to persist the version used to launch the product, as well as the project file that the product uses to save its state.
To persist the version, we are defining a ``version: str`` field in the :py:class:`CustomRecoveryStateInfo` class.
In order to be able to retrieve the project file later to restore the product instance state, we need to keep track of the project file name by defining the ``project_filename: str`` field in the :py:class:`CustomRecoveryStateInfo` class.

.. important::
    **All fields in your custom RecoveryStateInfo class must have default values.**
    The class must be instantiable without any arguments.
    This is required for mocking the custom product instance manager in tests using the ``saf-sdk-testing`` package.

.. note::
    To persist the project file, we need to make sure that the file is placed in a directory that is dedicated to storing product state files.
    For that purpose, you can use ``self.copy_to_state_directory()`` or ``self.state_directory``.


.. code-block:: python

    from ansys.saf.glow.solution import RecoveryStateInfo


    class CustomRecoveryStateInfo(RecoveryStateInfo):
        version: str | None = None
        project_filename: str = "project.prod"
        example_int_value: int = 0


Internal instance manager class implementation
----------------------------------------------

The first thing needed to implement an internal custom product instance manager is to create a new class derived from :py:class:`InstanceManager[TProductClient, TRecoveryState]`, where ``TProductClient`` is the type of the Python custom product client (in our example: ``CustomProductClient``) and ``TRecoveryState`` is the type of the recovery state info (in our example: ``CustomRecoveryStateInfo``) .
This base class is abstract and has the following methods that need to be implemented by the derived internal product instance manager class:

.. list-table::
    :header-rows: 1

    * - Method
      - Action

    * - ``initialize``
      - Initializes the product instance manager and creates the product instance.

        This method is called the first time the product instance is created, that is, when a transaction method with a ``create_instance`` decorator is called.
        It must call the ``self.initialize_service`` method and set the ``self.recovery_state_info`` property.

    * - ``get_client_object_implement``
      - Returns an instance of the product's client given the host and port of the product instance.

        In our example, this is the method that should return an instance of ``CustomProductClient``.

    * - ``close_client_object_implement``
      - Closes the instance of the product's client created in ``get_client_object_implement``.

        This is particularly important for clients that can be created with the ``with`` statement,
        since it usually means that there is some disposal to do at the end. In this case, create the client
        without using the ``with`` in ``get_client_object_implement`` and call the dispose/close method here.

        In our example, this is the method that should correctly close the instance created of ``CustomProductClient``.

    * - ``save_state_implement``
      - Saves the state of the product instance to a given directory, so that there is way to restore a product instance to its last state.
        This is needed when sharing the same product instance across multiple transaction methods.

        (The method should use the ``self.instance`` property of the product instance manager which returns the client to achieve this)

        Note that this method is actually called in the end of every transaction method that is using the ``@instance`` decorator.

    * - ``load_state_implement``
      - Loads the state of the product instance from a given directory.
        This is needed when sharing the same product instance across multiple transaction methods.

        (The method should use the ``self.instance`` property of the instance manager which returns the client to achieve this.)

    * - ``shutdown_implement``
      -  Gracefully terminates the product instance process.

         (The method should use the ``self.instance`` property of the instance manager which returns the client to achieve this.)

    * - ``get_product_name_implement``
      - Returns the name of the product in the product instance system (PIM or HPS) environment. Normally, this method would return
        a hard-coded string.

        (This facilitates the creation of the product instance process.)

.. vale off
.. important::

    The custom product instance manager cannot add additional arguments to any of these methods beyond those declared on the base class
    :class:`ansys.saf.glow.solution.InstanceManager` and its base :class:`ansys.saf.glow.solution.InstanceManagerBase`.
.. vale on

The implementation of such a class would look like this:

.. code-block:: python
    :caption: ``src/ansys/solutions/my_solution/solution/custom_product_manager.py``

    from ansys.saf.glow.solution import InstanceManager, RecoveryStateInfo
    from ansys.solutions.my_solution.solution.custom_product_client import CustomProductClient


    class CustomRecoveryStateInfo(RecoveryStateInfo):
        version: str | None = None
        project_filename: str = "project.prod"
        example_int_value: int = 0


    class InternalCustomProductInstanceManagerImpl(InstanceManager[CustomProductClient, CustomRecoveryStateInfo]):

        PRODUCT_NAME = "custom-product"
        SERVICE_NAME = "http"

        def initialize(self, version: str | None = None):
            """Initialize and start the custom product server."""
            self.initialize_service(self.SERVICE_NAME, version)
            self.recovery_state_info = CustomRecoveryStateInfo(version=version, project_filename="project.prod")

        @classmethod
        def get_product_name_implement(cls) -> str:
            """Return the name of the product in the product instance system (PIM or HPS) environment."""
            return cls.PRODUCT_NAME

        def get_client_object_implement(self, hostname: str, port: int) -> CustomProductClient:
            """Return an instance of the custom product's client given the host and port of the product instance."""
            return CustomProductClient(hostname, port)

        def close_client_object_implement(self) -> None:
            """Close the product specific client object."""
            self.instance.close()

        def save_state_implement(self) -> None:
            """Save the state of the product instance."""
            project_filepath = self.state_directory / self.recovery_state_info.project_filename
            self.instance.save(project_filepath.as_posix())

        def load_state_implement(self) -> None:
            """Loads the state of the product instance."""
            project_file_path = self.state_directory / self.recovery_state_info.project_filename
            self.instance.open(project_file_path.as_posix())

        def shutdown_implement(self) -> None:
            """Gracefully terminates the product instance process."""
            ...



.. warning::

  It is mandatory for the ``initialize`` method to do the following:

  - call the internal ``initialize_service`` method and,
  - set the ``recovery_state_info`` property. (If your custom product instance manager does not need a recovery state info, you still must create an empty class derived from ``RecoveryStateInfo`` and set an instance of it to the ``recovery_state_info`` property.)

Following the example above, it's recommended to define the ``SERVICE_NAME`` class attribute and to keep the ``version`` argument in the ``initialize`` method.
This is a best practice that helps to make the custom product manager easily testable using the ``saf-sdk-testing`` package. See its documentation for more details.


Public product instance manager exposed in solutions
----------------------------------------------------

As the name of ``InternalCustomProductInstanceManagerImpl`` indicates, this class is internal and only contains the implementation of the custom product instance manager.
In other words, ``InternalCustomProductInstanceManagerImpl`` must not be publicly exposed nor used within a solution.
To create such public API to be used within solutions, another small class derived from ``ProductInstanceManager`` must be implemented.

The derived class must specify which internal ``InstanceManager`` implementation to use by providing the ``instance_manager_impl`` parameter in class keyword arguments (the ``instance_manager_impl`` parameter should be a class derived from ``InstanceManager[T]``).
This class must then define two methods: ``__init__`` and ``initialize``.

Those methods are simply passing the parameters to the underlying internal ``InstanceManager`` implementation, so you must use the following constraints on their signatures:

- The parameters of ``def __init___(self, **kwargs:Any)`` must not be changed.
- The parameters of ``def initialize(self, ...)`` must be the exact same copy as the ``def initialize(self, ...)`` method from the internal ``InstanceManager`` implementation.
- ``__init__`` and ``initialize`` must share the same docstring.

.. code-block:: python
    :caption: ``custom_product_manager.py``

    from typing import Any
    from ansys.saf.glow.solution import ProductInstanceManager
    from ansys.solutions.my_solution.solution.custom_product_client import CustomProductClient

    ...


    class CustomProductInstanceManager(
        ProductInstanceManager[CustomProductClient, CustomRecoveryStateInfo],
        instance_manager_impl_type=InternalCustomProductInstanceManagerImpl,
    ):
        def __init__(self, **kwargs: Any):
            """Initialize and start a custom product instance.

            Parameters
            ----------
            version : str, optional
                The version of the custom product instance that must be used.
            """
            # Mandatory call to the base class!
            super().__init__(**kwargs)

        def initialize(self, version: str | None = None):
            """Initialize and start a custom product instance.

            Parameters
            ----------
            version : str, optional
                The version of the custom product instance that must be used.
            """
            # Mandatory call to the base implementation of ``start``, passing the values of the arguments of this method.
            super().start(version=version)


This ``CustomProductInstanceManager`` class is the one that is publicly exposed and consumed by solution developers for product instance management.
It can now be used in any step in the following way:


.. code-block:: python
    :caption: ``custom_shared_instance_step.py``

    from ansys.solutions.my_solution.solution.custom_product_manager import CustomProductInstanceManager


    class CustomSharedInstanceStep(StepModel):
        value: str = ""

        @transaction(self=StepSpec())
        @create_instance("custom_product_instance", CustomProductInstanceManager)
        @long_running
        def initialize_custom_product_instance(self, custom_product_instance: CustomProductInstanceManager) -> None:
            custom_product_instance.initialize(version="1")

        @transaction(self=StepSpec(upload=["value"]))
        @instance("custom_product_instance")
        def retrieve_value_from_custom_product(self, custom_product_instance: CustomProductInstanceManager) -> None:
            self.value = custom_product_instance.instance.get_value()

        @transaction(self=StepSpec(download=["value"]))
        @instance("custom_product_instance")
        def save_value_on_custom_product(self, custom_product_instance: CustomProductInstanceManager) -> None:
            custom_product_instance.instance.set_value(self.value)

        @transaction(self=StepSpec())
        @instance("custom_product_instance")
        def shutdown_custom_product(self, custom_product_instance: CustomProductInstanceManager) -> None:
            custom_product_instance.shutdown()

.. _custom-product-configurations:

Define custom product instance configurations
=============================================

To enable SAF GLOW Engine to create new custom product instance processes, you need to create a product instance configuration specifying how such custom product must be started.
A product instance configuration is a Python class that inherits from SAF GLOW Engine's :py:class:`IProductInstanceConfiguration`.

It has the following methods that need to be implemented by the derived product instance configuration class:

.. list-table::
    :header-rows: 1

    * - Method
      - Action

    * - ``product_name``
      - This is the product name that is exposed by the product instance management system (PIM or HPS).

        Use only lowercase letters and hyphens, for safety. Uppercase letters in product names can cause failures in Product Instance Management Systems.

    * - ``versions``
      - The set of versions that are supported.

        The last version is the default if no version is specified when an instance is created.

    * - ``get_version_configuration``
      - Returns configuration of a product for a specific version.


The ``get_version_configuration`` method should return a product instance version configuration object.
A product instance version configuration is a class implementing the SAF GLOW Engine's :py:class:`IProductInstanceVersionConfiguration` interface.
It must implement the following:

.. list-table::
    :header-rows: 1

    * - Method
      - Action

    * - ``service_name``
      - This is the name of the service that is exposed by the product instance management system (HPS or PIM) that identifies it from other services.
        It should be consistent with the name used in the PIM light and HPS configurations. Typically its something simple like ``grpc`` or ``http``.

    * - ``execution_command``
      - This is the command line used to start the product instance process.

        It can contain template variables in the form `${VAR}`. Supported variables are:

        - PORT: an integer which is the port that the process should expose its service on
        - EXECUTABLE: the full path to the executable using either the first product listed in the `software_requirements` for HPS or the path specified by ``exe_path_for_pim`` for PIM

    * - ``environment``
      - The environment variables that will be set in the environment running the ``execution_command``

    * - ``software_requirements``
      - (For HPS only!) The software that must be installed on the node running the ``execution_command``"""

    * - ``exe_path_for_pim``
      - (For PIM only!) The path to the product's executable.

    * - ``health_route``
      - The health route for the service. With our custom product example above, it should be ``/health``.

    * - ``service_type``
      - The type of service: ``grpc`` or ``http``


The configuration implementation for our custom product example would look like this:

.. code-block:: python
    :caption: ``src/ansys/solutions/my_solution/product_instance_configs/custom_product.py``

    import sys
    from ansys.saf.glow.solution.products.config import (
        IProductInstanceConfiguration,
        IProductInstanceVersionConfiguration,
        ISoftware,
        ServiceType,
        Software,
    )


    class CustomProductInstanceVersionConfiguration(IProductInstanceVersionConfiguration):
        def __init__(self, version: str) -> None:
            self._version = version

        @property
        def service_name(self) -> str:
            return "http"

        @property
        def execution_command(self) -> str:
            return "${EXECUTABLE} -m uvicorn ansys.solutions.my_solution.solution.custom_product_server:app  --port ${PORT}"

        @property
        def exe_path_for_pim(self) -> str:
            return sys.executable

        @property
        def environment(self) -> dict[str, str]:
            return {}

        @property
        def software_requirements(self) -> list[ISoftware]:
            # uvicorn and custom_product_server need to be installed on the evaluator to make this work!
            return [Software(name="Python", version="3.11")]

        @property
        def service_type(self) -> ServiceType:
            return ServiceType.HTTP


    class CustomProductInstanceConfiguration(IProductInstanceConfiguration):
        @property
        def product_name(self) -> str:
            return "custom-product"

        @property
        def versions(self) -> list[str]:
            return ["1"]

        def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
            return CustomProductInstanceVersionConfiguration(version)


Once you have created the ``CustomProductInstanceConfiguration`` and ``CustomProductInstanceVersionConfiguration`` implementation, put them inside a directory called ``product_instance_configs`` in the solution directory alongside the ``solution`` and ``ui`` directories. For example:

.. code-block:: console

    > ls .\src\ansys\solutions\my_solution\
    Mode                 LastWriteTime         Length Name
    ----                 -------------         ------ ----

    d----           31-Jul-23    13:45                product_instance_configs
    d----           31-Jul-23    12:05                solution
    d----           31-Jul-23    12:06                ui
    -a---           20-Jun-23    16:43              0 __init__.py
    -a---           21-Jun-23    12:11            349 main.py


.. code-block:: console

    > ls .\src\ansys\solutions\my_solution\product_instance_configs\
    Mode                 LastWriteTime         Length Name
    ----                 -------------         ------ ----
    -a---           01-Aug-23     8:49            709 another_custom_config.py
    -a---           01-Aug-23     8:49            437 custom_product_instance_config.py


Enable secure flags in custom product configurations
====================================================

If the product uses gRPC and supports secure startup options, you can enable transport-mode selection
from product configuration by setting secure flag parameters in your ``IProductInstanceVersionConfiguration`` implementation.

For scenario behavior (``WNUA``, ``UDS``, ``mTLS``, fallback), see :ref:`gRPC transport modes <instance_management_grpc_transport_modes>`.

Secure flag parameters
----------------------

In your version configuration class, you can define the following properties:

- ``enable_secure_flags``: Enables secure-flag handling for this product version.
- ``windows_local_secure_flags``: Flags used for localhost bindings on Windows.
- ``linux_local_secure_flags``: Flags used for localhost bindings on Linux.
- ``remote_secure_flags``: Flags used for non-localhost bindings (typically ``mTLS``).
- ``insecure_flags``: Fallback flags for insecure mode.

These flags are appended to your ``execution_command`` at runtime.

.. important::

    When using ``PIM Light Server``, only ``windows_local_secure_flags`` and ``insecure_flags`` are used. ``HPS`` supports all secure flag parameters, though.


Example: secure gRPC configuration and manager
----------------------------------------------

The following example defines a secure-enabled custom gRPC product configuration. It assumes you have:

- a ``secure_grpc_server`` module that can be started with the specified command and supports the indicated secure flags.
- the corresponding ``SecureCustomGrpcClient`` implemented to handle the secure connection modes.

.. code-block:: python
    :caption: ``secure_custom_product_instance_config.py``

    import sys

    from ansys.saf.glow.solution.products.config import (
        IProductInstanceConfiguration,
        IProductInstanceVersionConfiguration,
        ISoftware,
        ServiceType,
        Software,
    )


    class SecureCustomGrpcVersionConfiguration(IProductInstanceVersionConfiguration):
        def __init__(self, version: str) -> None:
            self._version = version

        @property
        def service_name(self) -> str:
            return "grpc"

        @property
        def execution_command(self) -> str:
            # $HOST is replaced with the value from GLOW_PRODUCT_BINDING_HOST environment variable, or its default value.
            # See "gRPC transport modes" and "Configuration" sections for more details.
            return (
                "${EXECUTABLE} -m ansys.solutions.my_solution.custom_product.secure_grpc_server "
                f"${{PORT}} --host ${{HOST}} --version {self._version}"
            )

        @property
        def exe_path_for_pim(self) -> str:
            return sys.executable

        @property
        def environment(self) -> dict[str, str]:
            return {}

        @property
        def software_requirements(self) -> list[ISoftware]:
            return [Software(name="Python", version=f"{sys.version_info.major}.{sys.version_info.minor}")]

        @property
        def service_type(self) -> ServiceType:
            return ServiceType.GRPC

        @property
        def enable_secure_flags(self) -> bool:
            # The default value in IProductInstanceVersionConfiguration is False, so secure flags are opt-in.
            return True

        @property
        def windows_local_secure_flags(self) -> str:
            # This is the default value in IProductInstanceVersionConfiguration,
            # used automatically if enable_secure_flags=True. Added for clarity. Omit if not needed to change.
            return "--transport-mode=WNUA"

        @property
        def linux_local_secure_flags(self) -> str:
            # This is the default value in IProductInstanceVersionConfiguration,
            # used automatically if enable_secure_flags=True. Added for clarity. Omit if not needed to change.
            return "--transport-mode=UDS --uds-dir=${UDS_DIR} --uds-id=${UDS_ID}"

        @property
        def remote_secure_flags(self) -> str:
            # This is the default value in IProductInstanceVersionConfiguration,
            # used automatically if enable_secure_flags=True. Added for clarity. Omit if not needed to change.
            return "--transport-mode=MTLS --certs-dir=${CERTS_DIR}"

        @property
        def insecure_flags(self) -> str:
            # This is the default value in IProductInstanceVersionConfiguration,
            # used automatically if enable_secure_flags=True. Added for clarity. Omit if not needed to change.
            return "--transport-mode=insecure"


    class SecureCustomGrpcConfiguration(IProductInstanceConfiguration):
        @property
        def product_name(self) -> str:
            return "custom-grpc-product-secure"

        @property
        def versions(self) -> list[str]:
            return ["1"]

        def get_version_configuration(self, version: str) -> IProductInstanceVersionConfiguration:
            return SecureCustomGrpcVersionConfiguration(version)


In the manager implementation, retrieve secure metadata from the resolved service and pass it to your
client constructor. Your manager must reference the same product name exposed by the configuration above
(``custom-grpc-product-secure``):

.. code-block:: python
    :caption: ``secure_custom_product_manager.py``

    import os
    from pathlib import Path

    from ansys.saf.glow.solution import (
        InstanceManager,
        ProductInstanceManager,
        RecoveryStateInfo,
    )

    from ansys.solutions.my_solution.custom_product.client import SecureCustomGrpcClient


    class SecureCustomRecoveryStateInfo(RecoveryStateInfo):
        pass


    class InternalSecureCustomProductInstanceManagerImpl(
        InstanceManager[SecureCustomGrpcClient, SecureCustomRecoveryStateInfo]
    ):
        PRODUCT_NAME = "custom-grpc-product-secure"
        SERVICE_NAME = "grpc"

        @classmethod
        def get_product_name_implement(cls) -> str:
            return cls.PRODUCT_NAME

        def initialize(self, version: str | None = None):
            self.initialize_service(self.SERVICE_NAME, version)
            self.recovery_state_info = SecureCustomRecoveryStateInfo()

        def get_client_object_implement(self, hostname: str, port: int) -> SecureCustomGrpcClient:
            # retrieve secure flags used to launch the product instance
            service = self._get_service()
            secure_flags = (service.secure_flags or "").lower()

            # instantiate the client depending on the transport mode used
            if "mtls" in secure_flags:
                certs_dir = os.getenv("ANSYS_GRPC_CERTIFICATES")
                if certs_dir is None:
                    raise RuntimeError("MTLS requires ANSYS_GRPC_CERTIFICATES to be configured.")
                return SecureCustomGrpcClient(
                    host=hostname,
                    port=port,
                    transport_mode="mtls",
                    certs_dir=Path(certs_dir),
                )
            elif "uds" in secure_flags:
                if not service.uds_dir or not service.uds_id:
                    raise RuntimeError("UDS requires uds_dir and uds_id to be configured in the service.")
                return SecureCustomGrpcClient(
                    host=hostname,
                    port=port,
                    transport_mode="uds",
                    uds_dir=Path(service.uds_dir),
                    uds_id=service.uds_id,
                )
            elif "wnua" in secure_flags:
                return SecureCustomGrpcClient(
                    host=hostname,
                    port=port,
                    transport_mode="wnua",
                )
            else:
                return SecureCustomGrpcClient(
                    host=hostname,
                    port=port,
                    transport_mode="insecure",
                )

        # Rest of methods (close_client_object_implement, save_state_implement, load_state_implement, shutdown_implement)
        # would be implemented here, similar to the previous insecure example.


    class SecureCustomProductManager(
        ProductInstanceManager[SecureCustomGrpcClient, SecureCustomRecoveryStateInfo],
        instance_manager_impl_type=InternalSecureCustomProductInstanceManagerImpl,
    ):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

        def initialize(self, version: Optional[str] = None):
            super().start(version=version)


This pattern lets your manager adapt the client transport mode using information published by the product instance
system service (``secure_flags``, ``uds_dir``, ``uds_id``) and environment variables (:envvar:`ANSYS_GRPC_CERTIFICATES`).
