.. _user_guide_run_on_desktop:

Run a solution on desktop
##########################

You can run a solution locally on your desktop using any of the following methods:

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 25 75

   * - Run method
     - Description

   * - :ref:`SAF CLI <user_guide_run_using_saf_cli>`
     - * Runs a solution with the ``saf run`` command by preparing the solution
         environment and invoking SAF Desktop Orchestrator.
       * Provides a convenient way to run solutions with configurable options.

   * - :ref:`Solutions Manager <user_guide_run_using_saf_cli>`
     - * Provides a Visual Studio Code extension that wraps SAF CLI's ``saf run`` command and provides a graphical interface
         for running solutions.
       * Supports users who prefer to manage and run solutions without the command line.

   * - :ref:`SAF Desktop Orchestrator <user_guide_run_using_saf_desktop_orchestrator>`
     - * Provides a direct orchestration entry point that coordinates the API, UI, and supporting services with configurable
         orchestration options.
       * Supports advanced users and CI/CD pipelines that require more control than SAF CLI provides.

   * - :ref:`GLOW CLI <user_guide_run_using_the_glow_cli>`
     - * Runs the solution API and UI independently, allowing developers to configure and manage each component separately.
       * Supports developers who need to debug or customize individual solution components.


.. tip::

  Start with SAF CLI or Solutions Manager for standard development workflows. Use SAF Desktop Orchestrator or GLOW CLI if you need specific customization.


.. _user_guide_run_using_saf_cli:

Run using SAF CLI
==================

You can run a solution with the ``saf run`` command using either SAF CLI or Solutions Manager. This command starts the full solution stack (API, UI, OTel Dashboard, and optional services) by invoking SAF Desktop Orchestrator.


.. _user_guide_run_using_saf_cli_solution_ui_modes:

Solution execution modes
--------------------------

When running a solution using SAF CLI (or Solutions Manager) you can open the solution in a :ref:`desktop window <user_guide_run_desktop_window>`, a :ref:`web browser <user_guide_run_web_browser>`, or the :ref:`SAF Portal <user_guide_run_saf_portal>`.


.. _user_guide_run_desktop_window:

Run in a desktop window
~~~~~~~~~~~~~~~~~~~~~~~~

.. tab-set::

  .. tab-item:: SAF CLI

    Run a solution in a desktop window using SAF CLI:

    .. code-block:: bash

       saf run <solution-name>

    For example:

    .. code-block:: bash

       saf run minimal-solution

  .. tab-item:: Solutions Manager

    Run a solution in a desktop window using Solutions Manager:

    #. Open Visual Studio Code.

    #. In the Activity Bar, click the **Solutions Manager** icon.

    #. In the **Solutions Manager**  pane, expand the **Create Solution** view.

    #. In the **Solutions Manager**  pane, expand the **Run Solution** view.

       .. image:: /_static/images/solutions_manager_run_solution_view_desktop.png
          :alt: Solutions Manager Run Solution in desktop view
          :width: 50%

    #. Provide the following values:

       a. Select the solution you want to run.

          You can either select an option from the list of available solutions or browse the solution folder of a different one.

       b. Select your run options:

          Ensure that **Portal mode** and **Browser mode** are not selected.

       c. Select a log level:

          The default log level is **INFO**. You can select a different log level if needed.

       d. Enter a project name.

          Enter the name of the project you want to run.

       e. If needed, configure the solution environment.

          .. seealso::
            The **Run Solution** pane provides options for specifying the solution environment. For more information, see :ref:`envar-config-system-envvar` and :ref:`envar-config-environment-file` in the :ref:`environment_variables` page.

    #. Run the solution.

       Click the :guilabel:`Run solution` button. Alternatively, you can copy the command under **Solution run command** and run it in the terminal.

The solution UI opens in a desktop window.

.. image:: /_static/images/getting_started_quick_start_minimal_solution_intro_page.png
   :alt: Solution opened in a desktop window


.. _user_guide_run_web_browser:

Run in a web browser
~~~~~~~~~~~~~~~~~~~~

