.. _components_overview:

SAF components
##############

The Solution Application Framework is composed of multiple Python packages, each with a specific
responsibility. This section provides an overview of each component, how they relate to each other,
and what role they play in the framework.

The packages are released as a coordinated set: for every SAF release, a combination of package
versions is validated to work together. The ``ansys-saf-sdk`` meta-package materializes that
combination as a single, versioned dependency, so that you do not have to track and align the
individual package versions yourself. See :ref:`components_meta_package`.


.. _components_dependency_graph:

Dependency graph
================

The following diagram shows the dependency relationships between SAF packages. An arrow from A to B
means A depends on B.

.. mermaid::

   %%{init: {"flowchart": {"nodeSpacing": 30, "rankSpacing": 50, "htmlLabels": true}} }%%
   graph TD
      CLI["&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;SAF CLI&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"]
      GLOW["&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;SAF GLOW Engine&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"]
      PROD_CFG["&nbsp;SAF Product Configuration&nbsp;"]
      PROD_MGR["&nbsp;&nbsp;&nbsp;SAF Product Manager&nbsp;&nbsp;&nbsp;"]
      BDM_API["&nbsp;&nbsp;&nbsp;&nbsp;BDM Python API&nbsp;&nbsp;&nbsp;&nbsp;"]
      BDM_SV["&nbsp;&nbsp;&nbsp;BDM Python Shared Volume&nbsp;&nbsp;&nbsp;"]
      OIDC["&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;IAM OIDC&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"]
      TESTING["&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;SAF Testing&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"]
      TEMPLATES["&nbsp;&nbsp;&nbsp;&nbsp;SAF Templates&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"]
      DSC["Dash Super Components"]
      ORCH["&nbsp;SAF Desktop Orchestrator&nbsp;&nbsp;"]
      INST["&nbsp;&nbsp;&nbsp;SAF Desktop Installer&nbsp;&nbsp;&nbsp;"]

      CLI -->|main| TEMPLATES
      CLI -->|tests| TESTING
      CLI -->|style| GLOW
      CLI -->|style| DSC

      GLOW -->|main| BDM_API
      GLOW -->|main| BDM_SV
      GLOW -->|main| OIDC
      GLOW -->|main| PROD_CFG
      GLOW -->|tests| TESTING

      PROD_MGR -->|main| PROD_CFG
      PROD_MGR -->|main| BDM_API
      PROD_MGR -->|main| BDM_SV
      PROD_MGR -->|main| GLOW
      PROD_MGR -->|tests| TESTING

      BDM_SV --> BDM_API

      ORCH -->|main| GLOW
      ORCH -->|main| PROD_CFG
      ORCH -->|tests| TESTING

      INST -->|style| GLOW

      TESTING -->|main| PROD_CFG

      style GLOW fill:#4a90d9,stroke:#2c5f8a,color:#fff
      style CLI fill:#6ab04c,stroke:#3d7a28,color:#fff
      style TEMPLATES fill:#6ab04c,stroke:#3d7a28,color:#fff
      style TESTING fill:#6ab04c,stroke:#3d7a28,color:#fff
      style BDM_API fill:#f0932b,stroke:#b36b1e,color:#fff
      style BDM_SV fill:#f0932b,stroke:#b36b1e,color:#fff
      style OIDC fill:#f0932b,stroke:#b36b1e,color:#fff
      style DSC fill:#6ab04c,stroke:#3d7a28,color:#fff
      style ORCH fill:#9b59b6,stroke:#6c3483,color:#fff
      style INST fill:#9b59b6,stroke:#6c3483,color:#fff
      style PROD_CFG fill:#e74c3c,stroke:#a93226,color:#fff
      style PROD_MGR fill:#e74c3c,stroke:#a93226,color:#fff

**Legend**:
🔵 Runtime ·
🟢 Developer Experience ·
🟠 Infrastructure ·
🟣 Desktop ·
🔴 Product Integration



.. _components_list:

Components
=============

The following sections describe each SAF package, the role it plays in the framework, and its key
features.


.. _components_glow_engine:

SAF GLOW Engine
----------------

SAF Guided Low-Code Workflow (GLOW) Engine is the central runtime of SAF. It provides the backend
framework for defining solution workflows, managing application state, and exposing a RESTful API
consumed by frontends.

