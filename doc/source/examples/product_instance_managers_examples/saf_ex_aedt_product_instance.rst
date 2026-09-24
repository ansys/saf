.. _saf-ex-aedt-product-instance:


AEDT Product Instance Manager
#############################

.. topic:: Objective

  Drive an Ansys Electronics Desktop (AEDT) product, such as Maxwell 2D, from a solution.
  Start the product instance in a long-running transaction, call the AEDT API to add a
  rectangle to the design and analyze it, then shut the instance down.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-aedt-product-instance-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

Ansys Electronics Desktop is a unified simulation platform that integrates multiple Ansys solvers for electromagnetic, thermal, and circuit analysis, enabling seamless collaboration and coupled physics simulations.

This example shows how to create a **product instance manager** for AEDT products, such as Maxwell 2D, using the SAF framework. The product instance manager allows you to manage the lifecycle of an AEDT product instance, including starting, stopping, and accessing the product's API.

In this example, you learn how to:

- :material-outlined:`rocket_launch;1.25em;saf-objective-icon` Start a product instance from a
  **long-running transaction** decorated with ``@create_instance``.
- :material-outlined:`hub;1.25em;saf-objective-icon` Reuse the running instance in the other
  **transaction methods** through the ``@instance`` decorator.
- :material-outlined:`api;1.25em;saf-objective-icon` Call the **AEDT API** to add a rectangle to
  the design and to analyze it.
- :material-outlined:`power_settings_new;1.25em;saf-objective-icon` **Shut down** the product
  instance from a dedicated transaction method.
- :material-outlined:`bolt;1.25em;saf-objective-icon` Wire one **callback** per button so the UI
  triggers a transaction and reports its outcome.


.. _saf-ex-aedt-product-instance-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

.. note::
    This example requires the AEDT 2025 R1 (25R1) product to be installed on your machine.
    To work with an AEDT product instance, be sure to install the ``core-pim`` and ``instance-management-aedt`` extras from the ``ansys-saf-sdk`` package. You can do this by manually editing your ``pyproject.toml``.

    .. code-block:: toml

        ansys-saf-sdk = {version = "^0.2.0", extras = ["core-pim", "instance-management-aedt"]}

    This will install the supported version of PyAEDT to control the AEDT product instances.
    This example uses PIM as the product instance management system. If you want to use HPS instead, replace the ``core-pim`` extra with ``core-hps``.
    For more information, see :ref:`instance_management_configuration`.


.. _saf-ex-aedt-product-instance-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To create a product instance manager for AEDT products and interact with it, work through the following sequence of sections.


.. _saf-ex-aedt-product-instance-backend:

:material-outlined:`dns;1.25em;sd-text-primary` Backend
---------------------------------------------------------

Create the solution definition.

.. key-concept:: Product instance manager

    A **product instance manager** wraps a running Ansys product session. The
    ``@create_instance`` decorator starts the product and binds the session to a name, while the
    ``@instance`` decorator injects that same session into any other transaction method.

.. key-concept:: Instance lifecycle

    A product instance outlives the transaction method that created it. It stays available to
    every transaction method of the solution until a transaction explicitly shuts it down.

