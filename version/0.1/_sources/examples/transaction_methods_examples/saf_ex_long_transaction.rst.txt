.. _saf-ex-long-transaction:


Long-running transaction streaming uploads
############################################

.. _saf-ex-long-transaction-summary:

.. topic:: Objective

  Use a long-running transaction to upload data as the transaction executes, coupled with page monitoring and progress display.

  Source code for this example is in the `solution-examples <https://github.com/ansys/solution-examples>`_ repository.

  .. _saf-ex-long-running-trans-objective:

:material-outlined:`ads_click;1.25em;sd-text-primary` Objective
==================================================================
A "long-running transaction" is a transaction method annotated with ``@long_running decorator``. This causes the transaction method to run asynchronously, allowing other methods to run while its own execution is still in progress.

This example shows how to upload data a the transaction executes and add widgets to the solution user interface: a button, a progress bar, a status label, and a timer that triggers a callback every second when active.


.. list-table:: **Long transaction streaming upload**
   :widths: 20 80
   :header-rows: 1

   * - Component
     - Description
   * - Step model
     - * Long-transaction counting from 0 to 50
       * Upload of the count to the solution
   * - User interface
     - * Button to start the long transaction
       * Progress bar showing long transaction progress
       * Status label to show the transaction status

.. figure:: /_static/images/usage_saf_ex_long_transaction_output_1.png
  :width: 100%

  Progress bar before the transaction execution starts

.. figure:: /_static/images/usage_saf_ex_long_transaction_output_2.png
  :width: 100%

  Progress bar while transaction execution is in progress

.. figure:: /_static/images/usage_saf_ex_long_transaction_output_3.png
  :width: 100%

  Progress bar when transaction execution is complete

.. _saf-ex-long-transaction-solution:

:octicon:`code-square;1em;sd-text-primary` Solution
======================================================

To add functionality and user interface elements to a long-running transaction, work through the following sequence of tabs.

.. tab-set::

  .. tab-item:: 1️⃣Backend
    :name: saf-ex-long-transaction-backend-tab

    Define the step model.

    .. dropdown:: Define the step model
     :open:

     The step model for a simple step named ``FirstStep`` is defined in the ``first_step.py`` file.

     * The step manages the state of the long transaction, using the ``current_increment`` attribute to count from 0 to 50.

     * The other attributes manage the actual number of increments to run:

       * A status string reflects when the latest increment was updated.
       * A Boolean attribute indicates whether the long transaction is running.

     * The only defined transaction uses a *for-loop* to increment the counter and the status string
       every second.

     .. code-block:: python
        :lineno-start: 6
        :caption: ``first_step.py``

            from ansys.saf.glow.solution import StepModel, StepSpec, transaction, long_running
            import time
            import datetime


            class FirstStep(StepModel):
                """Definition of a simple step."""

                status: str = "[]"
                processing: bool = False
                number_of_increments: int = 50
                current_increment: int = -1

                @long_running
                @transaction(
                    self=StepSpec(
                        download=["processing", "number_of_increments"],
                        upload=["status", "current_increment"],
                    )
                )
                def stream_updates(self) -> None:
                    for i in range(self.number_of_increments):
                        self.status = f"Update {i} at  {_now()}"
                        self.current_increment = i
                        self.transaction.upload(["status", "current_increment"])
                        time.sleep(1)
                        self.status = f"Last updated at {_now()}"


            def _now():
                return datetime.datetime.now().strftime("%H:%M:%S")


  .. tab-item:: 2️⃣Frontend
    :name: saf-ex-long-transaction-frontend-tab

    Define the user interface.

    .. dropdown:: Define the step layout
      :open:

      The user interface has three main widgets: a button, a progress bar, and a status label.
      A fourth element triggers a callback every second while active.

      .. code-block:: python
          :lineno-start: 6
          :caption: layout from ``first_page.py``

          from ansys.saf.glow.client import DashClient, callback
          from dash_extensions.enrich import Input, Output, State, dcc, html
          from ansys.saf.glow.solution import MethodStatus
          import dash_bootstrap_components as dbc
          from dash.exceptions import PreventUpdate

          from ansys.solutions.abc.solution.definition import AbcSolution
          from ansys.solutions.abc.solution.first_step import FirstStep


          def layout(step: FirstStep):
              return html.Div(
                  [
                      html.H1("Long Transaction Streaming Update Example"),
                      html.P(),
                      html.Button("Run test", id="run-button", n_clicks=0),
                      html.Div(
                          [
                              dbc.Progress(
                                  id="completion-progress", className="mb-3", value=0, label="", max=step.number_of_increments
                              )
                          ]
                      ),
                      html.Div(id="status-line", children=["nothing"]),
                      dcc.Interval(id="interval-refresh", interval=1 * 1000, n_intervals=0, disabled=True),  # in milliseconds
                  ]
              )

    .. dropdown:: Define the timer callback
      :open:

      * When the :guilabel:`Run` test button is clicked, the timer callback is activated
        and called every second.
      * The callback uses the data from the step to update the status string and the progress bar.
      * When the processing is finished, it reactivates the :guilabel:`Run` test button and
        deactivates the timer.


      .. code-block:: python
          :lineno-start: 53
          :caption: timer callback from ``first_page.py``

          @callback(
              Output("status-line", "children"),
              Output("run-button", "disabled"),
              Output("interval-refresh", "disabled"),
              Output("completion-progress", "value"),
              Output("completion-progress", "label"),
              Input("interval-refresh", "n_intervals"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def update_status(_, pathname):
              project = DashClient[AbcSolution].get_project(pathname)
              step = project.steps.first_step
              if not step.processing:
                  raise PreventUpdate
              else:
                  number_of_completed_increments = step.current_increment + 1
                  progress = int((number_of_completed_increments * 100) / step.number_of_increments)
                  if step.get_long_running_method_state("stream_updates").status == MethodStatus.Running:
                      status = "running"
                  else:
                      status = "done"
                      step.processing = False
                  return (
                      f"{step.status} {status}",
                      step.processing,
                      not step.processing,
                      number_of_completed_increments,
                      f"{progress}%",
                  )

    .. dropdown:: Define the transaction start button
      :open:

      * The callback starting the long transaction resets the data in the step.
      * To extend this example, you could add an input indicating the number of increments
        to be run.
      * This data can be set as it is downloaded in the corresponding transaction.

      .. code-block:: python
          :lineno-start: 33
          :caption: transaction start button callback from ``first_page.py``

          @callback(
              Output("status-line", "children"),
              Output("run-button", "disabled"),
              Output("interval-refresh", "disabled"),
              Output("completion-progress", "value"),
              Output("completion-progress", "label"),
              Input("run-button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def start_long_running_transaction(n_clicks, pathname):
              if n_clicks <= 0:
                  raise PreventUpdate
              project = DashClient[AbcSolution].get_project(pathname)
              step = project.steps.first_step
              step.processing = True
              step.current_increment = -1
              step.stream_updates()
              return "running", True, False, 0, ""
