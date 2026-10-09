.. _saf-ex-gif:

GIF display
############

.. _saf-ex-gif-summary:

.. topic:: Objective

  Insert a GIF image in a solution UI.

  Source code for this example is in the `solution-examples <https://github.com/ansys/solution-examples>`_ repository.



.. _saf-ex-gif-objective:

:material-outlined:`ads_click;1.25em;sd-text-primary` Objective
==================================================================

Plotly Dash supports the display of images (``html.Img``) and videos (``html.Video``). However, it does not directly support the display of GIF images. This example shows how to display a GIF image in the Dash UI.

When you complete this example, you can expect the following output in the solution UI:

.. _saf-ex-gif-output-1:

.. image:: /_static/images/usage_saf_ex_gif_output_1.png
    :width: 100%


.. _saf-ex-gif-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

To display GIF images in the Dash UI, you need the Dash plug-in component `dash-gif-component <https://pypi.org/project/dash-gif-component/>`_. Install the component using the following command:

.. code-block:: bash

   poetry add dash-gif-component


.. _saf-ex-gif-solution:

:octicon:`code-square;1em;sd-text-primary` Solution
======================================================

Insert a GIF image in the Dash UI, as follows:

#. Save the image file to the solution's ``assets`` folder.

   For this example, the image is saved as ``/assets/images/gif_example.gif``.

#. Insert the GIF in the UI as shown in the following code:

   .. dropdown:: Insert GIF image
    :open:

    .. code-block:: python
        :caption: ui/pages/gif_page.py

        from dash_extensions.enrich import html
        import dash_gif_component as gif


        def layout():
            """Layout of the GIF example page."""
            return html.Div(
                [
                    html.Br(),
                    html.H1("GIF", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
                    html.Br(),
                    html.P(
                        "Insert a GIF in the page layout.",
                        className="lead",
                        style={"font-size": "20px"},
                    ),
                    html.Br(),
                    html.Hr(className="my-2"),
                    html.Br(),
                    html.Div(
                        [
                            gif.GifPlayer(
                                gif="/assets/images/gif_example.gif",
                                autoplay=True,
                                still="/assets/images/gif_example.gif",
                            )
                        ],
                        style={
                            "height": "500px",
                            "display": "flex",
                            "justify-content": "center",
                            "align-items": "center",
                        },
                    ),
                ]
            )

    Now that your implementation is complete, continue to the :ref:`saf-ex-gif-testing` section.


.. _saf-ex-gif-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the :ref:`saf-ex-gif-objective` section.