.. dropdown:: Define the step model
  :open:

  * There are two transactions that are used to manage the product instance lifecycle: ``initialize_maxwell_2d_instance`` and ``exit_aedt``.
     * The first one initializes the product instance, while the second one shuts it down.
     * The ``initialize_maxwell_2d_instance`` long-running transaction is decorated with ``@create_instance`` to create an instance of the AEDT product manager, in this case, ``Maxwell2DManager``.
     * The ``exit_aedt`` transaction is used to shutdown the AEDT instance.

  * The other two transactions, ``add_rectangle`` and ``run_analysis`` are used to add a rectangle to the design and to analyze it, respectively.

  .. code-block:: python
    :lineno-start: 5
    :caption: ``aedt_step.py``

    from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
    from ansys.saf.glow.solution.beta.aedt import Maxwell2DManager


    class Maxwell2DSetupVerificationStep(StepModel):
        """Step to verify the setup of Maxwell 2D instance."""

        aedt_version: str = "251"
        origin: list[float] = [0, 0, 0]
        dimension: list[float] = [10, 10]

        @transaction(self=StepSpec(download=["aedt_version"]))
        @create_instance("maxwell_2d_instance", Maxwell2DManager)
        @long_running
        def initialize_maxwell_2d_instance(self, maxwell_2d_instance: Maxwell2DManager) -> None:
            """Initialize the Maxwell 2D instance."""
            maxwell_2d_instance.initialize(version=self.aedt_version)

        @transaction(self=StepSpec(download=["origin", "dimension"]))
        @instance("maxwell_2d_instance")
        def add_rectangle(self, maxwell_2d_instance: Maxwell2DManager) -> None:
            """Add a rectangle to the Maxwell 2D instance."""
            primitives = maxwell_2d_instance.instance.modeler.primitives  # type: ignore
            primitives.create_rectangle(self.origin, self.dimension)  # type: ignore

        @transaction(self=StepSpec())
        @instance("maxwell_2d_instance")
        def run_analysis(self, maxwell_2d_instance: Maxwell2DManager) -> bool:
            """Run the analysis on the Maxwell 2D instance."""
            return maxwell_2d_instance.instance.analyze()  # type: ignore

        @transaction(self=StepSpec())
        @instance("maxwell_2d_instance")
        def exit_aedt(self, maxwell_2d_instance: Maxwell2DManager) -> None:
            """Shutdown the AEDT instance."""
            maxwell_2d_instance.shutdown()


.. _saf-ex-aedt-product-instance-frontend:

:material-outlined:`web;1.25em;sd-text-primary` Frontend
----------------------------------------------------------

Expose the solution definition in the UI.

.. key-concept:: Callback

    A **callback** is a Dash-decorated function that fires in response to a UI event. In a
    SAF solution, callbacks reach the backend through ``project.steps.<step_name>``, read or
    write fields, and invoke transaction methods — no manual HTTP calls needed.

