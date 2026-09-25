.. _user_guide_frontend_dash_super_components_usage_logs_supervisor:

Logs Supervisor
################

``LogsSupervisor`` is a Dash All-in-One (AIO) component for parsing and displaying log files
generated with Python's ``logging`` module. It provides an interactive AG Grid table with filtering,
sorting, and real-time monitoring capabilities.

Key features:

- **Log parsing**: Parses log files using a user-specified format string.
- **Contextual feedback**: Displays no-rows messages for missing sources, empty logs, and parsing
  failures.
- **Level filtering**: Interactive buttons to filter by INFO, WARNING, ERROR, CRITICAL, and DEBUG.
- **Real-time monitoring**: Optional auto-updates to show new log entries as they are generated.
- **Interactive grid**: Sortable, filterable, and resizable AG Grid columns.
- **File/URL support**: Accepts local file paths or HTTP/HTTPS URLs as log sources.
- **Optional notifications**: Can emit persistent ``dmc`` notifications for parsing failures.
- **Persistent state**: Saves filter and column states across reloads.

.. image:: /_static/dash-media/logs_supervisor/example_output.png
   :alt: Logs Supervisor example output


Usage
=====

Configure the Dash application
------------------------------

``LogsSupervisor`` relies on custom JavaScript code to render log level badges in the
AG Grid table. Refer to the :ref:`ref_register_component_assets` section of the Getting
Started page for instructions on registering component assets. Specifically, you must:

1. Add the external script to your Dash app's ``external_scripts`` parameter
2. Call ``add_super_components_assets()`` to register the Flask endpoint that serves the
   JavaScript file

.. warning::

    Failing to include both the ``external_scripts`` entry and the
    ``add_super_components_assets()`` call results in the log level badges not rendering
    correctly in the grid. The custom no-rows renderer also requires these assets, so fallback
    no-rows feedback is affected as well. Core parsing and row rendering still work.


Basic usage
-----------

Import ``LogsSupervisor``:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_logs_supervisor.py
   :language: python
   :start-after: # [imports-start]
   :end-before: # [imports-end]

Add ``LogsSupervisor`` to the page layout with a local log file path and format string:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_logs_supervisor.py
   :language: python
   :start-after: # [basic-layout-start]
   :end-before: # [basic-layout-end]

Assuming the log file contains the following entries:

.. code-block:: text

    INFO - main - Application started
    WARNING - main - Low disk space
    ERROR - main - Unhandled exception occurred
    DEBUG - main - Debugging information

The component renders an AG Grid table with columns for ``levelname``, ``module``, and ``message``
and the following output is expected:

.. image:: /_static/dash-media/logs_supervisor/default_configuration.png
   :alt: Logs Supervisor default configuration
   :width: 85%

Real-time monitoring can be enabled by toggling the switch in the top-right corner of the component.
When enabled, the component polls the log file at regular intervals (default: every 3 seconds). To
activate monitoring from a callback, refer to the :ref:`ref_logs_supervisor_activate_monitoring`
section below.

.. warning::

    It is critical that the ``log_format`` parameter exactly matches the format string used in the
    logger's formatter. Mismatched formats result in no matching rows and a parsing-failed
    message in the grid.


Advanced usage
--------------

To customize the appearance of ``LogsSupervisor``, use the ``width`` and ``grid_props``
parameters. The update frequency can be controlled with the ``interval`` parameter.
The following example sets an update interval of 1 second, a custom container width, a fixed grid
height, and switches to the light AG Grid theme (``ag-theme-balham``):

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_logs_supervisor.py
   :language: python
   :start-after: # [advanced-layout-start]
   :end-before: # [advanced-layout-end]

The expected output is an AG Grid table with a fixed height of 600px, a width of 70%, and the
light ``ag-theme-balham`` theme:

.. image:: /_static/dash-media/logs_supervisor/custom_configuration.png
   :alt: Logs Supervisor custom configuration
   :width: 70%

In this advanced example, ``show_error_notifications=False`` disables popup notifications for
parsing failures while still showing contextual no-rows feedback in the grid.


Integration with SAF-based solutions
------------------------------------

The following example shows how to integrate ``LogsSupervisor`` in a SAF-based solution where
a GLOW transaction method generates a log file. Real-time monitoring is activated via a callback.

Generate a log file
~~~~~~~~~~~~~~~~~~~

The following example assumes that a log file is generated in a SAF-based solution in a GLOW
transaction method as follows:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/super_components_with_saf/src/ansys/solutions/super_components_with_saf/solution/my_step.py
   :language: python
   :start-after: # [generate-logs-start]
   :end-before: # [generate-logs-end]

.. note::

    This simple example generates random log messages for 30 seconds. In a real application, the
    log file would be generated by the actual application logic, and the component would monitor it
    in real time as new entries are added.

    Due to the way GLOW BDM file handles work, a new log file handle must be created and uploaded
    each time the log file is updated. This is because BDM file handles are immutable, so the same
    file handle cannot be updated with the new content, but a new handle must be created for each
    update.

    In the current example, the previous log file handles (and their associated files) are not
    deleted and are left to accumulate in storage until the transaction
    completes. In a production application, you would want to implement a cleanup mechanism to
    delete old log file handles and free up storage space. A full implementation
    of this cleanup mechanism can be found in the `showcase example
    <https://github.com/ansys/saf/blob/main/packages/dash-super-components/examples/showcase_all/src/ansys/solutions/showcase_dash_super_components/ui/pages/logs_supervisor_page.py>`_.


