.. _saf-ex-process-logs-events:

Streaming process logs
######################

.. topic:: Objective

  Stream log output to the solution UI while it is being produced: write the log lines from a
  long-running transaction method, raise an event for each new line, and let the frontend append
  them to a log panel in real time instead of waiting for the transaction to finish.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-process-logs-events-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

A transaction method that takes minutes to complete leaves the user with no feedback until it
returns. Combining a **long-running transaction method** with **SAF GLOW events** turns that silence
into a live stream: the backend pushes each new log line as soon as it is produced, and the frontend
displays it without polling or refreshing the page.

In this example, you learn how to:

- :material-outlined:`hourglass_top;1.25em;saf-objective-icon` Write the log file from a
  **long-running transaction method** so the UI stays responsive.
- :material-outlined:`data_object;1.25em;saf-objective-icon` Persist the accumulated log content in
  an **entity handle field** so it survives a page reload.
- :material-outlined:`stream;1.25em;saf-objective-icon` Push every new line to the frontend on a
  custom **event stream** with ``transaction.raise_event``.
- :material-outlined:`sensors;1.25em;saf-objective-icon` Emit a **termination event** when the
  transaction method completes or fails.
- :material-outlined:`bolt;1.25em;saf-objective-icon` Wire **callbacks** and **event listeners**
  that append the streamed lines, refresh the controls, and clear the panel.


.. _saf-ex-process-logs-events-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

The long-running transaction and events APIs are provided in the |glow-doc-ref|_ package, which is available by default in any SAF-based solution.


.. _saf-ex-process-logs-events-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To stream process logs from the backend to the solution UI, work through the following sequence of sections.


.. _saf-ex-process-logs-events-backend:

:material-outlined:`dns;1.25em;sd-text-primary` Backend
---------------------------------------------------------

Create the solution definition.

.. key-concept:: Entity handle field

    An ``EntityHandle`` field references a blob managed by BDM. It is the way a step persists a file
    it produces, so that the frontend can read the content back on any subsequent page render.

.. _saf-ex-process-logs-events-backend-code-model:

.. dropdown:: Declare the log file field
  :open:

  The ``log_file`` field on the step model persists the accumulated log content.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/basic_step.py
    :language: python
    :caption: solution/basic_step.py
    :start-at: log_file: EntityHandle = NO_ENTITY
    :end-at: log_file: EntityHandle = NO_ENTITY

  The ``log_file`` field is an ``EntityHandle`` that references the log file content stored via BDM. It defaults to ``NO_ENTITY``
  until the first log line is written.

.. key-concept:: Long-running transaction method

    A transaction method decorated with ``@long_running`` executes asynchronously. The UI stays
    responsive while it runs, and a **termination event** is raised on the stream named after the
    method when ``enable_termination_event=True`` is set on the ``@transaction`` decorator.

.. key-concept:: Event stream

    An **event stream** is a named channel between the backend and the frontend. The backend pushes
    messages on it with ``self.transaction.raise_event(message, stream_name=...)``, and the frontend
    subscribes to it with an event listener component.

.. _saf-ex-process-logs-events-backend-code-transaction:

.. dropdown:: Stream the log lines from a long-running transaction method
  :open:

  The ``generate_process_logs`` transaction method writes the log file and streams each new line as
  it is produced. The ``clear_logs`` transaction method discards the persisted content.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/basic_step.py
    :language: python
    :caption: solution/basic_step.py
    :pyobject: BasicStep.generate_process_logs

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/basic_step.py
    :language: python
    :caption: solution/basic_step.py
    :pyobject: BasicStep.clear_logs

  The ``generate_process_logs`` method is marked ``@long_running`` so it executes asynchronously, allowing the UI to remain
  responsive while it runs. The ``transaction`` decorator sets ``enable_termination_event=True`` so that a termination event is
  automatically raised on the stream named after the method, ``generate-process-logs``, when the method completes or fails.

  On each iteration the method:

  - appends a new timestamped line to the in-memory log content;
  - persists the updated content by re-uploading it to storage via ``store_stream`` and assigning the resulting ``EntityHandle``
    to ``self.log_file``;
  - raises an event carrying only the new line (not the whole log) on the custom ``generate-process-logs-update`` stream, so
    that listeners can append it directly to what is already displayed.

  The ``clear_logs`` transaction simply resets ``log_file`` to ``NO_ENTITY``, discarding the previously stored content.

  See

  - :ref:`Mount the event listeners <saf-ex-process-logs-events-frontend-code-listeners>` for how the UI subscribes to both streams;
  - :ref:`Append the streamed logs to the panel <saf-ex-process-logs-events-frontend-code-update>` for the callback that appends streamed lines to the log panel; and
  - :ref:`React to the termination event <saf-ex-process-logs-events-frontend-code-termination>` for the callback that reacts to the termination event.


.. _saf-ex-process-logs-events-frontend:

:material-outlined:`web;1.25em;sd-text-primary` Frontend
----------------------------------------------------------

Expose the solution definition in the UI.

.. _saf-ex-process-logs-events-frontend-code-layout:

.. dropdown:: Build the layout
  :open:

  The ``layout`` function renders the :guilabel:`Start` button and the scrollable log panel.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/process_logs_page.py
    :language: python
    :caption: ui/pages/basic/process_logs_page.py
    :start-at: NO_LOGS_MESSAGE = "No logs are available yet."
    :end-at: NO_LOGS_MESSAGE = "No logs are available yet."

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/process_logs_page.py
    :language: python
    :caption: ui/pages/basic/process_logs_page.py
    :pyobject: layout

  The log text is rendered inside a stable ``html.Pre`` element identified by ``id="log_content"``. Keeping the log text as a
  single string on a fixed component (rather than rebuilding the whole ``log_container`` tree on every update) makes it possible
  for later callbacks to update the displayed logs with a simple string concatenation. The initial content is populated from
  the persisted log file, if any, via :ref:`Restore the log panel on page load <saf-ex-process-logs-events-frontend-code-initial-text>`.

.. key-concept:: Event listener

    An **event listener** is a frontend component that subscribes to a backend event stream. It fires
    a callback every time a message is raised on that stream, which removes the need to poll the
    backend for progress.

.. _saf-ex-process-logs-events-frontend-code-listeners:

.. dropdown:: Mount the event listeners
  :open:

  The ``mount_event_listeners`` callback subscribes the page to the two backend streams.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/process_logs_page.py
    :language: python
    :caption: ui/pages/basic/process_logs_page.py
    :pyobject: mount_event_listeners

  Two listeners are created: ``generate-process-logs-update-listener`` receives every new log line raised on the
  ``generate-process-logs-update`` stream while the transaction is running, and ``generate-process-logs-termination-listener``
  receives the termination event automatically raised on the ``generate-process-logs`` stream (named after the transaction
  method) when the transaction completes or fails.

.. key-concept:: Callback

    A **callback** is a Dash-decorated function that fires in response to a UI event. In a SAF
    solution, callbacks reach the backend through ``project.steps.<step_name>``, read or write
    fields, and invoke transaction methods — no manual HTTP calls needed.

.. _saf-ex-process-logs-events-frontend-code-start:

.. dropdown:: Start the transaction method from the frontend
  :open:

  The ``start_generate_process_logs_transaction`` callback starts the ``generate_process_logs``
  transaction method.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/process_logs_page.py
    :language: python
    :caption: ui/pages/basic/process_logs_page.py
    :pyobject: start_generate_process_logs_transaction

  Clicking the :guilabel:`Start` button calls ``step.generate_process_logs(wait_time=10.0)``, which starts the long-running transaction
  asynchronously, and immediately shows a persistent, loading notification so the user knows the process is underway.

.. _saf-ex-process-logs-events-frontend-code-update:

.. dropdown:: Append the streamed logs to the panel
  :open:

  The ``update_logs_on_backend_events`` callback appends each streamed log line to the log panel.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/process_logs_page.py
    :language: python
    :caption: ui/pages/basic/process_logs_page.py
    :pyobject: update_logs_on_backend_events

  Each event message payload is JSON-encoded, so it must be decoded with ``json.loads`` before being used; otherwise the raw
  JSON text (including surrounding quotes and escaped ``\n`` sequences) would be displayed instead of an actual line break.
  If the log panel currently only shows the placeholder text, the new line replaces it rather than being appended, so the
  placeholder disappears as soon as the first log line arrives. Because the ``log_content`` element uses ``whiteSpace:
  pre-wrap``, the ``\n`` terminating each log line causes it to be displayed on its own row.

.. _saf-ex-process-logs-events-frontend-code-termination:

.. dropdown:: React to the termination event
  :open:

  The ``sync_controls`` and ``sync_notifications`` callbacks react to the transaction method's
  termination event.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/process_logs_page.py
    :language: python
    :caption: ui/pages/basic/process_logs_page.py
    :pyobject: sync_controls

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/process_logs_page.py
    :language: python
    :caption: ui/pages/basic/process_logs_page.py
    :pyobject: sync_notifications

  ``sync_controls`` disables the :guilabel:`Start` button and shows a loading spinner as soon as it is clicked, then re-enables it once the
  termination event is received. ``sync_notifications`` parses the termination event payload into a ``MethodState`` and uses the
  shared ``handle_method_event`` helper to replace the in-progress notification with a success or failure message.

.. _saf-ex-process-logs-events-frontend-code-clear:

.. dropdown:: Clear the logs
  :open:

  The ``clear_process_logs`` callback is triggered by the :guilabel:`Clear Logs` icon button.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/process_logs_page.py
    :language: python
    :caption: ui/pages/basic/process_logs_page.py
    :pyobject: clear_process_logs

  This callback calls the ``clear_logs`` transaction to discard the persisted log file, and resets the ``log_content`` text back
  to the placeholder message.

.. _saf-ex-process-logs-events-frontend-code-initial-text:

.. dropdown:: Restore the log panel on page load
  :open:

  The ``get_process_logs_text`` helper reads the persisted log file to populate the log panel when
  the page is first rendered.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/process_logs_page.py
    :language: python
    :caption: ui/pages/basic/process_logs_page.py
    :pyobject: get_process_logs_text

  This ensures that navigating back to the page after logs have already been generated shows the previously accumulated content,
  rather than starting from the placeholder message.

  Now that your implementation is complete, continue to the :ref:`saf-ex-process-logs-events-testing` section.


.. _saf-ex-process-logs-events-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-process-logs-events-feature-highlight>` section.