.. tab-set::

    .. tab-item:: SAF CLI

      Run the solution in a web browser using SAF CLI:

      .. code-block:: bash

        saf run --browser

    .. tab-item:: Solutions Manager

      Run the solution in a web browser using Solutions Manager:

      #. Open Visual Studio Code.

      #. In the Activity Bar, click the **Solutions Manager** icon.

      #. In the **Solutions Manager**  pane, expand the **Run Solution** view.

         .. image:: /_static/images/solutions_manager_run_solution_view_browser.png
            :alt: Solutions Manager Run Solution in browser view
            :width: 50%

      #. Provide the following values:

         a. Select the solution you want to install.

            You can either select an option from the list of available solutions or browse the solution folder of a different one.

         b. Select your run options:

            Ensure that **Browser mode** is selected.

         c. Select a log level:

            The default log level is **INFO**. You can select a different log level if needed.

         d. Enter a project name.

            Enter the name of the project you want to run.

          e. If needed, configure the solution environment.

             .. seealso::
               The **Run Solution** pane provides options for specifying the solution environment. For more information, see :ref:`envar-config-system-envvar` and :ref:`envar-config-environment-file` in the :ref:`environment_variables` page.

      #. Run the solution.

         Click the :guilabel:`Run solution` button. Alternatively, you can copy the command under **Solution run command** and run it in the terminal.

The solution UI opens in a web browser window.

.. image:: /_static/images/minimal_solution_intro_page_browser.png
   :alt: Solution opened in a browser window


.. _user_guide_run_saf_portal:

Run from SAF Portal
~~~~~~~~~~~~~~~~~~~~~~~~

.. tab-set::

    .. tab-item:: SAF CLI

      Run the solution from SAF Portal using SAF CLI:

      .. code-block:: bash

        saf run --portal

    .. tab-item:: Solutions Manager

      Run the solution from SAF Portal using Solutions Manager:

      #. Open Visual Studio Code.

      #. In the Activity Bar, click the **Solutions Manager** icon.

      #. In the **Solutions Manager**  pane, expand the **Run Solution** view.

         .. image:: /_static/images/solutions_manager_run_solution_view_portal.png
            :alt: Solutions Manager Run Solution in Portal view
            :width: 45%

      #. Provide the following values:

         a. Select the solution you want to install.

            You can either select an option from the list of available solutions or browse the solution folder of a different one.

         b. Select your run options:

            Ensure that **Portal mode** is selected.

         c. Select a log level:

            The default log level is **INFO**. You can select a different log level if needed.

         d. Enter a project name.

            Ener the name of the project you want to run.

         e. If needed, configure the solution environment.

            .. seealso::
              The **Run Solution** pane provides options for specifying the solution environment. For more information, see :ref:`envar-config-system-envvar` and :ref:`envar-config-environment-file` in the :ref:`environment_variables` page.

      #. Run the solution.

         Click the :guilabel:`Run solution` button. Alternatively, you can copy the command under **Solution run command** and run it in the terminal.

The solution opens in the SAF Portal user interface. SAF Portal provides a project management interface for the solution, allowing you to create new projects, view existing projects, and manage project settings.

.. image:: /_static/images/minimal_solution_portal_ui_empty.png
   :alt: Solution opened in SAF Portal


The ``saf run`` command
--------------------------

When you run a solution with a UI using ``saf run``, the following happens:

#. A project with a random name is automatically created (for example, ``my-project-2569``).
#. A PyWebView window opens with the solution UI for that project.
#. SAF Portal is **not** launched by default.

.. note::

   On Linux, the UI opens in a browser tab instead of PyWebView. To get the same behavior on Windows, use the
   ``--browser`` option as described in :ref:`user_guide_run_web_browser`.


``saf run`` options
--------------------

The ``saf run`` command has multiple command-line options. To see them all, run the following command:

.. code-block:: bash

   saf run --help

Options are divided into :ref:`user_guide_saf_run_options_ui_and_display`, :ref:`user_guide_saf_run_options_debugging`, and :ref:`user_guide_saf_run_options_port_configuration` categories, as detailed in the following sections.


.. _user_guide_saf_run_options_ui_and_display:

UI and display options
~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 25 75

   * - Option
     - Description

   * - ``--portal``
     - Opens the Portal UI instead of the solution UI, so you can manage multiple projects.

   * - ``--no-ui``
     - Runs the solution without starting the UI server.

   * - ``--browser``
     - Opens the UI in your default web browser instead of in a PyWebView window.

   * - ``--streamlit-ui``
     - Runs the solution UI using the Streamlit framework instead of Dash.


.. _user_guide_saf_run_options_debugging:

Debugging options
~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 25 55 20

   * - Option
     - Description
     - Default value

   * - ``--debug``
     - Runs the solution in debug mode. Enables hot-reloading of code changes.
     - Disabled

   * - ``--ui-debugger``
     - Enables ``debugpy`` in the UI process and disables the Dash/Flask debugger. Use this to attach an
       external debugger to the UI.
     - Disabled

   * - ``--loglevel <LEVEL>``
     - Sets the logging level. One of ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, or ``CRITICAL``.
     - Not set

   * - ``--log-to-files``
     - Logs to files under ``$APPDATA/ansys/glow/<MySolution>/logs/`` instead of showing the OTel Dashboard.
       Overrides any existing GLOW environment variables that configure logging.
     - Disabled


.. _user_guide_saf_run_options_port_configuration:

Port configuration
~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 25 55 20

   * - Option
     - Description
     - Default value

   * - ``--portal-ui-port <PORT>``
     - Sets the port on which the Portal UI runs.
     - Random available port

   * - ``--solution-api-port <PORT>``
     - Sets the port on which the Solution API runs.
     - Random available port

   * - ``--solution-ui-port <PORT>``
     - Sets the port on which the Solution UI runs.
     - Random available port

Project and environment options
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 25 55 20

   * - Option
     - Description
     - Default value

   * - ``--project <NAME>``
     - Specifies the display name of the project to open or create. You cannot use this option when
       SAF Portal is
       running. If omitted, a project with a randomly generated name (for example, ``my-project-2569``) is created.
     - Not set

   * - ``--env-file <PATH>``
     - Loads environment variables from this file.
     - ``.env`` in the solution root directory, if present

   * - ``--no-automatic-project-migration``
     - Disables automatic schema migration for projects created with an older solution version.
     - Disabled


``saf run`` console output
---------------------------

The console output for ``saf run`` provides all the information you need to interact with the running solution. It includes:

- Solution name and debug status
- Project name and display name
- Solution API URL (with Swagger docs at ``/docs``)
- Solution UI URL
- OTel Dashboard URL (logs and traces from each service)
- Status of optional services (SAF Portal, PIM Light Server, additional services)


.. code-block:: console

   [...=GLOW API]- Telemetry enabled, using OTLP logging configuration for GLOW API
   [...=GLOW UI]- Telemetry enabled, using OTLP logging configuration for GLOW UI
   * Serving Flask app 'ansys.solutions.my_solution.ui.app'
   * Debug mode: off
   INFO - Solution: My Solution
   INFO - Project:
   - display name: my-project-2569
   - name: projects/6800b09f77e87f3a18a39f0a
   INFO - Solution API: http://127.0.0.1:49929/docs
   INFO - Solution UI: http://127.0.0.1:49933/projects/6800b09f77e87f3a18a39f0a
   INFO - OTel Dashboard: http://127.0.0.1:49930
   INFO - SAF Portal: not launched
   INFO - PIM Light Server: not launched
   INFO - Additional services: not launched
   INFO - Starting webview...



.. _user_guide_run_using_saf_desktop_orchestrator:

Run using SAF Desktop Orchestrator
=====================================

Alternatively, you can run a solution using SAF Desktop Orchestrator directly. This is useful for advanced users who want to customize the orchestration process.

The orchestrator is installed as a Python package in the virtual environment of the solution. To install it, run:

.. code-block:: bash

   python -m ansys.saf.desktop.orchestrator \
   --solution-main-module-name <package>.<submodule>.<main_module>

Replace ``<package>.<submodule>.<main_module>`` with the full Python module name of the module containing the ``glow_main`` call for your solution.
For example, to start the orchestrator for the solution whose main module is located at ``src/ansys/solutions/my_solution/main.py``, run:

.. code-block:: bash

   python -m ansys.saf.desktop.orchestrator \
   --solution-main-module-name ansys.solutions.my_solution.main


The ``desktop.orchestrator`` command
--------------------------------------

