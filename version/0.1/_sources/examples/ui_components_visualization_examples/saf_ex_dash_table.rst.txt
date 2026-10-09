.. _saf-ex-dash-table:

Data tables
###########

.. topic:: Objective

    Use a Dash data table to create static and interactive table components for displaying data in a solution UI.

    Source code for this example is in the `solution-examples <https://github.com/ansys/solution-examples>`_ repository.


.. _saf-ex-plotly-table-obj:

:material-outlined:`ads_click;1.25em;sd-text-primary` Objective
==================================================================

Displaying data in the user interface is fundamental to any solution app, involving inputs such as strings, integers, floats, and files.

As a solution developer, you must know how to present large datasets in the user interface. This example demonstrates the use of static and dynamic ``DataTable`` components for data display.

When you complete this example, you can expect the following output in the solution UI:

.. figure:: /_static/images/usage_plotly_table_integration_output.png



:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

To render data in a table, you need the ``dash.dash_table.DataTable`` component from **Dash**. For more information, see the Plotly Dash `DataTable <https://dash.plotly.com/datatable>`_ documentation.



:octicon:`code-square;1em;sd-text-primary` Solution
======================================================

To display data in an interactive table, work through the following sequence of tabs.

.. tab-set::

  .. tab-item:: 1️⃣Logic
      :name: saf-ex-plotly-table-logic-tab

      Write the business logic.

      .. dropdown:: Generate or download the data
        :open:


        In the ``logic`` folder, create a module named ``parametric_data.py`` to generate the set of points.


        .. code-block:: python
            :caption: solution/logic/table_logic.py

            import numpy as np


            def generate_table_data(points: int = 30) -> dict:
                """Compute the data for the table."""
                t = np.linspace(-6, 6, points)
                x_s = 10 * np.sin(9.9 * t) * np.round(np.sqrt(np.cos(np.cos(10 * t))))
                y_s = 9 * np.cos(9.9 * t) ** 2 * np.sin(np.sin(10 * t))
                x, y = np.empty(0), np.empty(0)
                for alpha in np.linspace(0, 360, 6):
                    alpha = np.radians(alpha)
                    x = np.append(x, x_s * np.cos(alpha) + y_s * np.sin(alpha), axis=0)
                    y = np.append(y, -x_s * np.sin(alpha) + y_s * np.cos(alpha), axis=0)
                d = np.sqrt(x**2 + y**2)
                data_dict = {"x_coords": x.tolist(), "y_coords": y.tolist(), "distance": d.tolist()}
                return data_dict



  .. tab-item:: 2️⃣Backend
      :name: saf-ex-plotly-table-backend-tab

      Create the solution definition.

      .. dropdown:: Define the step model
       :open:

       First, create a ``StepModel`` class named ``TableStep`` with the following step fields:

       - ``data_dict``: a dictionary containing the generated table data
       - ``table_flag``: a flag to indicate if the table data is available

       Then, create a ``generate_data`` transaction method to
       invoke the business logic method ``generate_table_data``.

       Finally, update the ``data_dict`` and ``table_flag`` fields with the computed data.

       .. code-block:: bash
           :caption: solution/table_step.py

           from ansys.saf.glow.solution import StepModel, StepSpec, transaction

           from ansys.solutions.examples.solution.logic.table_logic import generate_table_data


           class TableStep(StepModel):
               """Step definition of the table step."""

               data_dict: dict = {}
               table_flag: bool = False

               @transaction(self=StepSpec(upload=["data_dict", "table_flag"]))
               def generate_data(self) -> None:
                   """Generate the data for the table."""
                   data_dict = generate_table_data()
                   self.data_dict = data_dict
                   self.table_flag = True


  .. tab-item:: 3️⃣Frontend

   Create the page layout with a button to trigger the table data generation and a container to display the interactive data table.

   .. dropdown:: Create the page layout with the table
    :open:

    In the ``layout`` function, add:

    * a ``dmc.Button`` from the ``dash_mantine_components`` library to generate the table data
    * an ``html.Div`` to contain the table

    .. code-block:: python
        :caption: ui/pages/table_page.py

        from ansys.saf.glow.client import DashClient, callback
        from dash import dash_table
        from dash_extensions.enrich import Input, Output, State, html
        from dash_iconify import DashIconify
        import dash_mantine_components as dmc
        import pandas as pd

        from ansys.solutions.examples.solution.basic.table_step import TableStep
        from ansys.solutions.examples.solution.definition import ExamplesSolution


        def layout(step: TableStep):
            """Layout of the table step page."""
            return html.Div(
                [
                    html.H1("Dash Table", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
                    html.Br(),
                    html.P(
                        "Use a table to display large datasets in a solution UI.",
                        className="lead",
                        style={"font-size": "20px"},
                    ),
                    html.Br(),
                    html.Hr(className="my-2"),
                    html.Br(),
                    dmc.Button(
                        "Generate data",
                        id="generate-data-button",
                        leftIcon=DashIconify(icon="streamline:startup-solid"),
                        radius="xl",
                        disabled=False,
                        className="mantine-button",
                        style={"color": "#FFFFFF", "width": "100%", "background-color": "#000000", "font-size": "14px"},
                    ),
                    html.Br(),
                    html.Div(id="data-table"),
                ]
            )


   .. dropdown:: Define the interactivity for the page
    :open:

    **Generate the data**

    The ``create_table_data`` function creates table data when the ``generate-data-button`` is clicked. This function:

    * retrieves the project and step objects from the Dash client,
    * generates the data using the ``generate_data`` method of the ``TableStep`` object, and
    * returns a ``DataTable`` using the ``_create_data_table`` function.

    .. code-block:: python
        :caption: ui/pages/table_page.py

        @callback(
            Output("data-table", "children"),
            Input("generate-data-button", "n_clicks"),
            State("url", "pathname"),
            prevent_initial_call=True,
        )
        def create_table_data(n_clicks, pathname):
            """Create the table data."""
            project = DashClient[ExamplesSolution].get_project(pathname)
            step = project.steps.table_step
            if n_clicks >= 1:
                step.generate_data()
                return _create_data_table(step)

    **Create the table**

    Add the ``_create_data_table`` function to create a Dash ``DataTable`` from the data dictionary. This function takes a ``TableStep`` object as an argument.

    * If the ``table_flag`` step field is ``True``, it creates a Dash ``DataTable`` from the ``data_dict`` step field.
    * If ``table_flag`` is ``False``, it returns an empty ``Div``.

    For more information on customizing the table, see the Plotly Dash `Styling the DataTable <https://dash.plotly.com/datatable/style>`_ documentation.

    .. code-block:: bash
        :caption: ui/pages/compute_page.py

        def _create_data_table(step):
            """Create a Dash table."""
            if step.table_flag:
                df = pd.DataFrame(step.data_dict)
                table_atti = html.Div(
                    [
                        dash_table.DataTable(
                            data=df.to_dict("records"),
                            columns=[{"name": i, "id": i} for i in df.columns],
                            id="id_data_table",
                            editable=True,
                            filter_action="native",
                            sort_action="native",
                            sort_mode="multi",
                            column_selectable="single",
                            row_selectable="multi",
                            row_deletable=True,
                            selected_columns=[],
                            selected_rows=[],
                            page_action="native",
                            page_current=0,
                            page_size=10,
                        ),
                    ]
                )
            else:
                table_atti = html.Div("")

    Now that your implementation is complete, continue to the :ref:`saf-ex-plotly-table-testing`  section.

.. _saf-ex-plotly-table-testing:


:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the :ref:`saf-ex-plotly-table-obj` section.
