.. _saf-ex-long-transaction:

Long-running transaction streaming events
############################################

.. topic:: Objective

  Report the progress of a slow computation while it runs: execute it in a long-running
  transaction method, raise events from inside the method, and refresh a progress bar and a
  status label in the solution UI when those events reach the frontend.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-long-transaction-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

A **long-running transaction method** is a transaction method decorated with ``@long_running``. It
runs asynchronously, so the frontend stays responsive and other methods can execute while it is
still in progress. Instead of making the frontend poll the backend, such a method can **raise
events** as it goes. The frontend subscribes to those events with a WebSocket listener and reacts
as soon as they are pushed, which is what makes live progress reporting possible.

In this example, you learn how to:

- :material-outlined:`hourglass_top;1.25em;saf-objective-icon` Turn a slow computation into a
  **long-running transaction method** with the ``@long_running`` decorator.
- :material-outlined:`data_object;1.25em;saf-objective-icon` Track the progress in **typed step
  fields**, such as a counter and a status string.
- :material-outlined:`podcasts;1.25em;saf-objective-icon` Push progress updates to the frontend from
  inside the method with ``self.transaction.raise_event``.
- :material-outlined:`flag;1.25em;saf-objective-icon` Notify the frontend that the method has
  terminated with ``enable_termination_event=True``.
- :material-outlined:`hearing;1.25em;saf-objective-icon` Subscribe to both event streams from the
  frontend with ``DashClient.create_event_listener``.
- :material-outlined:`bolt;1.25em;saf-objective-icon` Wire **callbacks** that start the method and
  refresh the **progress bar**, the status label, and the button state on every event.

When you complete this example, you can expect the following output in the solution UI:

.. _saf-ex-long-transaction-output-1:

.. figure:: /_static/images/usage_saf_ex_long_transaction_output_1.png
  :width: 100%

  Progress bar before the transaction execution starts

.. figure:: /_static/images/usage_saf_ex_long_transaction_output_2.png
  :width: 100%

  Progress bar while transaction execution is in progress

.. figure:: /_static/images/usage_saf_ex_long_transaction_output_3.png
  :width: 100%

  Progress bar when transaction execution is complete


.. _saf-ex-long-transaction-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

The long-running transaction API and the event API are provided in the |glow-doc-ref|_ package, which is available by default in any SAF-based solution.
The progress bar used in this example comes from the `Dash Mantine Components <https://www.dash-mantine-components.com/components/progress>`_ library.


.. _saf-ex-long-transaction-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To stream the progress of a long-running transaction method to the solution UI, work through the following sequence of sections.


.. _saf-ex-long-transaction-backend:

:material-outlined:`dns;1.25em;sd-text-primary` Backend
---------------------------------------------------------

Create the solution definition.

.. key-concept:: Long-running transaction method

    A transaction method decorated with ``@long_running`` executes asynchronously. The frontend keeps
    responding to user actions, and the current status of the method can be queried at any time with
    ``step.get_long_running_method_state(<method_name>)``.

.. key-concept:: Transaction event

    Inside a transaction method, ``self.transaction.raise_event(message, stream_name=...)`` pushes an
    arbitrary JSON-serializable payload to the named event stream. Any frontend listening to that
    stream receives the payload immediately, so no polling is required.

.. key-concept:: Termination event

    Decorating a transaction method with ``@transaction(..., enable_termination_event=True)`` makes
    GLOW raise one final event when the method terminates, whether it succeeded or failed. The payload
    is a ``MethodState`` object, and the stream is named after the method, with underscores replaced by
    hyphens. For ``stream_updates``, the termination stream is therefore ``stream-updates``.