When you run a solution using SAF Desktop Orchestrator (without flags), the following happens:

#. A project with a random name is automatically created (for example, ``my-project-2569``).
#. A PyWebView window opens with the solution UI for that project (on Windows). On other platforms, a browser tab opens instead.
#. SAF Portal is **not** launched by default.
#. On Windows, a splash screen displays while services start up.


``desktop.orchestrator`` options
--------------------------------

SAF Desktop Orchestrator has multiple command-line options. To see them all without starting the orchestrator, run:

.. code-block:: bash

   python -m ansys.saf.desktop.orchestrator --help

Options are divided into :ref:`orchestrator_command_options_required` and :ref:`orchestrator_command_options_optional` categories, as detailed in the
following sections.

.. _orchestrator_command_options_required:

Required
~~~~~~~~

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 50 50

   *  - Option
      - Description

   *  - ``--solution-main-module-name SOLUTION_MAIN_MODULE_NAME``
      - Specifies the full name of the Python module that contains the ``glow_main`` call.

        For example, the ``ansys.solutions.my_solution.main`` module refers to the ``src/ansys/solutions/my_solution/main.py`` file.


.. _orchestrator_command_options_optional:

Optional
~~~~~~~~

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 40 40 20

   *  - Option
      - Description
      - Default value

   *  - ``--portal``
      - Opens the project selection UI instead of the solution UI.

        If the ``ansys-projects-dashboard`` package is installed, the orchestrator opens the
        Projects Dashboard page in the solution UI instead of starting SAF Portal.
        Otherwise, it starts SAF Portal and opens the Portal UI.

        The Projects Dashboard path defaults to ``/projects``. To use a different path, set the
        :envvar:`SAF_DESKTOP_PROJECTS_DASHBOARD_PATH` environment variable.
      - Disabled

   *  - ``--no-ui``
      - Runs the solution without starting the UI server.
      - Disabled

   *  - ``--browser``
      - Opens the solution UI in the default web browser instead of a dedicated window.
      - Disabled

   *  - ``--streamlit-ui``
      - Runs the solution with Streamlit as the UI server.
      - Disabled

   *  - ``--project-display-name PROJECT_DISPLAY_NAME``
      - Specifies the display name of the project to open or create.

        You cannot use this option when SAF Portal is running.

        If you do not specify a display name, the orchestrator generates one in the format ``my-project-XXXXX``.
      - Not set

   *  - ``--env-file ENV_FILE``
      - Loads environment variables from this file.
      - ``.env`` in current directory

   *  - ``--no-automatic-project-migration``
      - Disables automatic schema migration upgrades for old projects.
      - Disabled

   *  - ``--log-to-files``
      - Logs to files instead of showing the OTel Dashboard.

        You can also enable this option by setting the environment variable
        :envvar:`SAF_DESKTOP_LOG_TO_FILES=True`, which overrides any existing GLOW
        environment variables that configure logging.
      - Disabled

   *  - ``--pre-load``
      - Runs the full solution stack without opening the solution UI window, then shuts down immediately.

        Use this option to warm up or validate a solution without displaying it, for example during
        installer builds.
      - Disabled

.. note::
   When SAF Portal is not started, the orchestrator always initializes a project,
   regardless of whether a project display name is provided. If no display name
   is provided, the project is named ``my-project-XXXXX``, where ``XXXXX`` is a
   random number.


``desktop.orchestrator`` console output
----------------------------------------

The console output displays the following information:

* Debug status
* Solution name
* Project name and display name
* Solution API/UI and OTel Dashboard URLs
* Status of services: ``Portal``, ``PIM Light Server``, and additional services

.. code-block::

  # Orchestrator output
  [...=GLOW API]- Telemetry enabled, using OTLP logging configuration for GLOW API
  [...=GLOW UI]- Telemetry enabled, using OTLP logging configuration for GLOW UI
  * Serving Flask app 'ansys.solutions.my_solution.ui.app'
  * Debug mode: off
  INFO - Solution: My Solution
  INFO - Project:
  - display name: my-project-2569
  - name: projects/6800b09f77e87f3a18a39f0a
  INFO - Solution API: http://127.0.0.1:49929/docs
  INFO - Solution UI: http://127.0.0.1:49933/projects/6800b09f77e87f3a18a39f0a
  INFO - OTel Dashboard: http://127.0.0.1:49930
  INFO - SAF Portal: not launched
  INFO - PIM Light Server: not launched
  INFO - Additional services: not launched
  INFO - Starting webview...


