.. _saf-ex-plotly-graph:

Plotly graphs
#############

.. _saf-ex-plotly-graph-summary:

.. topic:: Objective

  Use Plotly graphs to display step field data in a solution UI.

  Source code for this example is in the `solution-examples <https://github.com/ansys/solution-examples>`_ repository.


.. _saf-ex-plotly-graph-objective:

:material-outlined:`ads_click;1.25em;sd-text-primary` Objective
==================================================================

The user interface (UI) of a solution app can display both **input data** (such as strings, integers, floats, and files) and **output data** (such as 1D/2D/3D graphics, 3D viewers, and images).

As a solution developer, you must know how to display step field data in the UI. This example demonstrates how to display step field data a static plot in the solution UI.

When you complete this example, you can expect the following output in the solution UI:

.. _saf-ex-plotly-graph-output-1:

.. image:: /_static/images/usage_plotly_graph_integration_output.png
  :width: 100%


.. _saf-ex-plotly-graph-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

To render any Plotly-powered data visualization, you need the ``dcc.Graph`` component from the **Dash Core Components** library. For more information, see the `Plotly Dash documentation <https://dash.plotly.com/dash-core-components/graph>`_.


.. _saf-ex-plotly-graph-solution:

:octicon:`code-square;1em;sd-text-primary` Solution
======================================================

To display a simple set of points in a two-dimensional Plotly graph, work through the following sequence of tabs.


.. tab-set::

  .. tab-item:: 1️⃣Logic
    :name: saf-ex-plotly-graph-logic-tab

    Write the business logic.

    .. dropdown:: Create a method to generate the data
      :open:

      In the ``logic`` folder, create a module named ``parametric_curves.py``.

      In this module, create a ``compute_rd_curve`` method to generate the set of points.

      .. code-block:: bash
        :caption: solution/logic/parametric_curves.py

        def compute_rd_curve(points: int = 10000) -> tuple:
          t = np.linspace(-6, 6, points)
          x_s = 10*np.sin(9.9*t)*np.round(np.sqrt(np.cos(np.cos(10*t))))
          y_s = 9*np.cos(9.9*t)**2*np.sin(np.sin(10*t))
          x, y = np.empty(0), np.empty(0)
          for alpha in np.linspace(0, 360, 6):
            alpha = np.radians(alpha)
            x = np.append(x, x_s*np.cos(alpha) + y_s*np.sin(alpha), axis=0)
            y = np.append(y, -x_s*np.sin(alpha) + y_s*np.cos(alpha), axis=0)
          d = np.sqrt(x**2 + y**2)
          return x.tolist(), y.tolist(), d.tolist()


  .. tab-item:: 2️⃣Backend
    :name: saf-ex-plotly-graph-backend-tab

    Create the solution definition.

    .. dropdown:: Define the step model
      :open:

      Let ``x_coords`` and ``y_coords`` be the x and y coordinates of a set of points you
      want to display in the solution UI. Declare these as step fields in the step model for the **Compute** step.

      In the ``solution`` folder, create a module named ``compute_step.py``.

      In this module, create a ``compute_parametric_curve`` transaction method to invoke the ``compute_rd_curve`` business logic method.

      .. code-block:: bash
        :caption: solution/compute_step.py

                class ComputeStep(StepModel):
                    """Step model of the compute step."""

                    x_coords: list = []
                    y_coords: list = []
                    distance: list = []

                    @transaction(
                        self=StepSpec(
                            upload=[
                                "x_coords",
                                "y_coords",
                                "distance"
                            ]
                        )
                    )
                    def compute_parametric_curve(self) -> None:
                        """Method to compute the sum of two numbers."""
                        self.x_coords, self.y_coords, self.distance = parametric_curves.compute_rd_curve()


  .. tab-item:: 3️⃣Frontend
    :name: saf-ex-plotly-graph-frontend-tab

    Expose the solution definition in the UI.

    .. dropdown:: Initialize the Plotly graph
      :open:

      In the ``ui/pages`` folder, create a ``compute_page.py`` module to define the page layout for the **Compute** step.

      In the ``layout`` function, add a ``dcc.Graph`` component and pass it the data you want to show.

      .. code-block:: bash
        :caption: ui/pages/compute_page.py

          dcc.Graph(
                  id="graph",
                  figure={
                      "data": [
                          {
                              "type": "scatter",
                              "x": step.x_coords,
                              "y": step.y_coords
                          },
                      ]
                  }
              )

    .. dropdown:: Customize the figure layout
      :open:

      In the ``dcc.Graph`` component, customize the layout of the figure using the ``layout`` key.

      * Use the ``width`` and ``height`` options to control the size of the figure.
      * Use the ``margin`` option to adjust the margins relative to the graph box.

      Plotly enables many kinds of customization. For more information, see its `documentation <https://plotly.com/python-api-reference/generated/plotly.graph_objects.Layout.html>`_ .

      .. code-block:: bash
        :caption: ui/pages/compute_page.py

          dcc.Graph(
              id="graph",
              figure={
                  "data": [
                      {
                          "type": "scatter",
                          "x": step.x_coords,
                          "y": step.y_coords
                      },
                  ],
                  "layout": {
                      "width": 600,
                      "height": 600,
                      "margin": {
                          "l": 0,
                          "r": 0,
                          "b": 0,
                          "t": 0,
                      },
                  }
              }
          )


    .. dropdown:: Trigger the backend processes
      :open:

      In the ``layout`` function, create a button to trigger the backend coordinates computation from the frontend.

      .. code-block:: bash
        :caption: ui/pages/compute_page.py

        html.Div(
            dbc.Button(
                "Compute",
                id="compute",
                disabled=False,
                style = {
                    "display": "flex",
                    "justify-content": "center",
                    "align-items": "center",
                    "fontSize": "100%",
                    "background-color": "rgba(0, 0, 0, 1)",
                    "border-color": "rgba(0, 0, 0, 1)",
                    "height": "30px",
                }
            ),
            className="d-grid gap-2 col-5 mx-auto",

    .. dropdown:: Add interactivity
      :open:

      You can also introduce interactivity by adding callback to the step.

      For instance, the following callback updates the data you have displayed:

      .. code-block:: bash
        :caption: ui/pages/compute_page.py

          @callback(
              Output("graph", "figure"),
              Input("compute", "n_clicks"),
              State("url", "pathname"),
              State("graph", "figure"),
              prevent_initial_call=True,
          )
          def update_graph_data(n_clicks, pathname, figure):
              """Callback function to trigger the computation."""
              project = DashClient[Cosmic_WaveSolution].get_project(pathname)
              step = project.steps.compute_step
              step.compute_parametric_curve()
              figure["data"][0]["x"] = step.x_coords
              figure["data"][0]["y"] = step.y_coords
              return figure

      Now that your implementation is complete, continue to the :ref:`saf-ex-plotly-graph-testing` section.


.. _saf-ex-plotly-graph-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the :ref:`saf-ex-plotly-graph-objective` section.

