.. _saf-ex-plotly-graph:

Plotly graphs
#############

.. topic:: Objective

  Build an interactive 2D Plotly graph in a solution UI: compute the data in the backend,
  store it in step fields, and let the user reshape the curve from the frontend.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-plotly-graph-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

The user interface (UI) of a solution app can display both **input data** (such as strings, integers, floats, and files) and **output data** (such as 1D/2D/3D graphics, 3D viewers, and images).

In this example, you learn how to:

- :material-outlined:`functions;1.25em;saf-objective-icon` Write **business logic** that computes
  the transcendental butterfly curve with NumPy.
- :material-outlined:`data_object;1.25em;saf-objective-icon` Store the curve data in **typed step
  fields** and expose a **transaction method** that (re)computes it.
- :material-outlined:`show_chart;1.25em;saf-objective-icon` Render the data with a Dash
  ``dcc.Graph`` component and customize its layout.
- :material-outlined:`bolt;1.25em;saf-objective-icon` Wire a **callback** so UI controls
  trigger the backend computation and refresh the plot.

When you complete this example, you can expect the following output in the solution UI:

.. _saf-ex-plotly-graph-output-1:

.. image:: /_static/images/usage_plotly_graph_integration_output.png
  :width: 100%


.. _saf-ex-plotly-graph-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

To render any Plotly-powered data visualization, you need the ``dcc.Graph`` component from the **Dash Core Components** library. For more information, see the `Plotly Dash documentation <https://dash.plotly.com/dash-core-components/graph>`_.


.. _saf-ex-plotly-graph-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To display a set of points in a two-dimensional Plotly graph, work through the following sequence of sections.


.. _saf-ex-plotly-graph-logic:

:material-outlined:`functions;1.25em;sd-text-primary` Logic
------------------------------------------------------------

Write the business logic.

.. key-concept:: Business logic

    Business logic is plain Python: it has no dependency on SAF and can be developed and
    tested on its own before it is wired into a step.

.. dropdown:: Compute the curve coordinates
  :open:

  In the ``solution/logic`` folder, the ``butterfly_curve.py`` module exposes a
  ``compute_butterfly_curve`` function that generates the set of points of the
  `transcendental butterfly curve <https://en.wikipedia.org/wiki/Butterfly_curve_(transcendental)>`_
  for the given parameters.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/logic/butterfly_curve.py
    :language: python
    :caption: solution/logic/butterfly_curve.py
    :pyobject: compute_butterfly_curve


.. _saf-ex-plotly-graph-backend:

:material-outlined:`dns;1.25em;sd-text-primary` Backend
---------------------------------------------------------

Create the solution definition.

.. key-concept:: Typed field

    A field is a class attribute with a **type annotation** and a default value. SAF uses
    the annotation to persist the field, expose it through the REST API, and surface it to
    the frontend through the ``DashClient``.

.. dropdown:: Define the step fields
  :open:

  Let ``x_coords`` and ``y_coords`` be the x and y coordinates of a set of points you
  want to display in the solution UI. Declare these as step fields, alongside the
  parameters that control the shape of the curve.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/basic_step.py
    :language: python
    :caption: solution/basic_step.py
    :lines: 73-88
    :emphasize-lines: 8-16
    :dedent:

.. key-concept:: Transaction method

    A **transaction method** is the only place where step fields are read and written. Any
    method that touches a field must be decorated with ``@transaction``, which declares the
    fields it downloads (reads) and uploads (writes) through its ``StepSpec``.

.. dropdown:: Add a transaction method to compute the curve
  :open:

  Create a ``compute_butterfly_curve`` transaction method that invokes the
  ``compute_butterfly_curve`` business logic function and stores the result in the step fields.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/basic_step.py
    :language: python
    :caption: solution/basic_step.py
    :lines: 197-224
    :dedent:

.. important::

  This example deliberately uses a **blocking** transaction method rather than a
  long-running one. The business logic was tested beforehand and computes the curve in
  less than a second, so blocking the UI for that duration is safe and keeps the code
  simpler.

  Nothing prevents you from converting it to a long-running transaction method by adding
  the ``@long_running`` decorator if your own computation takes longer. For more
  information, see :ref:`saf-ex-long-transaction`.


.. _saf-ex-plotly-graph-frontend:

:material-outlined:`web;1.25em;sd-text-primary` Frontend
----------------------------------------------------------

Expose the solution definition in the UI.

.. dropdown:: Initialize the Plotly graph
  :open:

  In the ``ui/pages`` folder, the ``layout`` function of the page adds a ``dcc.Graph``
  component and passes it the figure built from the step fields.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/plot_page.py
    :language: python
    :caption: ui/pages/basic/plot_page.py
    :lines: 251-270
    :dedent:

.. key-concept:: Figure layout

    The ``layout`` key of a Plotly figure controls its size, axes and margins. Plotly
    enables many kinds of customization. For more information, see its
    `documentation <https://plotly.com/python-api-reference/generated/plotly.graph_objects.Layout.html>`_.

.. dropdown:: Build the figure
  :open:

  The ``_butterfly_figure`` function builds the figure from the step fields. The points are
  colored by their distance to the origin through the ``color`` and ``colorscale`` marker
  options, the ``width`` and ``height`` options control the size of the figure, the
  ``margin`` option adjusts the margins relative to the graph box, and the ``xaxis`` and
  ``yaxis`` options display the axes with an equal aspect ratio.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/plot_page.py
    :language: python
    :caption: ui/pages/basic/plot_page.py
    :pyobject: _butterfly_figure

.. dropdown:: Add controls to tune the curve parameters
  :open:

  Add a ``dmc.Slider`` component for each parameter so the user can play with the shape
  of the curve. Each slider is initialized with the value currently stored in the step.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/plot_page.py
    :language: python
    :caption: ui/pages/basic/plot_page.py
    :pyobject: _butterfly_parameters

.. key-concept:: Callback

    A **callback** is a Dash-decorated function that fires in response to a UI event. In a
    SAF solution, callbacks reach the backend through ``project.steps.<step_name>``, read or
    write fields, and invoke transaction methods — no manual HTTP calls needed.

.. dropdown:: Trigger the backend computation from the frontend
  :open:

  Write a callback that updates the curve parameter fields, invokes
  ``compute_butterfly_curve``, and refreshes the figure with the new coordinates.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/basic/plot_page.py
    :language: python
    :caption: ui/pages/basic/plot_page.py
    :pyobject: draw_butterfly_curve

  Now that your implementation is complete, continue to the :ref:`saf-ex-plotly-graph-testing` section.


.. _saf-ex-plotly-graph-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-plotly-graph-feature-highlight>` section.