.. _user_guide_run_using_the_glow_cli:

Run using the GLOW CLI
===========================

The GLOW CLI lets you run the solution API (backend) and the solution UI (frontend) independently. This is useful for advanced scenarios where you need fine-grained control over individual servers.

When to use the GLOW CLI
---------------------------

Use the GLOW CLI when you need to:

* Debug the API and UI independently
* Start only one part of the solution
* Control API and UI startup from separate terminals
* Switch from the built-in CLI wrappers to lower-level production server commands

For most local development workflows, use :ref:`SAF CLI <user_guide_run_using_saf_cli>` or :ref:`SAF Desktop Orchestrator <user_guide_run_using_saf_desktop_orchestrator>` instead.

How the GLOW CLI works
-----------------------

A SAF solution has two web applications:

* **Solution API**: The backend service that handles solution logic and data
* **Solution UI**: The frontend web application that users open in the browser

You can start each application in one of two ways:

* **Standard**: Use the GLOW CLI wrapper commands.
* **Advanced**: Call the production server directly.

In practice, a common workflow is:

#. Start the solution API in one terminal.
#. Start the solution UI in a second terminal.
#. Open the solution UI URL reported in the terminal output.


Solution API execution
-----------------------

To run the solution API, you can use the GLOW CLI or directly launch the app using a production server such as ``uvicorn``.


Run using the GLOW API
~~~~~~~~~~~~~~~~~~~~~~~~

The ``glow_engine api`` command launches a simple uvicorn server with only a few parameters exposed.

Run the following command to start the solution that is inside the ``ansys.solutions.<solution_name>`` environment:

.. code-block:: bash

   glow_engine api

This script automatically runs the following Python module: ``python -m ansys.saf.glow.cli api``.

.. note::
    This command automatically detects the entry point of the solution, which is expected to be ``ansys/solutions/<solution_name>/solution/definition.py``.

    If your solution has a different structure, use the ``--definition`` argument to specify the correct module using dot notation:

    .. code-block:: bash

       glow_engine api --definition tests.mocks.solutions.minimal_solution


The ``glow_engine api`` command
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you run the solution API using ``glow_engine api``, the following happens:

#. The REST API server starts and binds to the localhost and port specified (default: ``127.0.0.1:5432``).
#. The API is available at ``http://127.0.0.1:5432`` with interactive Swagger documentation at ``/docs``.
#. No project is automatically created. You must create projects using the API endpoints or other tools.
#. The UI server is **not** started. You must start it separately in another terminal using ``glow_engine ui``.


``glow_engine api`` command options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``glow_engine api`` command has multiple options. To see them all, run the following command:

.. code-block:: bash

   glow_engine api --help


The following ``glow_engine api`` options are available:


.. list-table:: GLOW API options
   :header-rows: 1
   :stub-columns: 1
   :widths: 25 60 15

   * - Option
     - Description
     - Default value

   * - ``--host TEXT``
     - Binds the server socket to this host.
     - ``127.0.0.1``

   * - ``--port INTEGER``
     - Binds the server socket to this port.
     - ``5432``

   * - ``--pim-host TEXT``
     - Specifies the host on which the product instance management system is running.
     - ``127.0.0.1``

   * - ``--pim-port INTEGER``
     - Specifies the port on which the product instance management system is running.
     - Not set

   * - ``--cors-origin TEXT``
     - Specifies the origins that are permitted to make cross-origin requests.
     - Not set

   * - ``--definition TEXT``
     - Specifies the solution definition module.
     - Not set

   * - ``--solution TEXT``
     - Specifies the solution module.
     - Not set

   * - ``--env-file PATH``
     - Loads environment variables from this file. If you do not specify a file, the command searches for ``.env`` in the current directory.
     - Not set


Run using a production server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To get full control over the parameters used by the server, you can directly call a production server such as ``uvicorn``
to start the solution API:

