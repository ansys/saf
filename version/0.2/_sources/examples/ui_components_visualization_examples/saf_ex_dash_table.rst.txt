.. _saf-ex-dash-table:

Data tables
###########

.. topic:: Objective

  Display a large dataset in a solution UI: generate the data in the backend, store it in a
  step field, and render it in an interactive Dash ``DataTable`` that the user can sort,
  filter, and edit.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-dash-table-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

The user interface (UI) of a solution app can display both **input data** (such as strings, integers, floats, and files) and **output data** (such as tables, 1D/2D/3D graphics, 3D viewers, and images).

As a solution developer, you must know how to present large datasets in the UI. A table is the most convenient component for this purpose because it remains readable as the number of rows grows.

In this example, you learn how to:

- :material-outlined:`functions;1.25em;saf-objective-icon` Write **business logic** that
  generates a dataset with NumPy.
- :material-outlined:`data_object;1.25em;saf-objective-icon` Store the dataset in a **typed
  step field** and expose a **transaction method** that generates it.
- :material-outlined:`table_chart;1.25em;saf-objective-icon` Render the dataset with a Dash
  ``DataTable`` component and enable sorting, filtering, and pagination.
- :material-outlined:`bolt;1.25em;saf-objective-icon` Wire a **callback** so a button click
  triggers the backend computation and populates the table.

When you complete this example, you can expect the following output in the solution UI:

.. _saf-ex-dash-table-output-1:

.. image:: /_static/images/usage_plotly_table_integration_output.png
  :width: 100%


.. _saf-ex-dash-table-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

To render data in a table, you need the ``dash.dash_table.DataTable`` component from **Dash**. For more information, see the Plotly Dash `DataTable <https://dash.plotly.com/datatable>`_ documentation.


.. _saf-ex-dash-table-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To display a dataset in an interactive table, work through the following sequence of sections.


.. _saf-ex-dash-table-logic:

:material-outlined:`functions;1.25em;sd-text-primary` Logic
------------------------------------------------------------

Write the business logic.

.. key-concept:: Business logic

    Business logic is plain Python: it has no dependency on SAF and can be developed and
    tested on its own before it is wired into a step.

.. dropdown:: Generate the data
  :open:

  In the ``solution/logic`` folder, the ``table_logic.py`` module exposes a
  ``generate_table_data`` function that returns the dataset as a dictionary of columns.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/logic/table_logic.py
    :language: python
    :caption: solution/logic/table_logic.py
    :pyobject: generate_table_data


.. _saf-ex-dash-table-backend:

:material-outlined:`dns;1.25em;sd-text-primary` Backend
---------------------------------------------------------

Create the solution definition.

.. key-concept:: Typed field

    A field is a class attribute with a **type annotation** and a default value. SAF uses
    the annotation to persist the field, expose it through the REST API, and surface it to
    the frontend through the ``DashClient``.

.. dropdown:: Define the step fields
  :open:

  Declare a ``data_dict`` field that holds the generated dataset and a ``table_flag`` field
  that tells the frontend whether the dataset is available.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/basic_step.py
    :language: python
    :caption: solution/basic_step.py
    :lines: 73-78
    :emphasize-lines: 4-6
    :dedent:

.. key-concept:: Transaction method

    A **transaction method** is the only place where step fields are read and written. Any
    method that touches a field must be decorated with ``@transaction``, which declares the
    fields it downloads (reads) and uploads (writes) through its ``StepSpec``.

.. dropdown:: Add a transaction method to generate the data
  :open:

  Create a ``generate_data`` transaction method that invokes the ``generate_table_data``
  business logic function and stores the result in the step fields.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/basic_step.py
    :language: python
    :caption: solution/basic_step.py
    :lines: 190-195
    :dedent:

.. important::

  This example deliberately uses a **blocking** transaction method rather than a
  long-running one. The business logic was tested beforehand and generates the dataset in
  less than a second, so blocking the UI for that duration is safe and keeps the code
  simpler.

  Nothing prevents you from converting it to a long-running transaction method by adding
  the ``@long_running`` decorator if your own computation takes longer. For more
  information, see :ref:`saf-ex-long-transaction`.


.. _saf-ex-dash-table-frontend:

:material-outlined:`web;1.25em;sd-text-primary` Frontend
----------------------------------------------------------

Expose the solution definition in the UI.

.. dropdown:: Create the page layout
  :open:

  In the ``ui/pages`` folder, the ``layout`` function of the page adds a ``dmc.Button`` that
  triggers the data generation and an empty ``html.Div`` that hosts the table once the data
  is available.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/table_page.py
    :language: python
    :caption: ui/pages/basic/table_page.py
    :pyobject: layout

.. key-concept:: Table styling

    The ``DataTable`` component exposes a dedicated style property for each part of the
    table, such as ``style_header``, ``style_data``, and ``style_filter``. For more
    information, see the Plotly Dash
    `Styling the DataTable <https://dash.plotly.com/datatable/style>`_ documentation.

.. dropdown:: Build the table
  :open:

  The ``_create_data_table`` function converts the ``data_dict`` step field into a pandas
  ``DataFrame`` and builds the ``DataTable`` from it. Sorting, filtering, row selection, row
  deletion, and pagination are enabled through the options of the component. When
  ``table_flag`` is ``False``, the function returns an empty ``html.Div`` so that nothing is
  displayed before the data is generated.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/table_page.py
    :language: python
    :caption: ui/pages/basic/table_page.py
    :pyobject: _create_data_table

.. key-concept:: Callback

    A **callback** is a Dash-decorated function that fires in response to a UI event. In a
    SAF solution, callbacks reach the backend through ``project.steps.<step_name>``, read or
    write fields, and invoke transaction methods — no manual HTTP calls needed.

.. dropdown:: Trigger the backend computation from the frontend
  :open:

  Write a callback that invokes ``generate_data`` when the button is clicked and returns the
  table built from the newly generated data.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/table_page.py
    :language: python
    :caption: ui/pages/basic/table_page.py
    :pyobject: create_table_data

  Now that your implementation is complete, continue to the :ref:`saf-ex-dash-table-testing` section.


.. _saf-ex-dash-table-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-dash-table-feature-highlight>` section.
