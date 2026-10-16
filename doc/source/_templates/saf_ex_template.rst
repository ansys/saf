.. ### TEMPLATE for creating SAF usage examples
 -----------------------------------------------
 Use this template to document your SAF usage example.
 (Placeholder content is taken from the "Plotly graph  integration" SAF usage example.)

.. ### HOW TO USE:

.. 1. Choose a name for your example:
     * Communicate the purpose of the example as a noun
     * Avoid unnecessary words like "example," "tutorial," "simple," or "basic"
     * EXAMPLE: Plotly graph integration

.. 2. Create the example file:
     * Copy this RST template file into the folder `doc\source\saf_hub\usage`
     * Rename the file for your example using this convention: saf_ex_example_name.rst
     * EXAMPLE: saf_ex_plotly_graph_integration.rst

.. 3. Create an image folder:
     * Follow the README instructions in `doc\source\_static\usage\saf_ex_images_template`

.. 4. Update placeholder content with your own information:
     * Placeholder text is in <angle brackets>
     * Placeholder code is in drop-downs
     * In code blocks, be sure to update the filename/path in the caption

.. 5. Update the example name throughout the file:
     * Replace "template" with the example name (abbreviations okay)
     * EXAMPLES:
         * Link targets:
              From:  .. _saf-ex-template:
              To:    .. _saf-ex-plotly-graph-int:
         * Object names:
              From:  :name: saf-ex-template-logic-tab
              To:    :name: saf-ex-plotly-graph-int-logic-tab
         * File paths:
              From:  .. figure:: /_static/usage/saf_ex_template/output_1.png
              To:    .. figure:: /_static/usage/saf_ex_plotly_graph_int/output_1.png

.. 6. Add references to the index file.
     * Follow the instructions in `doc\source\saf_hub\usage\index.rst`


.. _saf-ex-template:

<Example name>
###########################
.. Update the "Summary" placeholder to describe what the example does.

.. _saf-ex-template-summary:

.. topic:: Objective

  Learn to <use Plotly graphs to display step field data in the user interface of a solution.>


.. _saf-ex-template-objective:

:material-outlined:`ads_click;1.25em;sd-text-primary` Objective
==================================================================
.. Update placeholders with the example's purpose and what the user can expect to learn.

<The user interface (UI) of a solution app can display both **input data** (such as strings, integers, floats, and files) and **output data** (such as 1D/2D/3D graphics, 3D viewers, and images).>

<As a solution developer, you must know how to display step field data in the UI. This example demonstrates how to display step field data a static plot in the solution UI.

When you complete this example, you can expect the following output in the solution UI:

.. Include at least one image to show the expected results.
   When referencing an image, always start the path with:  _static/
   Update or remove the figure caption.

.. _saf-ex-template-output-1:

.. figure:: /_static/usage/saf_ex_images_template/output_1.png
  :width: 100%

  <Static plot for the **Compute** step>


.. _saf-ex-template-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================
..

.. List any prerequisite packages or SAF usage examples that should be completed first.
.. If none exist, delete the section.

Packages
 <To render any Plotly powered data visualization, you need the ``dcc.Graph`` component from the **Dash Core Components** library. For more information, see the `Plotly Dash documentation <https://dash.plotly.com/dash-core-components/graph>`_.>


Usage examples
 Make sure that you have already completed the following prerequisite examples:

 * <LINK_TO_EXAMPLE_1>
 * <LINK_TO_EXAMPLE_2>


.. _saf-ex-template-solution:

:octicon:`code-square;1em;sd-text-primary` Solution
======================================================
.. Replace the placeholder with what the example does.

To <display a simple set of points in a two-dimensional Plotly graph>, work through the **1️⃣Logic**, **2️⃣Backend**, and **3️⃣Frontend** tabs in sequence.

.. TABS:
  * Keep the tab names "Logic", "Backend", and "Frontend".
  * Keep the generic tab intro sentence. You may add sentences to summarize what is being done.

.. DROPDOWNS:
  * Choose titles that express the action as a verb ("Do this").
  * Be sure to use the `open` directive for all drop-downs.
  * Add/delete tabs as needed for the steps in your example.

.. tab-set::

  .. tab-item:: 1️⃣Logic
    :name: saf-ex-template-logic-tab

    First, write the business logic.

    .. dropdown:: <Create a method to generate the data>
      :name: saf-ex-template-logic-drop-1
      :open:

      <In the ``logic`` folder, create a module named ``parametric_curves.py``.>

      <In this module, create a ``compute_rd_curve`` method to generate the set of points.>

      .. code-block:: bash
        :caption: <solution/logic/parametric_curves.py>

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
    :name: saf-ex-template-backend-tab

    Next, create the solution definition.

    .. dropdown:: <Define the step model>
      :name: saf-ex-template-backend-drop-1
      :open:

      <Let ``x_coords`` and ``y_coords`` be the x and y coordinates of a set of points you
      want to display in the solution UI. Declare these as step fields in the step model for the **Compute** step.>

      <In the ``solution`` folder, create a module named ``compute_step.py``.>

      <In this module, create a ``compute_parametric_curve`` transaction method to invoke the ``compute_rd_curve`` business logic method.>

      .. code-block:: bash
        :caption: <solution/compute_step.py>

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
    :name: saf-ex-template-frontend-tab

    Now, expose the solution definition in the UI.

    .. dropdown:: <Initialize the Plotly graph>
      :name: saf-ex-template-frontend-drop-1
      :open:

      <In the ``ui/pages`` folder, create a ``compute_page.py`` module to define the page layout for the **Compute** step.>

      <In the ``layout`` function, add a ``dcc.Graph`` component and pass it the data you want to show.>

      .. code-block:: bash
        :caption: <ui/pages/compute_page.py>

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

    .. dropdown:: <Customize the figure layout>
      :name: saf-ex-template-frontend-drop-2
      :open:

      <In the ``dcc.Graph`` component, customize the layout of the figure using the ``layout`` key.>

      * <Use the ``width`` and ``height`` options to control the size of the figure.>
      * <Use the ``margin`` option to adjust the margins relative to the graph box.>

      <Plotly enables many kinds of customization. For more information, see its `documentation <https://plotly.com/python-api-reference/generated/plotly.graph_objects.Layout.html>`_ .>

      .. code-block:: bash
        :caption: <ui/pages/compute_page.py>

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


    .. dropdown:: <Trigger the backend processes>
      :name: saf-ex-template-frontend-drop-3
      :open:

      <In the ``layout`` function, create a button to trigger the backend coordinates computation from the frontend.>

      .. code-block:: bash
        :caption: <ui/pages/compute_page.py>

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

    .. dropdown:: <Add interactivity>
      :name: saf-ex-template-frontend-drop-4
      :open:

      <You can also introduce interactivity by adding callback to the step.>

      <For instance, the following callback updates the data you have displayed:

      .. code-block:: bash
        :caption: <ui/pages/compute_page.py>

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

      Now that your implementation is complete, continue to the :ref:`saf-ex-template-testing` section.


.. _saf-ex-template-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================
.. DOC NOTE: Additional info pending.
.. Add testing/debugging steps, as needed for your example.

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the :ref:`saf-ex-template-objective` section.

