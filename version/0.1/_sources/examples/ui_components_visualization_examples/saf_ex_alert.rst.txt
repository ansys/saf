.. _saf-ex-alert:

Alerts
###########################

.. _saf-ex-alert-summary:

.. topic:: Objective

  Use Dash alerts to display important messages to users.

  Source code for this example is in the `solution-examples <https://github.com/ansys/solution-examples>`_ repository.



.. _saf-ex-alert-objective:

:material-outlined:`ads_click;1.25em;sd-text-primary` Objective
==================================================================

When the user triggers a process (either server-side or client-side), it is important to provide feedback on the status of the process. Alerts are a great way to display important messages to users. This example shows how to use Dash alerts to display message in your solution.

When you complete this example, you can expect the following output in the solution UI:

.. _-saf-ex-alert-output-1:

.. figure:: /_static/images/usage_saf_ex_alert_output_1.png
  :width: 100%

  Alert displayed when the process completes

.. _-saf-ex-alert-output-2:

.. figure:: /_static/images/output_fail.png
  :width: 100%

  Alert displayed when the process fails


.. _saf-ex-alert-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

For this example, you need the ``Alert`` component from the `Dash Mantine Components <https://www.dash-mantine-components.com/>`_ library.

.. note::
    You may also try out the `Alert <https://dash-bootstrap-components.opensource.faculty.ai/docs/components/alert/>`_ component available in the **Dash Bootstrap Components** library.



.. _saf-ex-alert-solution:

:octicon:`code-square;1em;sd-text-primary` Solution
======================================================

To display an alert when a process completes, work through the following sequence of tabs.

.. tab-set::

  .. tab-item:: 1️⃣Backend
    :name: saf-ex-alert-backend-tab

    Create the solution definition.

    .. dropdown:: Define the step model
      :name: saf-ex-alert-backend-drop-1
      :open:

      First, create a ``StepModel`` class named ``AlertStep`` with the following three fields:

      * ``wait_time``: a float value that represents the time to wait
      * ``completed``: a Boolean value that indicates whether the process is completed
      * ``force_failure``: a Boolean value that indicates whether the process should
        complete or fail.

      Next, you need a transaction method that mocks a process which takes some time to complete. Create a ``process`` transaction method that waits for a specified amount of time.

      .. code-block:: python
        :caption: <solution/alert_step.py>

          import time

          from ansys.saf.glow.solution import StepModel, StepSpec, long_running, transaction


          class AlertStep(StepModel):
              """Definition of the alert step."""

              wait_time: float = 3.0
              completed: bool = False
              force_failure: bool = False

              @transaction(self=StepSpec(upload=["completed"], download=["wait_time", "force_failure"]))
              @long_running
              def process(self) -> None:
                  """Wait for some time."""
                  start_time = time.time()
                  while (time.time() - start_time) < self.wait_time:
                      time.sleep(0.5)
                  if self.force_failure:
                      raise Exception("Error occurred.")
                  self.completed = True


  .. tab-item:: 2️⃣Frontend
    :name: saf-ex-alert-frontend-tab

    Create two buttons to trigger the ``process`` transaction method: one button to complete the process, and and button to force the process to fail. Below the buttons, display an alert to show the process status.

    .. dropdown:: Create the page layout with the alert component
      :open:

      Create the page layout for the alert page.

      .. code-block:: python
        :caption: ui/pages/alert_page.py

          import time

          from ansys.saf.glow.client import DashClient, callback
          from ansys.saf.glow.solution import MethodStatus
          from dash_extensions.enrich import Input, Output, State, ctx, html
          from dash_iconify import DashIconify
          import dash_mantine_components as dmc

          from ansys.solutions.examples.solution.basic.alert_step import AlertStep
          from ansys.solutions.examples.solution.definition import ExamplesSolution


          def layout(step: AlertStep):
              """Layout of the alert example page."""
              return html.Div(
                  [
                      html.Br(),
                      html.H1("Alert", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
                      html.Br(),
                      html.P(
                          "Use an alert to display messages in a solution UI.",
                          className="lead",
                          style={"font-size": "20px"},
                      ),
                      html.Br(),
                      html.Hr(className="my-2"),
                      html.Br(),
                      html.Div(
                          html.Div(
                              [
                                  dmc.Button(
                                      "Run method with success",
                                      id="trigger_run_with_success",
                                      leftIcon=DashIconify(icon="streamline:startup-solid"),
                                      color="lime",
                                      radius="xl",
                                      disabled=False,
                                      className="mantine-button",
                                      style={"width": "50%", "font-size": "14px"},
                                  ),
                                  dmc.Button(
                                      "Run method with failure",
                                      id="trigger_run_with_failure",
                                      leftIcon=DashIconify(icon="streamline:startup-solid"),
                                      color="red",
                                      radius="xl",
                                      disabled=False,
                                      className="mantine-button",
                                      style={"width": "50%", "font-size": "14px"},
                                  ),
                              ],
                              style={"display": "flex", "justify-content": "center"},
                          ),
                          style={
                              "width": "50%",
                              "display": "inline-block",
                              "justify-content": "center",
                              "align-items": "center",
                              "margin-left": "25%",
                          },
                      ),
                      html.Br(),
                      html.Br(),
                      html.Div(
                          dmc.Alert(
                              id="alert",
                          ),
                          style={
                              "textAlign": "center",
                              "margin-left": "25%",
                              "width": "50%",
                          },
                      ),
                  ]
              )

    .. dropdown:: Connect the button to the transaction method
      :name: saf-ex-alert-frontend-drop-4
      :open:

      Whenever a button is clicked, the ``process`` transaction method should be triggered.
      For this, create a callback function to call the transaction method and update the alert component accordingly.

      .. code-block:: python
        :caption: ui/pages/alert_page.py

          @callback(
              Output("alert", "title"),
              Output("alert", "children"),
              Output("alert", "color"),
              Input("trigger_run_with_success", "n_clicks"),
              Input("trigger_run_with_failure", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def run_method(trigger_run_with_success, trigger_run_with_failure, pathname):
              """Trigger the computation."""
              project = DashClient[ExamplesSolution].get_project(pathname)
              step = project.steps.alert_step
              if ctx.triggered_id == "trigger_run_with_success" and trigger_run_with_success:
                  step.force_failure = False
              if ctx.triggered_id == "trigger_run_with_failure" and trigger_run_with_failure:
                  step.force_failure = True
              step.process()
              method_status = step.get_method_state("process").status
              while method_status == MethodStatus.Running:
                  method_status = step.get_method_state("process").status
                  time.sleep(0.1)
              if method_status == MethodStatus.Completed:
                  title = "Info"
                  message = "Method completed successfully."
                  color = "lime"
              elif method_status == MethodStatus.Failed:
                  title = "Error"
                  message = "Method failed."
                  color = "red"
              return title, message, color

      Now that your implementation is complete, continue to the :ref:`saf-ex-alert-testing` section.


.. _saf-ex-alert-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the :ref:`saf-ex-alert-objective` section.
