.. _environment_variables:

Environment variables
#####################

Alongside the command-line interface (SAF CLI) parameters, SAF supports configuration through the use of environment variables. Solutions can be
configured using multiple methods; when multiple methods are used, SAF resolves conflicts based on a defined order of precedence.


Configuration methods
=====================

You can use either SAF CLI or Solutions Manager to configure the solution using :ref:`SAFCLI parameters <envar-config-cli-parameters>`, :ref:`system environment variables <envar-config-system-envvar>`, or an :ref:`environment file <envar-config-environment-file>`. The following sections describe each method.


.. _envar-config-cli-parameters:

CLI parameters
---------------

SAF CLI parameters are configuration options passed directly via the command-line interface when
launching the solution. You can use these to configure the solution only if you are using SAF CLI.

.. code-block:: bash

   my_solution api --port 50002 --host 0.0.0.0


.. _envar-config-system-envvar:

Environment variables
----------------------

System environment variables are set in your shell or system configuration. You can configure the solution with these using either SAF CLI or Solutions Manager.

.. tab-set::

   .. tab-item:: SAF CLI

    Set environment variables using SAF CLI:

      .. tab-set::

         .. tab-item:: Windows (PowerShell)

            .. code-block:: powershell

               $env:GLOW_API_PORT = "50001"
               $env:GLOW_API_HOST = "0.0.0.0"

         .. tab-item:: Linux/macOS

            .. code-block:: bash

               export GLOW_API_PORT=50001
               export GLOW_API_HOST=0.0.0.0

   .. tab-item:: Solutions Manager

      Set environment variables using Solutions Manager:

      #. Open Visual Studio Code.

      #. In the Activity Bar, click the **Run Solution** icon.

      #. Under **Solution environment**, click the :guilabel:`Configure solution environment`.

         The **SAF Environment Configuration** interface opens in the editor. Environment settings are divided into categories.

      #. Find the environment variable you want to set:

         * Use the search bar to search for a specific environment variable.
         * Expand the **Filter by category** and select a category.

           .. image:: /_static/images/getting_started_solutions_manager_saf_environ_config_page.png
              :alt: Solutions Manager SAF Environment Configuration page
              :width: 90%

      #. Modify the configuration parameters as needed:

         * Select or deselect the check box to enable or disable an environment variable.
         * Once an environment variable is enabled, you can modify its value in the **Value** field,
           either by selecting from a drop-down list or by entering a value.
         * Click the :guilabel:`Enable all` or :guilabel:`Disable all` button to quickly enable or
           disable all environment variables in the selected category.

      #. Click the :guilabel:`Save configuration` button to save your changes.

         The configuration is saved in a ``.env`` file in the solution's root directory.
         When the solution is launched from Solutions Manager, it will use the saved configuration file.

      #. Close the editor page to exit the **SAF Environment Configuration** interface.


.. _envar-config-environment-file:

Environment file
----------------

An environment file (``.env``) contains key-value pairs for configuration variables. By default, the file is loaded from your current working directory.
You can configure the solution with this file using either SAF CLI or Solutions Manager.

.. tab-set::

   .. tab-item:: SAF CLI

      Use the ``--env-file`` SAF CLI parameter to specify a custom location:

      .. code-block:: text

         # .env file
         GLOW_API_PORT=50000
         GLOW_API_HOST=127.0.0.1
         GLOW_DEBUG=True

      To use a custom environment file:

      .. code-block:: bash

         my_solution api --env-file /path/to/custom.env

      When the solution is launched from SAF CLI, it will use the selected environment configuration file.

   .. tab-item:: Solutions Manager

      Select an environment file using Solutions Manager:

      #. Open Visual Studio Code.

      #. In the Activity Bar, click the **Run Solution** icon.

      #. Under **Solution environment**, click the button next to the **Select an environment file** search bar,
         then browse to and select the ``.env`` file you want to use.

         Alternatively, enter the path to the ``.env`` file directly in the search bar.

         .. image:: /_static/images/solutions_manager_environment_variables_file.png
          :alt: Solutions Manager environment variables file
          :width: 35%

      When the solution is launched from Solutions Manager, it will use the selected environment configuration file.


Order of precedence
===================