- **Package name**: ``ansys-saf-glow-engine``
- **Key features**:

  - Declarative workflow definition using ``Solution``, ``StepModel``, and ``StepSpec`` classes
  - ``@transaction`` and ``@long_running`` decorators for backend operations
  - Automatic REST API generation from the solution definition
  - Built-in project persistence (create, save, restore, export/import)
  - Integration with BDM Python API for file and folder management via ``EntityHandle``
  - OpenTelemetry instrumentation (logging, tracing, metrics)
  - Multi-deployment support (desktop, on-premises, cloud) from a single codebase
  - Built-in solution testing fixtures for API and UI testing


.. _components_saf_cli:

SAF CLI
-------

The command-line interface for SAF developers. It streamlines the entire solution lifecycle from
scaffolding to packaging.

- **Package name**: ``ansys-saf-cli``
- **Key features**:

  - ``saf new``—scaffold a solution from a Cookiecutter template
  - ``saf install``—set up the solution's Poetry-managed virtual environment
  - ``saf run``—launch the solution locally (API + UI + ...). Uses the ``ansys-saf-desktop-orchestrator`` package under the hood.
  - ``saf build``—generate a standalone desktop installer. Uses the ``ansys-saf-desktop-installer`` package under the hood.
  - ``saf add-step``—add a new step from a template plugin. Uses the ``ansys-saf-templates`` package under the hood.
  - ``saf execute``—run arbitrary commands inside the solution's environment
  - ``saf archive``—create a ``.saf`` source archive


.. _components_desktop_orchestrator:

SAF Desktop Orchestrator
-------------------------

The central controller for running SAF solutions in standalone desktop environments. It manages
the lifecycle of all services required by a solution—Solution API, Solution UI, OTel Dashboard,
SAF Portal, PIM Light Server, and any additional custom services.

- **Package name**: ``ansys-saf-desktop-orchestrator``
- **Key features**:

  - Sequential service startup with concurrent health checking
  - Support for Dash, Streamlit, or headless (no UI) modes
  - pywebview integration for native desktop window on Windows
  - Automatic project creation or selection at launch
  - Cross-platform process management (Windows + Linux)
  - Configurable via environment variables and ``.env`` files

Components managed by SAF Desktop Orchestrator include:

* ``Solution API``: Provides an interface derived from the solution that exposes a view of project data and enables transaction methods to be executed.
* ``Solution UI``: Displays the solution front-end in its own native window without the need for an external web browser.
* ``OTel Dashboard`` (enterprise feature): A web dashboard displaying logging and tracing information from the various services in the solution.
* ``SAF Portal`` (enterprise feature): This component provides a portal for creating and accessing projects in a solution.
* ``PIM Light Server`` (enterprise feature): This component handles the creation of a product instance in an isolated environment that is separated from the environment where the method executes.
* ``Additional services``: Additional services defined by the solution, such as stateless services like ADR.


.. _components_desktop_installer:

SAF Desktop Installer
---------------------

Packages SAF solutions into self-contained, distributable desktop installers. The generated
executable includes the Python interpreter and all dependencies.

- **Package name**: ``ansys-saf-desktop-installer``
- **Key features**:

  - Online and offline installer modes
  - Automatic Python interpreter bundling
  - Code encryption and obfuscation for IP protection (enterprise feature)
  - Embedded Sphinx documentation accessible from the UI
  - Desktop shortcuts and Start menu integration (Windows)
  - Configurable Python version selection


.. _components_product_configuration:

SAF Product Configuration
-------------------------

Provides protocol-based interfaces and ready-to-use product definitions for launching and
configuring Ansys products within SAF solutions.

- **Package name**: ``ansys-saf-product-configuration``
- **Key features**:

  - ``IProductInstanceConfiguration`` protocol for consistent product identity contracts
  - Built-in configurations for AEDT, Fluent, Geometry, MAPDL, Mechanical, optiSLang, and Visor


.. _components_product_manager:

SAF Product Manager
-------------------


Provides out-of-the-box PyAnsys-powered managers to launch and control Ansys product instances
within SAF solutions.