.. dropdown:: Define the step layout
  :open:

  The user interface has four main buttons that each one triggers a transaction in the step model.

  .. code-block:: python
    :lineno-start: 4
    :caption: layout from ``aedt_instance_page.py``

    from ansys.saf.glow.client import DashClient, callback
    from dash_extensions.enrich import Input, Output, State, html  # pyright: ignore[reportMissingTypeStubs]
    from dash_iconify import DashIconify
    import dash_mantine_components as dmc

    from ansys.solutions.examples.solution.definition import ExamplesSolution


    def layout():
        """Layout of the AEDT step UI."""
        return html.Div(
            [
                html.Br(),
                html.H1("AEDT Instance Manager", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
                html.Br(),
                html.Hr(className="my-2"),
                html.Br(),
                html.P(
                    "This example demonstrates how to leverage PIM to control AEDT. Click the Initialize button to start\
                    the instance. A transaction method will start AEDT which can be used across all transaction methods of\
                    the solution. Run AEDT operations with the Add and Analyze buttons. Close AEDT using the Shutdown\
                    button.",
                    className="lead",
                    style={"font-size": "20px"},
                ),
                html.Div(
                    [
                        dmc.Button(
                            "Initialize Instance",
                            id="init_button",
                            variant="filled",
                            radius="xl",
                            style={"color": "#FFFFFF", "width": "200px"},
                            leftIcon=DashIconify(icon="streamline:startup-solid"),
                        ),
                        dmc.Button(
                            "Shutdown Instance",
                            id="shutdown_aedt_button",
                            variant="filled",
                            radius="xl",
                            style={"color": "#FFFFFF", "width": "200px", "marginLeft": "20px"},
                            leftIcon=DashIconify(icon="mdi:shutdown"),
                        ),
                    ],
                    style={
                        "display": "flex",
                        "justifyContent": "center",
                        "alignItems": "center",
                        "marginTop": "20px",
                    },
                ),
                html.Br(),
                html.Div(id="init_result", children="Not initialized yet."),
                html.Br(),
                html.P(
                    "Once the instance is created, Add and Analyze methods can be used.",
                    className="lead",
                    style={"font-size": "20px"},
                ),
                html.Br(),
                html.Div(
                    dmc.Button(
                        "Add Rectangle",
                        id="add_rectangle_button",
                        variant="filled",
                        radius="xl",
                        style={"color": "#FFFFFF", "width": "20%"},
                        leftIcon=DashIconify(icon="material-symbols:square-outline"),
                    ),
                    style={
                        "alignItems": "center",
                    },
                ),
                html.Br(),
                html.Div(id="rectangle_result", children="No Rectangle Added yet."),
                html.Br(),
                dmc.Group(
                    [
                        dmc.Button(
                            "Analyze Design",
                            id="analyze_button",
                            variant="filled",
                            radius="xl",
                            style={"color": "#FFFFFF", "width": "20%"},
                            leftIcon=DashIconify(icon="tabler:analyze"),
                        ),
                        html.Div(id="result", children="Result:"),
                    ]
                ),
            ],
        )

.. dropdown:: Define the initialization of the product instance callback
  :open:

  * When the :guilabel:`Initialize Instance` button is clicked, the initialization callback is activated.
  * The callback starts the long-running transaction to initialize the product instance.
  * After waiting for 60 seconds to allow the product instance to be initialized, it updates the UI with the result.

  .. code-block:: python
    :lineno-start: 96
    :caption: initialization callback from ``aedt_instance_page.py``

    @callback(
        Output("init_result", "children"),
        Input("init_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def init(n_clicks: int, pathname: str):
        """Initialize the Maxwell 2D instance."""
        project = DashClient[ExamplesSolution].get_project(pathname)
        step = project.steps.aedt_step
        step.initialize_maxwell_2d_instance().wait(timeout=60)
        return "Maxwell 2D Instance initialized successfully."

.. dropdown:: Define the add_rectangle transaction button
  :open:

  * The callback starting the transaction adds a rectangle to the design based on the step values.
  * This values can be set or accessed with ``project.steps.aedt_step.origin`` and ``project.steps.aedt_step.dimension``.

  .. code-block:: python
    :lineno-start: 110
    :caption: add_rectangle transaction button callback from ``aedt_instance_page.py``

    @callback(
        Output("rectangle_result", "children"),
        Input("add_rectangle_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def add_rectangle(n_clicks: int, pathname: str):
        """Add a rectangle to the Maxwell 2D instance."""
        project = DashClient[ExamplesSolution].get_project(pathname)
        step = project.steps.aedt_step
        step.add_rectangle()
        return "Rectangle Added successfully."


.. dropdown:: Define the analyze transaction button
  :open:

  * The callback starting the transaction analyzes the current design passed.
  * This transaction returns a boolean value that updates the UI after the transaction has finished.

  .. code-block:: python
    :lineno-start: 124
    :caption: analyze transaction button callback from ``aedt_instance_page.py``

    @callback(
        Output("result", "children"),
        Input("analyze_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def analyze(n_clicks: int, pathname: str):
        """Run the analysis on the Maxwell 2D instance."""
        project = DashClient[ExamplesSolution].get_project(pathname)
        step = project.steps.aedt_step
        value = step.run_analysis()
        return f"Result: {'Analysis Successful.' if value is True else 'Analysis Failed.'}"

.. dropdown:: Define the shutdown transaction button
  :open:

  * When the :guilabel:`Shutdown Instance` button is clicked, the shutdown callback is activated.
  * The callback starts the transaction to shutdown the product instance.

  .. code-block:: python
    :lineno-start: 138
    :caption: shutdown transaction button callback from ``aedt_instance_page.py``

    @callback(
        Output("init_result", "children"),
        Input("shutdown_aedt_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def shutdown(n_clicks: int, pathname: str):
        """Shutdown the AEDT instance."""
        project = DashClient[ExamplesSolution].get_project(pathname)
        step = project.steps.aedt_step
        step.exit_aedt()
        return "Maxwell 2D Instance shutdown successfully."

  Now that your implementation is complete, continue to the :ref:`saf-ex-aedt-product-instance-testing` section.


.. _saf-ex-aedt-product-instance-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-aedt-product-instance-feature-highlight>` section.
