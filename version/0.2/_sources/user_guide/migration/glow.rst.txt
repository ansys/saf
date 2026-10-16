.. _migration_glow:

Upgrade to SAF GLOW Engine 2.0
##################################

This guide describes the breaking changes in SAF GLOW Engine 2.0 and how to migrate an existing solution.

Migration checklist
===================

Perform the following actions in this order:

#. Migrate your solution to :ref:`Blob Data Management (BDM) <blob_management>` while still on SAF GLOW Engine 1.x, so you don't have to absorb every breaking change at once.
#. If you need to keep existing projects, define a :ref:`project migration <project_migration>` for the new solution schema version.
#. Use project injection in your Dash callbacks instead of ``DashClient.get_project()`` (see :ref:`project-injection`).
#. Upgrade Dash to 3.x.
#. Replace the removed classes, methods, and environment variables listed in the sections below.
#. Upgrade ``ansys-saf-glow-engine`` to ``>=2.0`` in ``pyproject.toml``, along with every SAF SDK dependency to a version compatible with SAF GLOW Engine 2.0.
#. Add the ``ansys-saf-product-manager`` dependency with the extras for the products you use, and update your product manager imports (see :ref:`built-in-product-managers-2-0`).

FileReference removal
=====================

``FileReference`` and its related classes have been removed in SAF GLOW Engine 2.0. This includes
``FileReference``, ``FileGroupReference``, ``AssetFileReference``, ``AssetFileGroupReference`` and
``HpsFileReference``.

Your solution must use :ref:`BDM <blob_management>` from now on. It's recommended to do this before upgrading to SAF GLOW Engine 2.0 to be able to migrate your solution data schema smoothly and gradually.

Because this migration changes your solution data schema, existing projects are not compatible with the migrated solution. If you need to keep using them, define a :ref:`project migration <project_migration>` for the new schema version.

Dash
====

- Removed ``DashClient.get_project()``. In Dash callbacks, use project injection, as described in
  :ref:`project-injection`.

.. code-block:: python
    :caption: Before

    @callback(
        ...,  # Your inputs and output here
        State("url", "pathname"),
    )
    def my_method(pathname: str):
        project = DashClient[MySolution].get_project(pathname)
        project.steps.my_step_name.my_transaction()


.. code-block:: python
    :caption: After

    @callback(
        ...,  # Your inputs and output here
        State("url", "pathname"),
    )
    def my_method(project: MySolution):
        project.steps.my_step_name.my_transaction()

- Removed support for Dash 2.x. SAF GLOW Engine 2.0 requires Dash ``^3.0.0``.

.. _built-in-product-managers-2-0:

Built-in product managers
=========================

All built-in product managers have moved to the ``ansys-saf-product-manager`` package (``ansys.saf.product_manager`` module). Deprecated and duplicated managers have been removed at the same time: ``FileReference``-based managers, the standalone (non-wrapped) OptiSLang manager, and every insecure manager whose secure counterpart already existed.

Solutions must now declare the ``ansys-saf-product-manager`` dependency with the appropriate extras, and import product managers from ``ansys.saf.product_manager``.

Update ``pyproject.toml`` to move product extras from ``ansys-saf-glow-engine`` to ``ansys-saf-product-manager``:

.. code-block:: toml
    :caption: Before

    ansys-saf-glow-engine = {version = "^1.40", extras = ["geometry"]}

.. code-block:: toml
    :caption: After

    ansys-saf-glow-engine = {version = "^2.0"}
    ansys-saf-product-manager = {version = "^0.4", extras = ["geometry"]}

Update your imports:

.. code-block:: python
    :caption: Before

    from ansys.saf.glow.solution.beta.geometry import GeometryManager, GeometrySecureManager

.. code-block:: python
    :caption: After

    from ansys.saf.product_manager.geometry import GeometryManager

Details of the changes:

- Removed ``FileReference``-based product managers, which were located at ``ansys.saf.glow.solution``.
- Removed product manager imports from ``ansys.saf.glow.solution`` and its ``.beta`` submodule. All product managers must now be imported from ``ansys.saf.product_manager``.
- Removed insecure product managers when a secure product manager was already available. The secure product manager is now the default. For example, ``ansys.saf.glow.solution.beta.geometry.GeometrySecureManager`` has been replaced by ``ansys.saf.product_manager.geometry.GeometryManager``.
- Removed the standalone (non-wrapped) OptiSLang manager. Use ``ansys.saf.product_manager.optislang_wrapper.OslManager`` instead.
- Removed product-related extras from ``ansys-saf-glow-engine``: ``aedt``, ``fluent``, ``mechanical``, ``mapdl``, ``optislang``, ``theia`` and ``geometry``. These extras are now provided by ``ansys-saf-product-manager``.

Custom product managers and configurations
==========================================

- Classes imported from ``ansys.saf.glow.solution`` for building custom product managers now refer to the BDM classes previously exposed under ``ansys.saf.glow.solution.beta``. The old ``FileReference``-based classes have been removed. See :ref:`instance_management_custom` for details.
- Removed ``PimProductConfiguration`` and ``PimProductConfigurationBuilder`` from ``ansys.saf.glow.solution.products``. Use ``IProductInstanceConfiguration`` and ``IProductInstanceVersionConfiguration`` instead. See :ref:`custom-product-configurations` for details.

Client API
==========

- Removed ``modify_project_display_name()`` from the Client API. Use ``modify_info()`` instead, which also allows modifying the project description.

Environment variables
=====================

- Removed :envvar:`GLOW_METHOD_EXECUTION_DIRECTORY` and :envvar:`GLOW_KEEP_TRANSACTION_FILES`. They were only relevant to ``FileReference``. BDM stores files in the project files directory (configurable through :envvar:`GLOW_PROJECT_FILES_DIRECTORY`) and files are cleaned up automatically by the garbage collector. The garbage collector can be disabled with :envvar:`GLOW_BDM_GC_DISABLED`.
- Removed :envvar:`GLOW_INSTANCE_SYSTEM`, :envvar:`GLOW_PIM_HOST` and :envvar:`GLOW_PIM_PORT`. Use :envvar:`GLOW_PRODUCT_INSTANCE_SYSTEM`, :envvar:`GLOW_PRODUCT_INSTANCE_SYSTEM_HOST` and :envvar:`GLOW_PRODUCT_INSTANCE_SYSTEM_PORT` instead.

Security
========

Insecure gRPC connections to PIM Light Server are no longer supported. SAF GLOW Engine 2.0 only supports ``WNUA`` on local Windows, ``UDS`` on local Linux, and ``mTLS`` for any remote connection.

See :ref:`gRPC transport modes <instance_management_grpc_transport_modes>` for details on each mode. Transport selection is handled automatically by your orchestrator (for example, ``ansys-saf-desktop-orchestrator``).