- **Package name**: ``ansys-saf-product-manager``
- **Key features**:

  - Consistent API for initializing, connecting to, and controlling supported products
  - Built-in managers for AEDT, Fluent, Geometry, MAPDL, Mechanical, optiSLang, and Visor
  - Integration with SAF GLOW Engine for lifecycle management


.. _components_bdm_python_api:

SAF BDM Python API
------------------

Defines abstract interfaces (Python protocols) for managing files and directories in SAF
applications. It provides the contract between application code and storage backends.

- **Package name**: ``ansys-bdm-api``
- **Key features**:

  - ``EntityHandle``—immutable, frozen Pydantic model referencing stored entities
  - ``IStorageScope`` / ``IAsyncStorageScope``—read-write storage access protocols
  - ``IReadStorageScope`` / ``IAsyncReadStorageScope``—read-only access protocols
  - Stream-based entity creation via ``IEntityWriter``
  - Directory hierarchy support via ``RecursiveDictionaryOfEntityHandles``
  - Fully abstract—no dependency on any specific storage backend


.. _components_bdm_shared_volume:


BDM Python Shared Volume
----------------------------

A concrete implementation of BDM Python API that uses the local or network filesystem as the
storage backend. Ideal for desktop and on-premises deployments.

- **Package name**: ``ansys-bdm-shared-volume``
- **Key features**:

  - Implements ``IStorageScope``, ``IAsyncStorageScope``, and ``IStorageScopeFactory``
  - Template variable substitution in storage paths (``$TEMP_DIR``, ``$PROJECT_ID``, ``$UUID``)


.. _components_super_components_for_dash:

Dash Super Components
~~~~~~~~~~~~~~~~~~~~~~~~

A library of pre-assembled, high-level UI components tailored for simulation web applications
built with Plotly Dash.

- **Package name**: ``ansys-solutions-dash-super-components``
- **Key features**:

  - Ready-to-use components for common simulation UI patterns
  - Reduces boilerplate for building step-based wizard interfaces


.. _components_iam_oidc:

IAM OIDC
--------

Provides OAuth 2.0 / OpenID Connect authentication for SAF applications. It handles token
validation and user info retrieval without requiring developers to implement OIDC protocol
details.

- **Package name**: ``ansys-iam-oidc``
- **Key features**:

  - ``OidcClient`` / ``AsyncOidcClient`` for JWT signature and claims verification
  - ``OidcDependency``—FastAPI dependency injector for HTTP Bearer token extraction
  - ``OidcWebSocketDependency``—WebSocket subprotocol-based token extraction
  - ``get_user_info()`` with automatic fallback to the provider's userinfo endpoint
  - ``UserInfo`` Pydantic model with 22 standard OIDC claims


.. _components_saf_testing:

SAF Testing
------------

A centralized collection of reusable testing utilities, fixtures, and helper methods for
testing the SAF SDK ecosystem. For testing Solutions, refer to the fixtures provided by SAF GLOW Engine.

- **Package name**: ``ansys-saf-testing``
- **Key features**:

  - 14 pytest plugins registered via entry points for automatic fixture discovery
  - ``Process`` utility—subprocess wrapper with health checks and background mode
  - Selenium fixtures for browser-based end-to-end testing
  - Network utilities (free ports, local IP, TLS certificates)
  - Docker container management fixtures
  - Platform markers (``windows_only``, ``linux_only``, ``skip_for_ci``)


.. _components_saf_templates:

SAF Templates
--------------

A Cookiecutter-based template collection for scaffolding reusable solution steps. Consumed via
the ``saf add-step`` command in SAF CLI.

- **Package name**: ``ansys-saf-templates``
- **Key features**:

  - Plugin architecture—custom template repositories can be registered via entry points
  - Built-in templates: calculator step, HPS job submission, parametric study, geometry instance management
  - Automatic dependency injection into the solution's ``pyproject.toml``
  - SAF CLI compatibility range enforcement via semantic versioning
  - Post-generation hooks for file placement into the solution structure


.. _components_meta_package:

Meta-package
============

``ansys-saf-sdk`` is a meta-package that bundles the core SAF packages into a single, versioned
package. It contains no code of its own—it only declares dependencies on the individual SAF
packages, pinned to their latest compatible versions.


Purpose
--------

Because the SAF packages depend on each other (see :ref:`components_dependency_graph`), not every
combination of their versions is valid. The meta-package solves this by acting as the single source
of truth for the validated combination:

* **Compatibility**: All core packages are pinned to exact versions that are released and tested
  together, so they can be installed side by side without version conflicts.
* **A single version to track**: You declare one dependency, ``ansys-saf-sdk``, and its version
  identifies the whole SAF stack your solution is built against.
* **Simpler upgrades**: Moving to a new SAF release means bumping one version constraint instead of
  aligning six or more package versions by hand.
* **Scenario-based installation**: Optional extras let you pull in only the packages required by
  your deployment, frontend framework, and Ansys product integrations.

.. note::
   The meta-package covers the runtime packages consumed by a solution. Developer tooling and
   frontend libraries are installed separately: :ref:`components_saf_cli`, :ref:`components_saf_templates`,
   and :ref:`components_super_components_for_dash` are not part of ``ansys-saf-sdk``.


Core dependencies
-----------------

Installing ``ansys-saf-sdk`` installs these packages by default:

* ``ansys-bdm-api`` (see :ref:`components_bdm_python_api`)
* ``ansys-bdm-shared-volume`` (see :ref:`components_bdm_shared_volume`)
* ``ansys-saf-glow-engine`` (see :ref:`components_glow_engine`)
* ``ansys-iam-oidc`` (see :ref:`components_iam_oidc`)
* ``ansys-saf-product-configuration`` (see :ref:`components_product_configuration`)
* ``ansys-saf-product-manager`` (see :ref:`components_product_manager`)

The following diagram shows what the meta-package pulls in. Solid arrows are the core dependencies,
installed by default; dashed arrows are packages added by an optional extra.

.. mermaid::

   %%{init: {"flowchart": {"nodeSpacing": 30, "rankSpacing": 60, "htmlLabels": true}} }%%
   graph LR
      SDK["&nbsp;&nbsp;ansys-saf-sdk&nbsp;&nbsp;"]

      subgraph CORE["Core dependencies"]
         GLOW["&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;SAF GLOW Engine&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"]
         PROD_CFG["&nbsp;SAF Product Configuration&nbsp;"]
         PROD_MGR["&nbsp;&nbsp;&nbsp;SAF Product Manager&nbsp;&nbsp;&nbsp;"]
         BDM_API["&nbsp;&nbsp;&nbsp;&nbsp;BDM Python API&nbsp;&nbsp;&nbsp;&nbsp;"]
         BDM_SV["&nbsp;&nbsp;&nbsp;BDM Python Shared Volume&nbsp;&nbsp;&nbsp;"]
         OIDC["&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;IAM OIDC&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"]
      end

      subgraph EXTRAS["Optional extras"]
         ORCH["&nbsp;Desktop Orchestrator&nbsp;&nbsp;"]
         INST["&nbsp;&nbsp;&nbsp;Desktop Installer&nbsp;&nbsp;&nbsp;"]
      end

      SDK --> GLOW
      SDK --> PROD_CFG
      SDK --> PROD_MGR
      SDK --> BDM_API
      SDK --> BDM_SV
      SDK --> OIDC

      SDK -.->|desktop| ORCH
      SDK -.->|build| INST

      style SDK fill:#34495e,stroke:#1c2833,color:#fff
      style GLOW fill:#4a90d9,stroke:#2c5f8a,color:#fff
      style BDM_API fill:#f0932b,stroke:#b36b1e,color:#fff
      style BDM_SV fill:#f0932b,stroke:#b36b1e,color:#fff
      style OIDC fill:#f0932b,stroke:#b36b1e,color:#fff
      style ORCH fill:#9b59b6,stroke:#6c3483,color:#fff
      style INST fill:#9b59b6,stroke:#6c3483,color:#fff
      style PROD_CFG fill:#e74c3c,stroke:#a93226,color:#fff
      style PROD_MGR fill:#e74c3c,stroke:#a93226,color:#fff


.. _components_meta_package_extras:

Extras
------