When multiple configuration methods are used, SAF resolves conflicts based on a defined order of precedence. This ensures that the most specific configuration takes priority over more general settings. Configuration values follow a standard precedence hierarchy, from highest to lowest:

#. **CLI parameters** (highest precedence):

   Command-line arguments override all other configuration sources.

#. **Environment variables**:

   System environment variables override values from the environment file.

#. **Environment file** (lowest precedence):

   Values from the environment file (``.env``) are used if not specified elsewhere.


Order of precedence example
----------------------------

Consider the configuration for the :envvar:`GLOW_API_PORT` setting:

* If you define :envvar:`GLOW_API_PORT=50000` in your ``.env`` file, the value is used as the base configuration.

* If you set the environment variable *before* execution, as shown below, the environment variable value (``50001``) overrides the ``.env`` file value:

  .. tab-set::

     .. tab-item:: Windows (PowerShell)

         .. code-block:: powershell

             $env:GLOW_API_PORT = "50001"

     .. tab-item:: Linux/macOS

         .. code-block:: bash

             export GLOW_API_PORT=50001


* If you provide a SAF CLI parameter *during* execution, as shown below, the SAFCLI parameter value (``50002``) takes precedence over both the
  environment variable and the ``.env`` file:

  .. code-block:: bash

     my_solution api --port 50002


.. seealso::

   Variables that accept a Boolean value accept the values documented in the `Types/booleans <https://docs.pydantic.dev/2.0/usage/types/booleans/>`_ section of the official Pydantic documentation.


Configuration environment variables
===================================

The environment variables used to configure SAF are listed below. The default values are provided for reference, but they may vary based on the solution and deployment context.


Deployment
-----------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_DEPLOYMENT`
     - Specifies the deployment where SAF GLOW Engine runs.
     - Permitted values:

       -  ``Desktop`` (default)
       -  ``DockerCompose``

API server
----------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_API_HOST`
     - Specifies the host where the solution API server runs.
     - ``127.0.0.1``

   * - :envvar:`GLOW_API_PORT`
     - Specifies the port where the solution API server runs.
     - ``5432``

   * - :envvar:`GLOW_SOLUTION_DEFINITION`
     - Specifies the solution definition module to use when launching the API
       application directly via a production server instead of SAF GLOW Engine's CLI.

       **Example:** ``ansys.solutions.my_solution.solution.definition``
     - Auto-discovered (varies by solution)

UI server
----------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_UI_HOST`
     - Specifies the host where the solution UI server runs.
     - ``127.0.0.1``

   * - :envvar:`GLOW_UI_PORT`
     - Specifies the port where the solution UI server runs.
     - ``5433``

   * - :envvar:`GLOW_API_URL`
     - Specifies the URL of the solution API server.
     - ``http://127.0.0.1:5432``

   * - :envvar:`GLOW_EXTERNAL_API_URL`
     - Specifies the URL of the GLOW API server in a form accessible to the user machine (for example, ``http://127.0.0.1:5432``). Enables the access to the content of an entity handle or a file reference from the user machine (for example, from a browser).

       * In desktop deployments, this value is automatically set to :envvar:`GLOW_API_URL`.
       * In on-premises deployments, you must set this value because :envvar:`GLOW_API_URL` contains a URL accessible only from within the UI container (for example, ``http://my-solution-api:50000``).

     - The value of :envvar:`GLOW_API_URL`

   * - :envvar:`GLOW_PORTAL_URL`
     - Specifies the URL of the Portal server.
     - ``None``

   * - :envvar:`GLOW_UI_PROJECT_FILES_DIRECTORY`
     - Specifies the absolute path to the project files directory that is shared with the GLOW API server in a
       form accessible to the UI server, for deployments where the UI server runs on a different system than the GLOW API server.
     - ``None``

   * - :envvar:`GLOW_WS_EVENTS_ADDR`
     - Specifies the URL of the GLOW API server in a form accessible to the host machine (for example, ``http://127.0.0.1:5432``)
       prefixed with the websocket protocol (for example, ``ws://127.0.0.1:5432`` or ``wss://127.0.0.1:5432``). Enables
       websockets created within Dash client to connect to the websocket endpoint within the GLOW API server.

       * In desktop deployments, this value is automatically resolved from :envvar:`GLOW_API_URL`.
       * In on-premises deployments, you must set this value because :envvar:`GLOW_API_URL` contains a URL
         accessible only from within the UI container (for example, ``http://my-solution-api:50000``).

     - Resolved from the :envvar:`GLOW_API_URL`:
       ``ws://127.0.0.1:5432``

   * - :envvar:`GLOW_GRAPHQL_POOL_SIZE`
     - Specifies the number of available GraphQL clients that can be used concurrently.

       (DashClient is using GraphQL internally to communicate with the GLOW API. Therefore, a small pool size may impact the performance for a solution used by many concurrent users.)

     - ``3``

   * - :envvar:`GLOW_UI_MODULE`
     - Specifies the module containing the UI's Dash application.

       Used to specify the module when launching the UI application directly via a production server instead of GLOW's CLI.

       **Example:** ``ansys.solutions.my_solution.ui.app``

     -

BDM Python API
--------------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_BDM_GC_DISABLED`
     - Disables BDM Python API garbage collection when set to ``True``.
     - ``False``