Add component to layout
~~~~~~~~~~~~~~~~~~~~~~~

Add ``LogsSupervisor`` to the page layout and pass the log file URL and custom grid height:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/super_components_with_saf/src/ansys/solutions/super_components_with_saf/ui/app.py
   :language: python
   :start-after: # [layout-logs-supervisor-start]
   :end-before: # [layout-logs-supervisor-end]

The expected output is an empty AG Grid table, ready to display log entries as they are generated
in the transaction method:

.. image:: /_static/dash-media/logs_supervisor/saf_logs_supervisor_empty.png
   :alt: Logs Supervisor empty state
   :width: 65%

.. _ref_logs_supervisor_activate_monitoring:

Activate monitoring
~~~~~~~~~~~~~~~~~~~

To automatically enable real-time monitoring when a log-generating method is triggered, set the
``data`` property of the ``activate_monitoring`` store to ``True`` (this code snippet assumes
that a button with ID
``generate-logs-basic-button`` triggers log generation):

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/super_components_with_saf/src/ansys/solutions/super_components_with_saf/ui/app.py
   :language: python
   :start-after: # [generate-logs-and-monitor-start]
   :end-before: # [generate-logs-and-monitor-end]

As the transaction method generates log entries, the component automatically updates to display new
logs in real time. The monitoring continues until turned off by setting the store ``data`` value
to ``False`` in a callback, or by toggling the switch in the component's UI:

.. image:: /_static/dash-media/logs_supervisor/saf_logs_supervisor_populated.png
   :alt: Logs Supervisor populated state
   :width: 75%


How it works
------------

1. **Initialization**: The component parses the log file using the provided format string
2. **Display**: Log entries are displayed in an AG Grid table with columns based on the format
   attributes
3. **Filtering**: Click the log level buttons (INFO, WARNING, ERROR, CRITICAL, DEBUG) to filter by
   level
4. **Monitoring**: Toggle the switch in the top-right corner to enable or turn off real-time updates
5. **Auto-update**: When monitoring is active, the component polls the log file at regular intervals
   (default: 3000 ms)
6. **Persistence**: Filter settings and column states are preserved across page reloads. When the
   component is re-initialized with a different log file or format, all filters except for the log
   level filters are cleared and the real-time monitoring is switched off.
7. **Feedback states**: The no-rows overlay message changes based on parse status:

   - ``No logs to display.`` when there are no rows after a successful parse
   - ``Log source is not available.`` when a local file or URL source is missing
   - ``Could not process log. Please check the log file path and format.`` for parse failures and
     non-matching formats


Filter logs
~~~~~~~~~~~

The log level buttons at the top of the component can be used to filter logs by severity:

- **INFO** (blue): Informational messages
- **WARNING** (orange): Warning messages
- **ERROR** (red): Error messages
- **CRITICAL** (pink): Critical error messages
- **DEBUG** (grape): Debug messages

Click a button to toggle that level on or off. Multiple levels can be active simultaneously.

Toggle monitoring
~~~~~~~~~~~~~~~~~

The switch located at the top right corner controls real-time monitoring:

- **ON** (blue checkmark): Component automatically updates the table at the specified interval
- **OFF** (gray X): Monitoring is paused; table displays the current snapshot

.. note::

    It is recommended to turn off monitoring when log generation has stopped to avoid unnecessary
    polling and API requests.


Properties
==========

Constructor parameters
----------------------

========================  ================================================================  ===========  =========
Parameter                 Description                                                       Type         Required
========================  ================================================================  ===========  =========
log_file                  Path or URL to the log file to be parsed. Supports local file     str or Path  Yes
                          paths (as ``str`` or ``Path`` objects) and HTTP/HTTPS URLs.
log_format                Format string of the log messages. Must exactly match the         str          Yes
                          formatter used in the logger.
                          See `the Python logging documentation
                          <https://docs.python.org/3/library/logging.html#logrecord-|
                          attributes>`_
                          for available format attributes.
aio_id                    The unique identifier for the component. If not provided, a UUID  str          No
                          is generated.
interval                  The interval in milliseconds for auto-updating the log messages   int          No
                          when monitoring is enabled. Default: ``3000`` (3 seconds).
width                     The width of the component container. Can be a CSS string (for    str or int   No
                          example, ``"70%"``, ``"800px"``) or an integer (treated as
                          pixels). Default: ``"100%"``.
grid_props                Dictionary containing properties for the AG Grid component.       dict         No
                          These properties are merged with defaults. See
                          `Dash AG Grid documentation
                          <https://dash.plotly.com/dash-ag-grid>`_ for available options.
show_error_notifications  Whether to show ``dmc`` error notifications when parsing fails.   bool         No
                          Default: ``True``.