.. code-block:: bash

   uvicorn ansys.saf.glow.api:app --host <host> --port <port>

.. note::
    This command automatically detects the definition of the solution, which is expected to be ``ansys/solutions/<solution_name>/solution/definition.py``.

    If your solution has a different structure, set the environment variable :envvar:`GLOW_SOLUTION_DEFINITION` to specify the correct module using dot notation.

.. attention::
  You cannot use :envvar:`GLOW_API_HOST` and :envvar:`GLOW_API_PORT` to configure the host and port of the uvicorn server.
  However, GLOW needs to know in which host and port it is running for its proper functioning and this information is not
  retrieved automatically from ``uvicorn`` either. Therefore, you must configure both the ``uvicorn`` port and host, and
  GLOW's environment variables :envvar:`GLOW_API_PORT` and :envvar:`GLOW_API_HOST` to the same values.

.. seealso::
  For more information on the options available to configure the server, see `Settings <https://uvicorn.dev/settings/?h=settings/>`_ in the official Uvicorn documentation.


Solution UI execution
-------------------------

To run only the solution UI, you can use the GLOW CLI or directly launch the app using production servers such as ``gunicorn``
(Linux) or ``waitress`` (Windows and Linux).


Run using the GLOW UI
~~~~~~~~~~~~~~~~~~~~~~

Run the following command to start the solution UI that is inside the ``ansys.solutions.<solution_name>`` environment:

.. code-block:: bash

   glow_engine ui

This script automatically runs the following Python module: ``python -m ansys.saf.glow.cli ui``.

.. note::
    This command automatically detects the entry point of the solution, which is expected to be ``ansys/solutions/<solution_name>/main.py``.

    If your solution has a different structure, use the ``--solution`` argument to specify the correct module using dot notation:

    .. code-block:: bash

       glow_engine ui --solution tests.mocks.solutions.minimal_solution


The ``glow_engine ui`` command
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you run the solution UI using ``glow_engine ui``, the following happens:

#. The Dash UI server starts and binds to the localhost and port specified (default: ``127.0.0.1:5433``).
#. The UI is available at ``http://127.0.0.1:5433`` and is ready for browser access.
#. The UI connects to a solution API server. If no API URL is specified, the UI starts but will display connection errors until the API is running.
#. No project is automatically created. Projects must be managed by creating them first via the API or another method.


``glow_engine ui`` options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``glow_engine ui`` command has multiple options. To see them all, run the following command:

.. code-block:: bash

   glow_engine ui --help

The following ``glow_engine ui`` options are available:

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 25 60 15

   * - Option
     - Description
     - Default value

   * - ``--host TEXT``
     - Binds the server socket to this host.
     - ``127.0.0.1``

   * - ``--port INTEGER``
     - Binds the server socket to this port.
     - ``5433``

   * - ``--api-server-url TEXT``
     - Specifies the URL of the solution API server.
     - Not set

   * - ``--portal-ui-url TEXT``
     - Specifies the URL of the Portal UI.
     - Not set

   * - ``--solution TEXT``
     - Specifies the solution module.
     - Not set

   * - ``--env-file PATH``
     - Loads environment variables from this file. If you do not specify a file, the command searches for ``.env`` in the current directory.
     - Not set


Run using a production server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To get full control over the parameters used by the server, you can directly call it using a production server such as ``gunicorn`` (Linux)
or ``waitress`` (Windows and Linux) to start the solution UI:

.. tab-set::

  .. tab-item:: Gunicorn

    .. code-block:: bash

      gunicorn -b <host>:<port> ansys.saf.glow.ui:app


  .. tab-item:: Waitress

    .. code-block:: bash

      waitress-serve ansys.saf.glow.ui:app --port <port> --host <host>


.. note::
  This command automatically detects the definition of the solution, which is expected to be ``ansys/solutions/<solution_name>/solution/definition.py``,
  and the solution UI application, which is expected to be ``ansys/solutions/<solution_name>/ui/app.py``.

  If your solution has a different structure, set the environment variables :envvar:`GLOW_SOLUTION_DEFINITION` and :envvar:`GLOW_UI_MODULE` to specify
  the correct modules using dot notation:

  .. code-block:: bash

     export GLOW_SOLUTION_DEFINITION=tests.mocks.solutions.minimal_solution.solution.definition
     export GLOW_UI_MODULE=tests.mocks.solutions.minimal_solution.ui.app