.. _pim-configuration:

Product Instance Manager
-------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_PRODUCT_INSTANCE_SYSTEM`
     - Specifies the Product Instance Manager system to be used.
     - Permitted values:

       -  ``PIM`` (default)
       -  ``HPS``

   * - :envvar:`GLOW_PRODUCT_INSTANCE_SYSTEM_HOST`
     - Specifies the host where the Product Instance Manager system runs.
     - ``127.0.0.1``

   * - :envvar:`GLOW_PRODUCT_INSTANCE_SYSTEM_PORT`
     - Specifies the port where the Product Instance Manager system runs.
     - ``None``

   * - :envvar:`GLOW_PIM_SOCKET_PATH`
     - Specifies the path to the UNIX socket file used by PIM Light Server.

       Required to connect to PIM Light Server on Linux when :envvar:`GLOW_PRODUCT_INSTANCE_SYSTEM_HOST` is set to ``localhost``.
     - ``None``

   * - :envvar:`GLOW_PRODUCT_HOST`
     - Specifies the host where the product is running (not the manager system).

       * For HPS, must be set in the environment where the product instance is running, not in the GLOW API environment.
       * For PIM, set it in the GLOW API environment. Overrides the value retrieved automatically from the Product Instance Manager system.
     - ``None``

   * - :envvar:`GLOW_PRODUCT_BINDING_HOST`
     - Sets the TCP host or IP address where the product instance listens for connections.

       (Not to be confused with the ``GLOW_PRODUCT_HOST`` environment variable. ``GLOW_PRODUCT_HOST`` is the address used to connect to the product instance from outside, whereas ``GLOW_PRODUCT_BINDING_HOST`` is the address where the product instance listens for connections).

       * For HPS, must be set in the environment where the product instance runs, not in the GLOW API environment.
       * For PIM, must be set in the environment where PIM runs.

     - ``0.0.0.0``

   * - :envvar:`GLOW_PRODUCT_INSTANCE_SYSTEM_PROJECT_FILES_DIRECTORY`
     - Specifies the absolute path to the project files directory shared with
       the GLOW API server in a form accessible to the product when the Product
       Instance Manager system runs on a different system.
     - ``None``

   * - :envvar:`GLOW_PRODUCT_INSTANCE_SYSTEM_PLATFORM`
     - Specifies the platform where the Product Instance Manager system runs
       when it is on a different system than the GLOW API server.

       Permitted values:

       -  ``Windows``
       -  ``Linux``

     - ``None``

   * - :envvar:`ANSYS_GRPC_CERTIFICATES`
     - Specifies the path to the directory where the gRPC certificates used by
       PIM Light Server are stored.

       These certificates are required to connect to PIM Light Server
       when ``GLOW_PRODUCT_INSTANCE_SYSTEM_HOST`` is not ``localhost``.
     - ``None``

   * - :envvar:`SAF_OPTISLANG_TIMEOUT`
     - Timeout in seconds for requests to managing the OptiSLang server instance.
     - ``300``

   * - :envvar:`SAF_VISOR_TIMEOUT`
     - Timeout in seconds for requests to managing the Visor server instance.
     - ``300``


.. _hps_jobs_configuration:

HPS system for job and parametric study submission
---------------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_HPS_HOST`
     - Sets the host where the HPS system runs.
     - ``127.0.0.1``

   * - :envvar:`GLOW_HPS_PORT`
     - Sets the port where the HPS system listens.
     - ``None``

