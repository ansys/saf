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
   ├── external/
   │   └── compose.yaml           # Solution using pre-built images
   └── distributed-deployment-template/
       └── compose.yaml           # Solution + HPS + Web Portal

The standalone, standalone-with-HPS, and distributed deployments build solution images locally from
``deployments/Dockerfile``. The external deployment uses pre-built solution images instead, so the
deployment machine does not need access to the Python package sources used to build those images.


Container deployment prerequisites
===================================

.. list-table:: Comparison of container deployment prerequisites
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


.. _user-guide-docker-compose-external:

External deployment with pre-built images
=========================================

Use the external deployment to run a solution without building its API and UI images on the deployment
machine. It provides the same core services as the standalone deployment: PostgreSQL, the solution API,
the optional solution UI, and an OpenTelemetry dashboard.

Build and download the images
-----------------------------

The generated solution includes a ``build solution images`` GitHub Actions workflow in
``.github/workflows/build-image.yml``. It builds the ``solution_api`` Dockerfile target and, when a UI
is configured, the ``solution_ui`` target. It saves the images into a single tar file and uploads that
file as a workflow artifact.

The workflow also runs as part of the generated solution's ``build and release`` workflow through a
reusable workflow call, using the default image tag ``main``. To build images manually with another tag:

#. Open the generated solution repository on GitHub and select the **Actions** tab.

#. Select **build solution images**, then **Run workflow**.

#. Select the branch to build and set ``image_tag`` to a valid Docker image tag, such as ``1.1.0``.
   The default is ``main``.

#. After the workflow succeeds, download the ``<APP_NAME>-images-<tag>`` artifact from the workflow
   run summary and extract its ZIP archive. It contains ``<APP_NAME>-images-<tag>.tar``.
   Artifacts are retained for 30 days.

The tar file contains ``<APP_NAME>-api:<tag>`` and, when applicable, ``<APP_NAME>-ui:<tag>``.
``APP_NAME`` is the Docker name generated for the solution.

.. note::

   The tar file contains only the solution images. PostgreSQL and the OpenTelemetry dashboard use
   separate images referenced in ``deployments/external/compose.yaml``. Docker may pull these images
   when starting the deployment. For an offline deployment, these images must also be available on
   the deployment machine.

Load and run the solution
-------------------------

#. Transfer the image tar file and the generated ``deployments/external/`` directory, including its
   ``.env`` file, to the deployment machine.

#. Load the images into the Docker engine that will run the solution. Replace the placeholders with
   the downloaded file's name:

   .. code-block:: bash

      docker load -i <APP_NAME>-images-<tag>.tar

#. In ``deployments/external/.env``, ensure that ``APP_NAME`` matches the loaded images' name and
   ``APP_IMAGE_VERSION`` matches their tag. For example:

   .. code-block:: bash

      APP_NAME=my-solution_1-1-0
      APP_IMAGE_VERSION=1.1.0

   Configure the other deployment settings as needed. Before sharing or deploying the solution,
   replace the placeholder OpenTelemetry API key in both ``.env`` and ``compose.yaml`` with the same
   secure value.

#. Navigate to the external deployment directory and start the services:

   .. code-block:: bash

      cd deployments/external
      docker compose up -d --wait

#. Access the API at ``http://localhost:8000/docs`` and, when configured, the UI at
   ``http://localhost:8001/projects/<project-id>``. Create a project through the API first, as described
   in :ref:`user-guide-docker-compose-run`. These URLs use the default ports from ``.env``.

The API and UI services use ``pull_policy: never`` and have no build configuration. If a solution
image is missing or its name or tag does not match ``.env``, startup fails instead of pulling or
building a replacement.

To stop the services, run the following command from ``deployments/external/``:

.. code-block:: bash

   docker compose down


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

For development deployments configured with Docker Compose ``watch`` mode, use:

.. code-block:: bash

   docker compose up --build --watch

This automatically syncs and restarts containers when you modify source files in the ``solution/`` or ``ui/``
directories.

The external deployment runs pre-built images and does not configure source synchronization or
rebuilding. To apply source changes, build and load new images instead.


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

   .. list-table:: Comparison of deployment template environment files
      :stub-columns: 1
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
      * - External deployment
        - ``deployments/external/.env``

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

#. Update the images and restart the services:

   For deployments that build locally, rebuild the images and restart the services:

   .. code-block:: bash

      docker compose -f deployments/<template>/compose.yaml up --build

   For the external deployment, build and download new images as described in
   :ref:`user-guide-docker-compose-external`. Load the new tar file, match ``APP_NAME`` and
   ``APP_IMAGE_VERSION`` in ``deployments/external/.env`` to the loaded images, and restart from
   ``deployments/external/``:

   .. code-block:: bash

      docker compose up -d --wait

   Changing ``pyproject.toml`` or ``.env`` alone does not update pre-built images.