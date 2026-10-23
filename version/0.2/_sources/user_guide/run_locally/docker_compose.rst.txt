.. _ug-run-docker-compose:

Run a solution with Docker Compose
####################################

SAF solutions can run as containerized services using Docker Compose. Every SAF solution generated via
``saf new`` includes pre-configured Compose files in the ``deployments/`` directory:

.. code-block:: text

   deployments/
   ├── standalone/
   │   └── compose.yaml           # Solution only
   ├── standalone-with-hps/
   │   └── compose.yaml           # Solution + HPS
   └── distributed-deployment-template/
       └── compose.yaml           # Solution + HPS + Web Portal


Container deployment prerequisites
===================================

.. list-table::
  :header-rows: 1
  :stub-columns: 1
  :widths: 30 70

  * - Prerequisite
    - Description
  * - WSL (Windows only)
    - `WSL <https://learn.microsoft.com/en-us/windows/wsl/install>`_
  * - Virtualization
    - `Docker Desktop <https://docs.docker.com/desktop/setup/install/windows-install/>`_ (requires a license)
      or `Docker Engine <https://docs.docker.com/engine/install/>`_ (open-source)
  * - Environment variables
    - Set :envvar:`MACHINE_IP` with the IP address of your machine if you use Docker Desktop or the IP address of your WSL if you use WSL.

Standalone deployment
=====================

.. rubric:: Purpose:

Development and testing environment for the solution in isolation.

.. rubric:: Description:

The standalone deployment is designed for developers to verify that the solution works properly in containerized mode. It starts only the core services of the solution without external dependencies.

.. rubric:: Services included:

- PostgreSQL database
- Solution REST API (SAF GLOW)
- Solution UI (Dash framework, if configured)
- OpenTelemetry dashboard for observability

.. rubric:: Usage:

This deployment is **not meant for production** but is ideal for:

- Developing and testing solutions locally
- Verifying solution functionality in containers
- Debugging solution-specific issues

.. _user-guide-docker-compose-run:

Run the solution
-----------------

#. Navigate to the solution root directory.

#. Start the services (wait for all services to start):

   .. code-block:: bash

      docker compose -f deployments/standalone/compose.yaml up --build

#. Open a web page and reach the GLOW API Swagger UI: ``http://localhost:8000/docs``

#. Create a project using the ``Create Project`` POST request.

#. Copy the project name from the response. It should look like: ``projects/<project-id>``

#. Open the Solution UI: ``http://localhost:8001/projects/<project-id>``

Now you can walk through the solution workflow.


Shut down the solution
-----------------------

To shut down the solution:

#. Press :kbd:`CTRL+C` in the terminal where you executed the previous Docker command, or

#. Turn the Docker containers down:

   .. code-block:: bash

      docker compose -f deployments/standalone/compose.yaml down


Standalone deployment with HPS
================================

.. rubric:: Purpose:

Development environment that includes HPS (HPC Platform Services) integration.

.. rubric:: Description:

This deployment extends the standalone setup by adding HPS components to the landscape. It helps developers debug the connection between HPS and SAF.

.. rubric:: Services included:

- All services from standalone deployment
- Integration with external HPS network
- Traefik labels for external routing

.. rubric:: Prerequisites:

- HPS must be started first and running.
- :envvar:`EXT_NETWORK_NAME` environment variable must be set to match the HPS external network.

.. rubric:: Usage:

This deployment is **not meant for production** but is ideal for:

- Testing HPS integration
- Debugging communication between SAF and HPS
- Validating solution behavior with HPS services

Run the solution
-----------------

#. Ensure that HPS is running.

#. Set the external network name:

   .. code-block:: bash

      export EXT_NETWORK_NAME=<hps-network-name>

#. Navigate to the solution root directory.

#. Start the services (wait for all services to start):

   .. code-block:: bash

      docker compose -f deployments/standalone-with-hps/compose.yaml up --build

#. Access the solution API and UI as described in the :ref:`Standalone deployment <user-guide-docker-compose-run>` instructions (points 3 to 6).


Shut down the solution
----------------------

#. Press :kbd:`CTRL+C` in the terminal where you executed the previous Docker command, or

#. Turn the Docker containers down:

   .. code-block:: bash

      docker compose -f deployments/standalone-with-hps/compose.yaml down


Platform-specific dependencies configuration
==============================================

The ``deployments/Dockerfile`` supports platform-specific dependencies using Poetry extras and build arguments.

.. rubric:: How to use:

- By default, the Dockerfile installs only the base dependencies.
- To install platform-specific dependencies (for example: HPS, Minerva, Dash), pass the ``EXTRAS`` build argument when building the container, separated by commas.

.. rubric:: Examples:

.. tab-set::

   .. tab-item:: Build with multiple extras

      .. code-block:: bash

         docker compose build --build-arg EXTRAS="hps,pim,minerva"

   .. tab-item:: Compose file

      .. code-block:: yaml

         solution-api:
           build:
             context: ../../
             dockerfile: deployments/Docker/Dockerfile
             args:
               EXTRAS: "hps,pim,minerva"


Development workflow
====================

All Compose files support Docker Compose ``watch`` mode for hot-reloading during development:

.. code-block:: bash

   docker compose up --build --watch

This automatically syncs and restarts containers when you modify source files in the ``solution/`` or ``ui/``
directories.


Stop services
=============

To stop and remove all containers:

.. code-block:: bash

   docker compose down

To also remove persistent volumes (database data, project files):

.. code-block:: bash

   docker compose down -v


Release a new solution version
==============================

When you release a new version of an existing solution, two files must be updated — no changes to the
Compose files themselves are required.

#. Update ``pyproject.toml``:

   Bump the ``version`` field in your solution's ``pyproject.toml`` to the new release version:

   .. code-block:: toml

      [tool.poetry]
      name    = "my-solution"
      version = "1.1.0"   # <-- update this

#. Update the ``.env`` file for each deployment template:

   Each deployment template has its own ``.env`` file, as shown in the following table. Update :envvar:`APP_NAME` in every ``.env``
   file you intend to use.

   .. list-table::
      :header-rows: 1
      :widths: 30 70

      * - Deployment template
        - Path to the ``.env`` file
      * - Standalone
        - ``deployments/standalone/.env``
      * - Standalone with HPS
        - ``deployments/standalone-with-hps/.env``
      * - Distributed deployment
        - ``deployments/distributed-deployment-template/.env``

   .. note::
      The :envvar:`APP_NAME` should follow the same pattern as the value generated by ``saf new``:
       ``<solution-package-name>_<version-with-dashes>``. The version is taken from ``pyproject.toml``, with dots replaced by dashes (for example, ``1.1.0`` becomes ``1-1-0``).


   In each of those files, update :envvar:`APP_NAME` to reflect the new version:

   .. code-block:: bash

      # Docker resource name (derived from the pyproject.toml version; replace dots with dashes)
      APP_NAME=my-solution_1-1-0

   .. note::

      The :envvar:`APP_NAME` environment variable is used to name all Docker resources (networks, volumes, and images such as
      ``${APP_NAME}-api`` and ``${APP_NAME}-ui``). Embedding the version in :envvar:`APP_NAME` ensures
      that each release produces uniquely tagged artefacts and avoids conflicts with previously
      deployed containers.

#. Rebuild and restart the services:

   After saving both files, rebuild the images and restart the services:

   .. code-block:: bash

      docker compose -f deployments/<template>/compose.yaml up --build