.. note::

   If the noted pair of values are not present, then the
   HPS system for job and parametric will be the one configured
   to be the product instance manager system if it is a HPS system.
   See the :ref:`section on configuring the product instance manager system <pim-configuration>`.

Authentication
--------------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_AUTH_ISSUER_URL`
     - Specifies the address of the Identity Provider (usually Keycloak) for
       authenticated access to the GLOW API.

       **Example:** ``https://localhost:8443/hps/auth/realms/rep``

     - ``None``

   * - :envvar:`GLOW_AUTH_CLIENT_ID`
     - Specifies the public oauth2 identifier of the solution API.

       **Example:** ``my-solution-api``
     - ``None``

   * - :envvar:`GLOW_AUTH_DISABLED`
     - Disables API authorization when set to ``True``.
     - ``True``

   * - :envvar:`GLOW_API_KEY`
     - Provides the API key for authenticating local requests to the API server.

       When set, requests originating from ``localhost`` that carry this value in the ``x-api-key``
       header are authenticated without OIDC validation.

       Mutually exclusive with :envvar:`GLOW_API_KEY_FILE`.

     - ``None``

   * - :envvar:`GLOW_API_KEY_FILE`
     - Provides the absolute path to a file containing the API key for authenticating local requests to the API server.

       The path must be absolute and the file must exist.

       Mutually exclusive with :envvar:`GLOW_API_KEY`.

     - ``None``


HPS authentication
-------------------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_HPS_CLIENT_ID`
     - Specifies the client ID of the HPS system in Keycloak for Keycloak-based authentication.

       **Example:** ``rep-jms-web``

     - ``rep-jms-web``

   * - :envvar:`GLOW_HPS_USERNAME`
     - Specifies the username to log in to the HPS system for username/password authentication.

       **Example:** ``repadmin``
     - ``""``

   * - :envvar:`GLOW_HPS_PASSWORD`
     - Specifies the password to log in to the HPS system for username/password authentication.

       **Example:** ``repadmin``
     - ``None``

.. note::

   If both types of HPS authentication are configured, Keycloak-based has priority.

Solution configuration
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_OVERWRITE_SOLUTION_CONFIG`
     - Specifies whether to allow overwriting of the persisted solution configuration when there
       is a version update.
     - ``None``

Directories
------------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_PROJECT_FILES_DIRECTORY`
     - Specifies the full OS file system path to the directory for storing the project files.
     - ``%APPDATA%/ansys/glow/SOLUTION_NAME/project_files/``

Transaction method child processes
-----------------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_METHOD_CLEANUP_CHILD_PROCS`
     - Specifies whether to automatically kill child processes spawned by a long-running transaction
       method after it completes.

       For more information, see :ref:`child_process_cleanup`.
     - ``True``

Database
---------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_DATABASE_TYPE`
     - Specifies the type of database to be used.
     - Permitted values:

       - ``sqlite`` (default)
       - ``postgresql``

   * - :envvar:`GLOW_DATABASE_LOCATION`
     - Specifies the location of the database.

       Can be a file path (for ``sqlite``) or a ``postgres``
       connection URI of the form ``postgresql://username:password@host:port``

     - ``%APPDATA%/ansys/glow/SOLUTION_NAME/glow.db``


Data repository
----------------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_DATA_REPOSITORY_TYPE`
     - Specifies the type of data repository to be used.

       Permitted values:

       -  ``FileSystem`` (only for development)
       -  ``Minerva``

     - ``None``

   * - :envvar:`GLOW_DATA_REPOSITORY_UPLOAD_ROOT`
     - Specifies the absolute path in the data repository to which a relative upload path is appended when uploading data.

       If the upload path is an absolute path, the upload path is used.
     - ``/Data``

Project migration
-----------------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION`
     - Enables automatic project migration when set to ``True``.

       This environment variable should only be enabled for development, never in a production environment.
     - ``False``