.. dropdown:: Define the step model
  :open:

  The step model for a simple step named ``FirstStep`` is defined in the ``first_step.py`` file.

  * The step manages the state of the long transaction, using the ``current_increment`` attribute to count from 0 to 50.

  * The ``number_of_increments`` attribute controls the actual number of increments to run, and the
    ``status`` string reflects when the latest increment was updated.

  * The only defined transaction uses a *for-loop* to increment the counter and the status string
    every second, and raises a progress event on every iteration.

  * The transaction enables the termination event, so the frontend is notified when the loop ends.

  .. code-block:: python
     :lineno-start: 6
     :caption: ``first_step.py``

         from ansys.saf.glow.solution import StepModel, StepSpec, transaction, long_running
         import time
         import datetime

         PROGRESS_STREAM_NAME = "long-transaction-progress"
         TERMINATION_STREAM_NAME = "stream-updates"


         class FirstStep(StepModel):
             """Definition of a simple step."""

             status: str = "[]"
             number_of_increments: int = 50
             current_increment: int = -1

             @long_running
             @transaction(
                 self=StepSpec(
                     download=["number_of_increments"],
                     upload=["status", "current_increment"],
                 ),
                 enable_termination_event=True,
             )
             def stream_updates(self) -> None:
                 for i in range(self.number_of_increments):
                     self.status = f"Update {i} at {_now()}"
                     self.current_increment = i
                     self.transaction.raise_event(
                         message={
                             "status": self.status,
                             "current_increment": self.current_increment,
                             "number_of_increments": self.number_of_increments,
                         },
                         stream_name=PROGRESS_STREAM_NAME,
                     )
                     time.sleep(1)
                 self.status = f"Last updated at {_now()}"


         def _now():
             return datetime.datetime.now().strftime("%H:%M:%S")


.. _saf-ex-long-transaction-frontend:

:material-outlined:`web;1.25em;sd-text-primary` Frontend
----------------------------------------------------------

Expose the solution definition in the UI.

.. dropdown:: Define the step layout
  :open:

  The user interface has two widgets: a button that starts the transaction and a progress bar, with
  the completion percentage displayed next to it. The user is also kept informed with a ``dmc``
  notification, which is updated on every event pushed by the backend.

  .. code-block:: python
      :lineno-start: 6
      :caption: layout from ``first_page.py``

      import json

      from ansys.saf.glow.client import DashClient, callback
      from ansys.saf.glow.solution import MethodState, MethodStatus
      from dash_extensions.enrich import Input, Output, State, ctx, html, no_update
      import dash_mantine_components as dmc

      from ansys.solutions.abc.solution.definition import AbcSolution
      from ansys.solutions.abc.solution.first_step import PROGRESS_STREAM_NAME, TERMINATION_STREAM_NAME

      NOTIFICATION_ID = "long-transaction-notification"


      def layout(project: AbcSolution):
          step = project.steps.first_step
          is_running = step.get_long_running_method_state("stream_updates").status == MethodStatus.Running
          progress = _to_percentage(step.current_increment + 1 if is_running else 0, step.number_of_increments)

          return html.Div(
              [
                  html.H1("Long Transaction Streaming Update Example"),
                  html.P(),
                  dmc.Button("Run test", id="run-button", n_clicks=0, disabled=is_running, loading=is_running),
                  dmc.Group(
                      [
                          dmc.Progress(
                              id="completion-progress",
                              value=progress,
                              animated=is_running,
                              style={"flex": 1},
                          ),
                          dmc.Text(f"{progress}%", id="completion-progress-label", w=50, ta="right", fw=500),
                      ],
                      gap="sm",
                      wrap="nowrap",
                      align="center",
                  ),
              ]
          )


      def _to_percentage(completed_increments: int, number_of_increments: int) -> int:
          if number_of_increments <= 0:
              return 0
          return int((completed_increments * 100) / number_of_increments)