========================  ================================================================  ===========  =========


.. _ref_logs_supervisor_log_format_attributes:

Supported log format attributes
-------------------------------

The ``log_format`` parameter supports the following Python logging format attributes:

=======================  ========================  =================================================
Attribute                Example Output            Description
=======================  ========================  =================================================
``%(asctime)s``          2024-01-15 10:30:45,123   Human-readable time when LogRecord was created
``%(created)f``          1705315845.123            Time when LogRecord was created (Unix timestamp)
``%(filename)s``         my_module.py              Filename portion of pathname
``%(funcName)s``         my_function               Name of function containing the logging call
``%(levelname)s``        INFO                      Text logging level for the message
``%(levelno)d``          20                        Numeric logging level for the message
``%(lineno)d``           42                        Source line number where logging call was issued
``%(message)s``          This is a log message     The logged message
``%(module)s``           my_module                 Module (name portion of filename)
``%(msecs)d``            123                       Millisecond portion of creation time
``%(name)s``             my_logger                 Name of the logger used to log the call
``%(pathname)s``         /path/to/my_module.py     Full pathname of source file
``%(process)d``          12345                     Process ID
``%(processName)s``      MainProcess               Process name
``%(relativeCreated)d``  1234                      Time in milliseconds since logger was created
``%(thread)d``           67890                     Thread ID
``%(threadName)s``       MainThread                Thread name
``%(taskName)s``         Task-1                    Task name (Python 3.12+)
=======================  ========================  =================================================

For complete details on format attributes, see the
`Python logging documentation <https://docs.python.org/3/library/logging.html#logrecord-attributes>`_.


Grid properties
---------------

The ``grid_props`` parameter accepts any valid Dash AG Grid properties. Default properties include:

.. code-block:: python

    {
        "rowData": [],  # Populated from parsed log file
        "columnDefs": [],  # Generated from log_format
        "defaultColDef": {
            "filter": True,
            "resizable": True,
            "sortable": True,
            "editable": False,
        },
        "filterModel": {},
        "dashGridOptions": {
            "noRowsOverlayComponent": "DMC_NoRows_Overlay",
            "noRowsOverlayComponentParams": {"message": "No logs to display."},
            "suppressMovableColumns": True,
            "tooltipShowDelay": 500,
            "suppressScrollOnNewData": True,
        },
        "className": "ag-theme-balham-dark",
        "persistence": True,
        "persisted_props": ["columnState"],
        "style": {"height": "200px"},
    }

User-provided properties are merged with these defaults.


Component IDs
-------------

The component exposes the following IDs for use in callbacks:

- ``LogsSupervisor.ids.info_button(aio_id)``: INFO level filter button
- ``LogsSupervisor.ids.warning_button(aio_id)``: WARNING level filter button
- ``LogsSupervisor.ids.error_button(aio_id)``: ERROR level filter button
- ``LogsSupervisor.ids.critical_button(aio_id)``: CRITICAL level filter button
- ``LogsSupervisor.ids.debug_button(aio_id)``: DEBUG level filter button
- ``LogsSupervisor.ids.activate_monitoring(aio_id)``: Store that controls when monitoring
  starts/stops (bool via ``data`` property)

Limitations
===========

- The ``log_format`` string must exactly match the format used in the logger's formatter, or parsing
  does not return matching rows.
- Real-time monitoring continues until manually turned off. It does not automatically stop when log
  generation completes.
- Only the format attributes listed in :ref:`ref_logs_supervisor_log_format_attributes` are
  supported. Custom format attributes raise a ``ValueError``.
- A ``dmc.NotificationContainer`` is required only when ``show_error_notifications=True`` and you
  want parse-failure notifications displayed.


Full example
============

For a complete working example check out the `showcase example
<https://github.com/ansys/saf/blob/main/packages/dash-super-components/examples/showcase_all/src/ansys/solutions/showcase_dash_super_components/ui/pages/logs_supervisor_page.py>`_.

The example shows:

- Triggering a long-running transaction that generates random log messages at multiple
  severity levels for 30 seconds
- A default supervisor using only the required constructor arguments with a 3-second polling
  interval and the dark AG Grid theme
- A customized supervisor with a 1-second polling interval, a fixed width, and the light
  AG Grid theme
- Both supervisors listening to the same log source and activating supervision via a shared
  callback
- Managing the trigger button loading state via callbacks and re-enabling it when the
  transaction terminates

For a minimal self-contained runnable example, see the
:ref:`sphx_glr_examples_dash_super_components_examples_general_example_logs_supervisor.py` page in the Examples gallery.


Source code
===========

For the full API reference of ``LogsSupervisor``, see
:class:`~ansys.solutions.dash_super_components.LogsSupervisor`.

Check out the `component source code <https://github.com/ansys/saf/blob/main/packages/dash-super-components/src/ansys/solutions/dash_super_components/logs_supervisor.py>`_
to discover the underlying logic. Contributions are welcomed. You can extend the component
functionalities by raising a pull request in the
`dash-super-components <https://github.com/ansys/saf/tree/main/packages/dash-super-components>`_ package.