Logging
--------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`SAF_DESKTOP_LOG_TO_FILES`
     - Specifies whether to log to files under ``$APPDATA/ansys/glow/<MySolution>/logs/`` and disable OTel Dashboard.

       This option is mutually exclusive with ``OTEL_EXPORTER_OTLP_ENDPOINT``. If both environment variables are set, an error is raised.
       (Note that this sets the SAF GLOW Engine environment variables for log configuration files, overriding any existing value.)
     - ``False``

   * - :envvar:`GLOW_LOG_CONFIG`
     - Specifies the full OS file system path to the ``YAML`` logging configuration file for the API service.
     - ``None``

   * - :envvar:`GLOW_UI_LOG_CONFIG`
     - Specifies the full OS file system path to the ``YAML`` logging configuration file for the UI service.
     - ``None``

   * - :envvar:`GLOW_METHOD_LOG_CONFIG`
     - Specifies the full OS file system path to the ``YAML`` logging configuration file for the Method Runner.
     - ``None``

   * - :envvar:`GLOW_LOGGING_LEVEL`
     - Specifies the logging level for ``ansys`` loggers.

       Overwrites values from log configurations.
     - ``INFO``

Telemetry
---------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`OTEL_EXPORTER_OTLP_ENDPOINT`
     - Specifies the endpoint for the OTLP exporters (traces, logs, and metrics).

       Non-URL values enable export to process output.
     - ``None``

Debugging
----------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_DEBUG`
     - Specifies whether debugging in SAF GLOW Engine is enabled.
     - ``False``

   * - :envvar:`GLOW_API_HOT_RELOAD`
     - Enables API hot reload when set to ``True``.

       Only works if debug mode is activated.
     - ``True``

   * - :envvar:`GLOW_API_HOT_RELOAD_MONITORING_DIR`
     - Sets the directory that SAF GLOW Engine monitors for changes when API hot reload is enabled.

       For solutions generated with SAF CLI, the default behavior prevents unnecessary API server reloads
       when only UI files are modified.

     - If the module location can be resolved, that directory is used; otherwise,
       the current working directory is used.

   * - :envvar:`GLOW_UI_PYTHON_DEBUGGING`
     - Enables Python debugging in the GLOW UI.

       Setting it to ``True`` implies that ``debugpy.listen`` is invoked by the UI server
       process and the debug functionality of Dash / Flask is disabled.
     - ``False``

   * - :envvar:`GLOW_DEBUG_API_PORT`
     - Specifies the Python debugger port for the GLOW API service.
     - ``5724``

   * - :envvar:`GLOW_DEBUG_UI_PORT`
     - Specifies the Python debugger port for the GLOW UI service.
     - ``5725``

.. note::

  Debugging works only when the solution is executed via SAF GLOW Engine's CLI, not when it is executed using a production server.

  ..  To know more about the ways to run a solution, see the SAF CLI documentation.

Events
----------

.. list-table::
   :header-rows: 1
   :widths: 20 55 25

   * - Variable
     - Description
     - Default values

   * - :envvar:`GLOW_WS_EVENT_POLL_INTERVAL`
     - Sets the interval, in seconds, in the event transmission loop for a websocket connection.

       Each iteration of the loop queries the database for new events and transmits those events via the websocket.
       :envvar:`GLOW_WS_EVENT_POLL_INTERVAL` is the duration of the pause between iterations of the loop.

       If a solution raises events in a transaction method and consumes them via web sockets, then:

       * Reducing this value makes a solution UI respond more quickly to those events, but increases the load on the database server and may negatively impact the overall performance of the solution.

       * Increasing this value reduces the load on the database server and may positively impact the overall performance of the solution, but makes the solution UI respond more slowly to the transaction method events.

     - ``1.0``

Portal API
----------

.. list-table::
    :header-rows: 1
    :widths: 20 55 25

    * - Variable
      - Description
      - Default values

    * - :envvar:`PORTAL_API_VERSION`
      - Specifies the API version of SAF Portal used to communicate with it.
      - ``v1``

Services
--------

.. list-table::
    :header-rows: 1
    :widths: 20 55 25

    * - Variable
      - Description
      - Default values

    * - :envvar:`SAF_DESKTOP_HEALTH_CHECK_TIMEOUT`
      - Sets the maximum time, in seconds, to wait for a service (for example, API, UI, Portal, or PIM) to become healthy after it has been started.
      - ``25`` seconds