.. dropdown:: Mount the event listeners
  :open:

  * Event listeners are invisible WebSocket components that trigger callbacks when the backend
    pushes an event.
  * **The lifetime of a listener must match the lifetime of the components its callbacks write
    to.** A Dash callback is dispatched with all of its inputs and outputs, so if an event arrives
    while one of them is not in the layout, the renderer raises a *"nonexistent object was used in
    an Input/Output"* error.
  * This example therefore uses two sets of listeners: an application scoped set, mounted into
    ``html.Div(id="long-transaction-event-listeners-container")`` declared in the global layout,
    which only drives the notification; and a page scoped set, declared in the page layout, which
    drives the button and the progress bar.
  * Nothing is lost when the user leaves the page: the notification keeps following the
    transaction, and ``layout`` rebuilds the button and the progress bar from the step fields when
    the user comes back.

  .. code-block:: python
      :lineno-start: 45
      :caption: page scoped listeners from ``first_page.py``

      # Inside layout(), next to the widgets they drive.
      html.Div(
          [
              DashClient.create_event_listener(
                  step, id="long-transaction-page-progress-listener", stream_name=PROGRESS_STREAM_NAME
              ),
              DashClient.create_event_listener(
                  step, id="long-transaction-page-termination-listener", stream_name=TERMINATION_STREAM_NAME
              ),
          ]
      )

  .. code-block:: python
      :lineno-start: 60
      :caption: application scoped listeners from ``first_page.py``

      @callback(
          Output("long-transaction-event-listeners-container", "children"),
          Input("url", "pathname"),
      )
      def mount_event_listeners(project: AbcSolution):
          step = project.steps.first_step
          return [
              DashClient.create_event_listener(
                  step, id="long-transaction-progress-listener", stream_name=PROGRESS_STREAM_NAME
              ),
              DashClient.create_event_listener(
                  step, id="long-transaction-termination-listener", stream_name=TERMINATION_STREAM_NAME
              ),
          ]

.. key-concept:: Event listener

    ``DashClient.create_event_listener(step, id=..., stream_name=...)`` returns a WebSocket component
    connected to the given event stream of the step. Its ``message`` property is a dictionary whose
    ``data`` key holds the JSON-encoded payload raised by the backend, so it can be used as the
    ``Input`` of any callback. Several listeners may subscribe to the same stream: each one gets its
    own event queue on the server.

.. key-concept:: Callback

    A **callback** is a Dash-decorated function that fires in response to a UI event. In a SAF
    solution, callbacks reach the backend through ``project.steps.<step_name>``, read or write
    fields, and invoke transaction methods. No manual HTTP calls are needed.

.. dropdown:: Define the transaction start button
  :open:

  * The callback starting the long transaction resets the data in the step.
  * It also shows a persistent loading notification so the user knows the transaction is running.
  * To extend this example, you could add an input indicating the number of increments
    to be run.
  * This data can be set as it is downloaded in the corresponding transaction.

  .. code-block:: python
      :lineno-start: 61
      :caption: transaction start button callback from ``first_page.py``

      @callback(
          Output("notification-container", "sendNotifications", allow_duplicate=True),
          Input("run-button", "n_clicks"),
          State("url", "pathname"),
          prevent_initial_call=True,
      )
      def start_long_running_transaction(n_clicks, project: AbcSolution):
          notification = no_update

          if ctx.triggered_id == "run-button" and n_clicks:
              step = project.steps.first_step
              step.current_increment = -1
              step.stream_updates()

              notification = [
                  dict(
                      title="Info",
                      id=NOTIFICATION_ID,
                      action="show",
                      message="Streaming updates from the long running transaction...",
                      autoClose=False,
                      loading=True,
                      color="blue",
                      withCloseButton=False,
                  )
              ]

          return notification

.. key-concept:: Notification

    ``dmc.NotificationContainer`` is declared once in the global application layout with the
    ``notification-container`` identifier. Callbacks write to its ``sendNotifications`` property to
    show (``action="show"``) or refresh (``action="update"``) a notification identified by its
    ``id``, which makes it easy to keep a single notification alive for the whole duration of a
    long-running transaction.