.. attention::
  You cannot use :envvar:`GLOW_UI_HOST` and :envvar:`GLOW_UI_PORT` to configure the host and port of the ``gunicorn/waitress``
  server. However, GLOW needs to know in which host and port it is running for its proper functioning and this information is
  not retrieved automatically from ``gunicorn/waitress`` either. Therefore, you must configure both the ``gunicorn/waitress``
  port and host, and GLOW's environment variables :envvar:`GLOW_UI_PORT` and :envvar:`GLOW_UI_HOST` to the same values.

  If you have used non-default values to configure the host and port of the API, you must also configure the environment
  variable :envvar:`GLOW_API_URL`. Check :ref:`environment_variables` for more details about this environment variable.

.. seealso::
  For more information on the options available to configure the server, see `Settings <https://gunicorn.org/reference/settings/>`_ in the official Gunicorn documentation and `Arguments <https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html#arguments>`_ in the official Waitress documentation.


.. _user_guide_run_archived_solution:

Run an archived solution
========================

You can run an archived solution using the Solution App Starter utility (``solution-app-starter`` script). It provides a convenient, one-click method for launching archived solutions, making it easier to share, test, and validate solution packages.

To run an archived solution using the Solution App Starter:

.. code-block:: bash

   saf execute <solution_name> "solution-app-starter <archived_solution>"

The solution UI opens in a desktop window.


The ``solution-app-starter`` script
-------------------------------------

When you run the ``solution-app-starter`` script, it performs the following actions:

#. **Launches the solution**: Starts the solution using GLOW without launching SAF Portal or other optional services.
#. **Creates a new project**: Generates a new project with a unique, randomly assigned name.
#. **Opens the solution UI**: Opens the solution user interface for the newly created project.

Each execution uses a temporary directory for data storage and creates a new project instance. This ensures that every run starts in a clean, isolated environment.

The ``solution-app-starter`` script cleans the temporary directory when execution completes.

.. note::

   To ensure the extracted solution can be correctly imported and executed, the temporary directory is added to the beginning (position 0) of Python's module search path (``sys.path``), and the :envvar:`PYTHONPATH` environment variable is set to contain the whole ``sys.path``.


``solution-app-starter`` console output
----------------------------------------

The console displays the same information as when calling the ``ansys.saf.desktop.orchestrator`` module. The temporary data storage directory is logged with the format ``APPDATA set to``. For example:

.. code-block:: bash

   solution_app_starter:Extracting solution to temp directory C:\Users\test\AppData\Local\Temp\tmpfg0yp17z...
   solution_app_starter:Added solution directory C:\Users\test\AppData\Local\Temp\tmpfg0yp17z\src to PYTHONPATH.
   solution_app_starter:Loading solution in file C:\Users\test\AppData\Local\Temp\tmpfg0yp17z\src\ansys\solutions\my_archived_solution\main.py
   solution_app_starter:APPDATA set to C:\Users\test\AppData\Local\Temp\tmp6ltewxeg.
   solution_app_starter:Starting project with display_name 673b7cec-da45-48ef-a03a-34deb21cc7b4...
   _telemetry.instrumentor]- Orchestrator logging to C:/.../logs/orchestration/log_zkdrn748.log
   =GLOW UI]- GLOW UI logging to C:/.../logs/ui_server/log_m86ikn60.log
   =GLOW API]- GLOW API logging to C:/.../logs/api_server/log_0fc8b2sr.log
   * Serving Flask app 'ansys.solutions.my_archived_solution.ui.app'
   * Debug mode: on
   Solution: My Solution
   Project:
   - display name: my-project-8915
   - name: projects/67d2e4ae13ae5d580c08b1e4
   Solution API: http://127.0.0.1:61925/docs
   Solution UI: http://127.0.0.1:61926/projects/67d2e4ae13ae5d580c08b1e4
   SAF Portal: not launched
   PIM Light Server: not launched
   Additional services: not launched

.. seealso::
   For instructions on solution archiving, see :ref:`user_guide_archive_a_solution`.