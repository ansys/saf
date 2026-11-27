.. _saf-ex-spinner:

Spinners
########

.. _saf-ex-spinner-summary:

.. topic:: Objective

  Use a Dash spinner to display loading states in your solution.

  Source code for this example is in the `solution-examples <https://github.com/ansys/solution-examples>`_ repository.


.. _saf-ex-spinner-objective:

:material-outlined:`ads_click;1.25em;sd-text-primary` Objective
==================================================================

To deliver the best experience, it is important to let the user know when a process is running.
Spinners are a great way to indicate that the application is loading data or performing a task.
This example shows how to use Dash spinners to display loading states in your solution.

When you complete this example, you can expect the following output in the solution UI:

.. _-output-1:

.. figure:: /_static/images/usage_saf_ex_spinner_output_1.png
  :width: 100%

  Spinner displayed while the process is running

.. _-output-2:

.. figure:: /_static/images/usage_saf_ex_spinner_output_2.png
  :width: 100%

  Process completion message displayed when the process is complete


.. _saf-ex-spinner-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

.. vale off

To display loading states in the solution UI, you need the ``dcc.Loading`` component from the **Dash Core Components** library. For more information, see the Plotly Dash `dcc.Loading <https://dash.plotly.com/dash-core-components/loading>`_ documentation.

.. vale on


.. _saf-ex-spinner-solution:

:octicon:`code-square;1em;sd-text-primary` Solution
======================================================

To display a spinner while a process is running, work through the following sequence of tabs.

.. tab-set::

  .. tab-item:: 1️⃣Backend
    :name: saf-ex-spinner-backend-tab

    Create the solution definition.

    .. dropdown:: Define the step model
      :name: saf-ex-spinner-backend-drop-1
      :open:

      First, create a ``StepModel`` class named ``SpinnerStep`` with the following fields:

      * ``wait_time``: a float value that represents the time to wait
      * ``completed``: a Boolean value that indicates whether the process is completed

      Next, you need a transaction method that mocks a process which takes some time to complete.Create a ``wait_some_time`` transaction method that waits for a specified amount of time.

      .. code-block:: python
        :caption: solution/spinner_step.py

          import time
          from ansys.saf.glow.solution import StepModel, StepSpec, transaction


          class SpinnerStep(StepModel):
              """Step definition of the dash spinners."""

              wait_time: float = 3.0
              completed: bool = False

              @transaction(self=StepSpec(upload=["completed"], download=["wait_time"]))
              def wait_some_time(self) -> None:
                  """Wait for some time."""
                  start_time = time.time()
                  while (time.time() - start_time) < self.wait_time:
                      time.sleep(0.5)
                  self.completed = True


  .. tab-item:: 2️⃣Frontend
    :name: saf-ex-spinner-frontend-tab

    Create a simple button to trigger the ``wait_some_time`` transaction, display a spinner while waiting for the process to complete, and show a simple message when the process is completed.

    .. dropdown:: Create the page layout with the loading component
      :name: saf-ex-spinner-frontend-drop-1
      :open:

      To implement the static part of the UI, create the page layout for the spinner page.

      .. code-block:: python
        :caption: ui/pages/spinner_page.py

        from ansys.saf.glow.client import DashClient, callback
        from dash_extensions.enrich import Input, Output, State, dcc, html
        from dash_iconify import DashIconify
        import dash_mantine_components as dmc

        from ansys.solutions.examples.solution.definition import ExamplesSolution
        from ansys.solutions.examples.solution.spinner_step import SpinnerStep


        def layout(step: SpinnerStep):
            """Layout of the spinner page."""
            return html.Div(
                [
                    html.H1("Spinner", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
                    html.P(
                        "This page demonstrates the usage of spinners in Dash.",
                        className="lead",
                        style={"font-size": "20px"},
                    ),
                    html.Hr(className="my-2"),
                    html.Br(),
                    dmc.Button(
                        "Start",
                        id="start_button",
                        variant="filled",
                        radius="xl",
                        style={"color": "#FFFFFF", "width": "20%"},
                        leftIcon=DashIconify(icon="streamline:startup-solid"),
                    ),
                    dcc.Loading(
                        id="loading",
                        type="default",
                        children=html.Div(
                            id="loading_output",
                            style={"margin-top": "50px"},
                        ),
                    ),
                ]
            )

    .. dropdown:: Connect the button to the transaction method
      :name: saf-ex-spinner-frontend-drop-4
      :open:

      Whenever the :guilabel:`Start` button is clicked, the ``wait_some_time`` transaction method should be triggered. For this, create a callback function to call the transaction method and update the loading component accordingly.

      .. code-block:: python
        :caption: ui/pages/spinner_page.py

        @callback(
            Output("loading_output", "children"),
            Input("start_button", "n_clicks"),
            State("url", "pathname"),
            prevent_initial_call=True,
        )
        def start_transaction(n_clicks, pathname):
            """Start the transaction."""
            project = DashClient[ExamplesSolution].get_project(pathname)
            step = project.steps.spinner_step
            step.wait_some_time()
            return html.Div("Transaction completed.")


    Now that your implementation is complete, continue to the :ref:`saf-ex-spinner-testing` section.


.. _saf-ex-spinner-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the :ref:`saf-ex-spinner-objective` section.