Optional extras pull in additional packages, or extras of the core packages, for specific scenarios:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Extra
     - Description

   * - ``core-dash``
     - SAF GLOW Engine support for Dash-based frontends.

   * - ``core-pim``
     - SAF GLOW Engine support for Product Instance Management (PIM).

   * - ``core-hps``
     - SAF GLOW Engine support for HPC Platform Services (HPS).

   * - ``core-test``
     - SAF GLOW Engine testing utilities.

   * - ``core-mcp``
     - SAF GLOW Engine support for the Model Context Protocol (MCP).

   * - ``core-all``
     - All optional extras of the core packages.

   * - ``instance-management``
     - SAF Product Configuration and SAF Product Manager packages.

   * - ``instance-management-fluent``
     - Instance management support for Ansys Fluent.

   * - ``instance-management-aedt``
     - Instance management support for Ansys Electronics Desktop (AEDT).

   * - ``instance-management-optislang``
     - Instance management support for Ansys optiSLang.

   * - ``instance-management-geometry``
     - Instance management support for Ansys Geometry.

   * - ``instance-management-mapdl``
     - Instance management support for Ansys MAPDL.

   * - ``instance-management-mechanical``
     - Instance management support for Ansys Mechanical.

   * - ``instance-management-visor``
     - Instance management support for Visor-based products.

   * - ``instance-management-all``
     - All instance management product integrations.

   * - ``desktop``
     - SAF Desktop Orchestrator, for running solution applications as desktop apps.

   * - ``build``
     - SAF Desktop Installer, for building standalone desktop installers.

   * - ``all``
     - Every optional extra combined.

Extras can be combined. For example, a Dash solution that drives Fluent and runs as a desktop
application requires ``core-dash``, ``instance-management-fluent``, and ``desktop``.


Installation
------------

Install the meta-package like any other Python package. Extras are given as a comma-separated list
in square brackets.

Two requirements apply before you run the install command: pip must be upgraded, and pip must be
allowed to consider pre-releases.

.. _components_meta_package_install_pip_version:

Upgrade pip first
~~~~~~~~~~~~~~~~~

``ansys-saf-sdk`` requires **pip 26 or later**. Upgrade pip in the target environment before
installing the meta-package:

.. code-block:: bash

   python -m pip install --upgrade pip

.. warning::
   If pip is not upgraded, the installation fails. Upgrade pip and run the install command again.

.. tip::
   Check the pip version of the environment you are installing into with:

   .. code-block:: bash

      python -m pip --version


.. _components_meta_package_install_commands:

Install commands
~~~~~~~~~~~~~~~~

The pip commands pass the ``--pre`` flag because some third-party dependencies of the SAF
components are only published as pre-releases. In particular, the OpenTelemetry instrumentation
packages required by :ref:`components_glow_engine` are released as beta versions, such as
``0.65b0``. PEP 440 classifies these as pre-releases, and pip ignores pre-releases by default, so
without ``--pre`` the resolution fails reporting that no matching distribution was found.

.. tab-set::

    .. tab-item:: pip

        Upgrade pip, then install the core packages only:

        .. code-block:: bash

            pip install --pre ansys-saf-sdk

        Install the core packages with extras:

        .. code-block:: bash

            pip install --pre "ansys-saf-sdk[core-dash,instance-management-fluent,desktop]"

        Install everything:

        .. code-block:: bash

            pip install --pre "ansys-saf-sdk[all]"

    .. tab-item:: Poetry

        Add the meta-package to a solution:

        .. code-block:: bash

            poetry add "ansys-saf-sdk[core-dash,instance-management-fluent,desktop]"

        Alternatively, declare it in the solution's ``pyproject.toml`` file and run
        ``saf install``:

        .. code-block:: toml

            [tool.poetry.dependencies]
            ansys-saf-sdk = { version = "^0.1.0", extras = [
                "core-dash",
                "instance-management-fluent",
                "desktop",
            ] }


Usage
-----

The meta-package exposes no modules of its own. Import from the individual packages exactly as you
would without it:

.. code-block:: python

   from ansys.saf.glow.solution import Solution, StepModel, StepSpec, transaction

Because ``ansys-saf-sdk`` pins its core dependencies to exact versions, adding another explicit
constraint on one of those packages in the same environment can create a conflict. Let the
meta-package own the versions of the packages it bundles, and declare only the extras you need.

.. seealso::
   * :ref:`ug-install` for installing a solution environment and managing its dependencies.
   * :ref:`prerequisites_saf_cli` for installing SAF CLI, which is not part of the meta-package.
