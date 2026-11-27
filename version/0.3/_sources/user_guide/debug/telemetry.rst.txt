.. _debug_with_telemetry:

Debug with telemetry
####################


What is telemetry?
==================

Telemetry refers to the automated collection and transmission of data about a running application's
behavior and performance. In the context of SAF, telemetry covers three pillars:

- **Logs**: Structured messages emitted during execution (informational, warnings, errors).
- **Traces**: End-to-end records of a request as it flows through different components, useful for
  identifying bottlenecks and failures.
- **Metrics**: Numerical measurements aggregated over time (request durations, active connections,
  response sizes).

SAF uses `OpenTelemetry <https://opentelemetry.io/>`_ as the standard for instrumentation, generation,
collection, and export of telemetry data. This ensures compatibility with any observability stack that
supports the OpenTelemetry protocol (OTLP).

To visualize this data, SAF recommends the
`.NET Aspire dashboard <https://aspire.dev/dashboard/overview/>`_, a lightweight web UI that displays
structured logs, distributed traces, and metrics in a single place. Any other OTLP-compatible backend
(Grafana, Jaeger, Datadog) works as well.


Set up the Aspire dashboard
============================

There are two ways to make the Aspire dashboard available during development. Choose the approach that
matches your setup.

Use ``saf run`` with the Aspire package
-----------------------------------------

:enterprise-badge:`Enterprise Feature`

.. admonition:: Available to Ansys customers and Channel Partners
   :class: enterprise

   This feature is available to Ansys customers and Channel Partners.
   `Contact the PyAnsys team <mailto:pyansys-core@synopsys.com>`_ to request access.

When running a solution on desktop through the SAF orchestrator (``saf run``), the simplest approach is
to install the ``ansys-saf-aspire`` package in the solution's virtual environment:

Once the package is installed, SAF Desktop Orchestrator automatically detects it and starts the
Aspire dashboard server when you run the solution with ``saf run``. No additional configuration is
required.

The dashboard URL is displayed in the terminal output:

.. code-block:: none

   INFO - OTEL Dashboard: http://localhost:18888/login?t=...

Open this URL in your browser to access structured logs, traces, and metrics.

.. note::
   If you prefer not to see the dashboard or want to log to files instead, pass the
   ``--log-to-files`` flag to ``saf run``.


Use Docker (without the Aspire package or orchestrator)
----------------------------------------------------------

If you run the solution without the orchestrator (for example using ``glow_engine api`` and
``glow_engine ui`` directly) or if you do not have the ``ansys-saf-aspire`` package installed, you can
start the Aspire dashboard manually via Docker.

.. note::
   These instructions assume that Docker is already installed.

#. Launch the ``.NET Aspire dashboard`` container:

   .. code-block:: bash

      docker run --rm -it -p 18888:18888 -p 4318:18889 --name aspire-dashboard mcr.microsoft.com/dotnet/aspire-dashboard:9.1.0

#. Retrieve the dashboard login URL from the container logs:

   .. code-block:: bash

      docker logs aspire-dashboard

   Look for a line like ``Login to the dashboard at http://0.0.0.0:18888/login?t=...`` and open it in
   your browser.

#. Set the :envvar:`OTEL_EXPORTER_OTLP_ENDPOINT` environment variable to point to the container's
   OTLP receiver (port ``4318``):

   .. tab-set::

      .. tab-item:: Windows

         .. tab-set::

            .. tab-item:: PowerShell

               .. code-block:: powershell

                  $env:OTEL_EXPORTER_OTLP_ENDPOINT = 'http://localhost:4318'

            .. tab-item:: Command Prompt

               .. code-block:: batch

                  set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

      .. tab-item:: Linux/macOS

         .. code-block:: bash

            export OTEL_EXPORTER_OTLP_ENDPOINT='http://localhost:4318'

#. Start the solution.

   Telemetry data is now exported to the running Aspire container.

#. Browse the data on the dashboard.


Available metrics
=================

By default, the following metrics are available for collection in the ``GLOW API`` resource:

* ``http.server.duration``: Measures the duration of the inbound HTTP request.
* ``http.server.status_code``: Reports the status code of the API requests.

The FastAPI application is instrumented and provides access to the following built-in metrics in the ``FastAPI`` resource:

* ``http.server.active_requests``: Measures the number of concurrent HTTP requests that are currently in-flight.
* ``http.server.duration``: Measures the duration of the inbound HTTP request.
* ``http.server.request.size``: Measures the size of HTTP request messages (compressed).
* ``http.server.response.size``: Measures the size of HTTP response messages (compressed).