.. dropdown:: Synchronize the notification with the transaction lifecycle
  :open:

  * This callback is driven by the **application scoped** listeners, so it only writes to
    ``notification-container``, which belongs to the global layout and is therefore always present.
  * Progress events refresh the in-progress notification with the latest status; the termination
    event replaces it with a success or failure message built from the ``MethodState`` payload.
  * As a result the user keeps following the transaction from any page of the solution.

  .. code-block:: python
      :lineno-start: 118
      :caption: notification synchronization callback from ``first_page.py``

      @callback(
          Output("notification-container", "sendNotifications", allow_duplicate=True),
          Input("long-transaction-progress-listener", "message"),
          Input("long-transaction-termination-listener", "message"),
          prevent_initial_call=True,
      )
      def sync_notifications(progress_message, termination_message):
          notification = no_update

          if ctx.triggered_id == "long-transaction-progress-listener" and progress_message:
              update = json.loads(progress_message["data"])
              progress = _to_percentage(update["current_increment"] + 1, update["number_of_increments"])
              notification = [
                  dict(
                      title="Info",
                      id=NOTIFICATION_ID,
                      action="update",
                      message=f"{update['status']} ({progress}%)",
                      autoClose=False,
                      loading=True,
                      color="blue",
                      withCloseButton=False,
                  )
              ]
          elif ctx.triggered_id == "long-transaction-termination-listener" and termination_message:
              method_state = MethodState.model_validate_json(termination_message["data"])
              succeeded = method_state.status == MethodStatus.Completed
              notification = [
                  dict(
                      title="Success" if succeeded else "Error",
                      id=NOTIFICATION_ID,
                      action="update",
                      message=(
                          "Successfully ran stream_updates."
                          if succeeded
                          else "Failed to run stream_updates. Please check the logs."
                      ),
                      color="green" if succeeded else "red",
                      autoClose=5000 if succeeded else False,
                      withCloseButton=True,
                      loading=False,
                  )
              ]

          return notification

.. dropdown:: Synchronize the controls with the transaction lifecycle
  :open:

  * This callback is driven by the **page scoped** listeners, so every one of its inputs and
    outputs belongs to the page layout and it can never be triggered while its components are
    unmounted.
  * It reacts to three inputs, dispatched on ``ctx.triggered_id``: the click on the button, which
    disables it and starts the animated progress bar; a progress event, which advances the progress
    bar and refreshes the percentage label; and the termination event, which re-enables the button
    and completes the bar.
  * The progress stream and the termination stream are independent, so their events are not ordered
    relative to each other. The ``disabled`` state of the button is read back as a ``State`` and used
    to discard progress events that arrive after the transaction has ended.
  * Progress events carry everything the frontend needs, so no round trip to the backend is
    required. Every output that must not change is left to ``no_update``.

  .. code-block:: python
      :lineno-start: 176
      :caption: controls synchronization callback from ``first_page.py``

      @callback(
          Output("run-button", "disabled", allow_duplicate=True),
          Output("run-button", "loading", allow_duplicate=True),
          Output("completion-progress", "animated", allow_duplicate=True),
          Output("completion-progress", "value", allow_duplicate=True),
          Output("completion-progress-label", "children", allow_duplicate=True),
          Input("run-button", "n_clicks"),
          Input("long-transaction-page-progress-listener", "message"),
          Input("long-transaction-page-termination-listener", "message"),
          State("run-button", "disabled"),
          prevent_initial_call=True,
      )
      def sync_controls(n_clicks, progress_message, termination_message, is_running):
          disable_run_button, loading_run_button = no_update, no_update
          animated, progress, progress_label = no_update, no_update, no_update

          if ctx.triggered_id == "run-button" and n_clicks:
              disable_run_button, loading_run_button = True, True
              animated, progress, progress_label = True, 0, "0%"
          elif ctx.triggered_id == "long-transaction-page-progress-listener" and progress_message and is_running:
              update = json.loads(progress_message["data"])
              progress = _to_percentage(update["current_increment"] + 1, update["number_of_increments"])
              progress_label = f"{progress}%"
          elif ctx.triggered_id == "long-transaction-page-termination-listener" and termination_message:
              method_state = MethodState.model_validate_json(termination_message["data"])
              disable_run_button, loading_run_button = False, False
              animated = False
              if method_state.status == MethodStatus.Completed:
                  progress, progress_label = 100, "100%"

          return disable_run_button, loading_run_button, animated, progress, progress_label

  Now that your implementation is complete, continue to the :ref:`saf-ex-long-transaction-testing` section.


.. _saf-ex-long-transaction-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-long-transaction-feature-highlight>` section.
