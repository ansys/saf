.. _saf-ex-fluent-product-instance:


Fluent Product Instance Manager
###############################

.. topic:: Objective

  Drive an Ansys Fluent session from a solution. Launch the solver in a long-running
  transaction, import a mesh, set up the physics, and run a transient simulation, while the
  solver transcript is streamed live to the user interface.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-fluent-product-instance-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

Ansys Fluent is a powerful simulation tool for computational fluid dynamics (CFD), supporting a wide range of applications including fluid flow, heat transfer, and multiphase phenomena.

This example demonstrates how to create a **product instance manager** for Fluent products using the SAF framework. The product instance manager enables management of the Fluent product instance lifecycle, including starting, stopping, and accessing the product's API.

In this example, you learn how to:

- :material-outlined:`rocket_launch;1.25em;saf-objective-icon` Launch a Fluent session from a
  **long-running transaction** decorated with ``@create_instance``.
- :material-outlined:`hub;1.25em;saf-objective-icon` Reuse the running session in the other
  **transaction methods** through the ``@instance`` decorator.
- :material-outlined:`api;1.25em;saf-objective-icon` Call the **Fluent API** to import a mesh, set
  up the physics, and run a transient simulation.
- :material-outlined:`save;1.25em;saf-objective-icon` Store the solver output files in
  **entity handle fields** through the storage scope.
- :material-outlined:`stream;1.25em;saf-objective-icon` Stream the solver transcript to the UI with
  ``raise_event`` and a ``DashClient`` **event listener**.
- :material-outlined:`notifications;1.25em;saf-objective-icon` Drive **button states and
  notifications** from the event stream, then shut the instance down.

When you complete this example, you can expect the following output in the solution UI:

.. _saf-ex-fluent-product-instance-output-1:

.. figure:: /_static/images/usage_saf_ex_fluent_product_instance_output_1.png
  :width: 100%

  Status before the initialization of the product instance

.. figure:: /_static/images/usage_saf_ex_fluent_product_instance_output_2.png
  :width: 100%

  Status after the initialization of the product instance

.. figure:: /_static/images/usage_saf_ex_fluent_product_instance_output_3.png
  :width: 100%

  Status after calling the ``import_mesh`` and ``run_simulation`` methods of the product instance

.. figure:: /_static/images/usage_saf_ex_fluent_product_instance_output_4.png
  :width: 100%

  Status after shutting down the product instance


.. _saf-ex-fluent-product-instance-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

.. note::
    This example requires the Fluent 2025 R2 Service Pack 4 (25R2 SP4) product to be installed on your machine.
    To work with a Fluent product instance, be sure to install the ``core-pim`` and ``instance-management-fluent`` extras from the ``ansys-saf-sdk`` package. You can do this by manually editing your ``pyproject.toml``.

    .. code-block:: toml

        ansys-saf-sdk = {version = "^0.2.0", extras = ["core-pim", "instance-management-fluent"]}

    This will install the supported version of ``ansys-fluent-core`` to control the Fluent product instances.
    This example uses PIM as the product instance management system. If you want to use HPS instead, replace the ``core-pim`` extra with ``core-hps``.
    For more information, see :ref:`instance_management_configuration`.


.. _saf-ex-fluent-product-instance-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To create a product instance manager for Fluent products and interact with it, work through the following sequence of sections.


.. _saf-ex-fluent-product-instance-backend:

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

.. key-concept:: Event stream

    ``self.transaction.raise_event()`` publishes a message on a named **stream**. The frontend
    subscribes to that stream with an event listener, which lets a long-running transaction
    report its progress without blocking the UI.

.. dropdown:: Define the step model
  :open:

  * There are two transactions that are used to manage the product instance lifecycle: ``launch_fluent`` and ``shutdown_instance``.

    * The first one initializes the product instance, while the second one shuts it down.
    * The ``launch_fluent`` long-running transaction is decorated with ``@create_instance`` to create an instance of the Fluent product manager, in this case, ``Fluent3DDPSolverManager``.
    * The ``shutdown_instance`` transaction is used to shut down the Fluent instance.

  * The other two transactions, ``import_mesh`` and ``run_simulation``, are used to import a mesh and to run a solver simulation, respectively.

  .. code-block:: python
    :lineno-start: 5
    :caption: ``fluent_step.py``

    from ansys.bdm.api import NO_ENTITY, EntityHandle
    from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
    from ansys.saf.glow.solution.beta.fluent import Fluent3DDPSolverManager


    class FluentInstanceStep(StepModel):
        """Step to manage the Fluent 3DDP Solver instance."""

        version: str = "252"
        max_temperature_file: EntityHandle = NO_ENTITY
        simulation_output: EntityHandle = NO_ENTITY

        fluent_output_file: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(download=["version"]))
        @create_instance("fluent_3ddp_solver_instance", Fluent3DDPSolverManager)
        @long_running
        def launch_fluent(self, fluent_3ddp_solver_instance: Fluent3DDPSolverManager) -> None:
            """Initialize the Fluent 3DDP Solver instance."""
            self.transaction.raise_event(message="Clear Messages", stream_name="fluent-output-stream")
            self.transaction.raise_event(
                message="Initializing Fluent 3DDP Solver instance.", stream_name="fluent-output-stream"
            )
            try:
                fluent_3ddp_solver_instance.initialize(version=self.version)
            except Exception as e:
                self.transaction.raise_event(message="Fluent initialization failed", stream_name="fluent-instance-stream")
                self.transaction.raise_event(
                    message=f"Fluent initialization failed: {e}", stream_name="fluent-output-stream"
                )
                return
            self.transaction.raise_event(message="Fluent initialized.", stream_name="fluent-instance-stream")
            self.transaction.raise_event(message="Fluent initialized.", stream_name="fluent-output-stream")

        @transaction(self=StepSpec(upload=["fluent_output_file"]))
        @instance("fluent_3ddp_solver_instance")
        @long_running
        def import_mesh(self, fluent_3ddp_solver_instance: Fluent3DDPSolverManager) -> None:
            """Import the mesh into the Fluent 3DDP Solver instance."""
            self.transaction.raise_event(message="Clear Messages", stream_name="fluent-output-stream")
            self.transaction.raise_event(message="Starting to import the mesh.", stream_name="fluent-output-stream")

            filepath = self.storage_scope.get_storage_root() / "fluent_output.txt"

            def on_trancript(transcript):
                try:
                    filepath.write_text(str(transcript))
                    self.fluent_output_file = self.storage_scope.store(filepath)
                    self.transaction.raise_event(message=str(transcript), stream_name="fluent-output-stream")
                except Exception as e:
                    self.transaction.raise_event(message=f"Mesh import failed: {e}", stream_name="fluent-output-stream")
                    self.transaction.raise_event(message="Mesh import failed.", stream_name="fluent-instance-stream")

            session = fluent_3ddp_solver_instance.instance

            session.transcript.register_callback(on_trancript)

            self.transaction.raise_event(message="Started importing Mesh", stream_name="fluent-output-stream")

            # Import mesh
            try:
                example_file = self.transaction.get_asset_entity_handle("brake.msh.h5")
                example_file_path = fluent_3ddp_solver_instance.storage_scope.get_cached(example_file)
                session.tui.file.read_case(str(example_file_path))  # type: ignore
            except Exception as e:
                self.transaction.raise_event(message=f"Mesh import failed: {e}", stream_name="fluent-output-stream")
                self.transaction.raise_event(message="Mesh import failed.", stream_name="fluent-instance-stream")
                return

            # Define models and material
            session.tui.define.models.energy("yes", "no", "no", "no", "yes")  # type: ignore
            session.tui.define.models.unsteady_2nd_order_bounded("yes")  # type: ignore
            session.tui.define.materials.copy("solid", "steel")  # type: ignore

            # Solve only energy equation (conduction)
            session.tui.solve.set.equations("flow", "no", "kw", "no")  # type: ignore

            # Define disc rotation
            session.tui.define.boundary_conditions.set.solid(  # type: ignore
                "disc1",
                "disc2",
                "()",
                "solid-motion?",
                "yes",
                "solid-omega",
                "no",
                -15.79,
                "solid-x-origin",
                "no",
                -0.035,
                "solid-y-origin",
                "no",
                -0.821,
                "solid-z-origin",
                "no",
                0.045,
                "solid-ai",
                "no",
                0,
                "solid-aj",
                "no",
                1,
                "solid-ak",
                "no",
                0,
                "q",
            )

            # Apply frictional heating on pad-disc surfaces
            session.tui.define.boundary_conditions.set.wall(  # type: ignore
                "wall_pad-disc1",
                "wall-pad-disc2",
                "()",
                "wall-thickness",
                "no",
                0.002,
                "q-dot",
                "no",
                2e9,
                "q",
            )

            # session.file.

            # Apply convection cooling on outer surfaces due to air flow
            session.tui.define.boundary_conditions.set.wall(  # type: ignore
                "wall-disc*",
                "wall-geom*",
                "()",
                "thermal-bc",
                "yes",
                "convection",
                "convective-heat-transfer-coefficient",
                "no",
                100,
                "q",
            )

            # Initialize flow
            session.tui.solve.initialize.initialize_flow()  # type: ignore

            session.transcript.stop()

            self.transaction.raise_event(message="Mesh import success.", stream_name="fluent-instance-stream")
            self.transaction.raise_event(message="Mesh import success.", stream_name="fluent-output-stream")

        @transaction(self=StepSpec(upload=["simulation_output", "max_temperature_file", "fluent_output_file"]))
        @instance("fluent_3ddp_solver_instance")
        @long_running
        def run_simulation(self, fluent_3ddp_solver_instance: Fluent3DDPSolverManager) -> None:
            """Run the simulation in the Fluent 3DDP Solver instance."""
            filepath = self.storage_scope.get_storage_root() / "fluent_output.txt"

            self.transaction.raise_event(message="Clear Messages", stream_name="fluent-output-stream")
            self.transaction.raise_event(message="Starting to run the simulation.", stream_name="fluent-output-stream")

            def on_trancript(transcript):
                try:
                    filepath.write_text(str(transcript))
                    self.fluent_output_file = self.storage_scope.store(filepath)
                    self.transaction.raise_event(message=str(transcript), stream_name="fluent-output-stream")
                except Exception as e:
                    self.transaction.raise_event(message=f"Run simulation failed: {e}", stream_name="fluent-output-stream")
                    self.transaction.raise_event(message="Run simulation failed.", stream_name="fluent-instance-stream")

            session = fluent_3ddp_solver_instance.instance

            session.transcript.register_callback(on_trancript)

            try:
                # Post processing setup
                session.tui.solve.report_definitions.add(  # type: ignore
                    "max-pad-temperature",  # type: ignore
                    "volume-max",
                    "field",
                    "temperature",
                    "zone-names",  # type: ignore
                    "geom-1-innerpad",
                    "geom-1-outerpad",
                )
                session.tui.solve.report_definitions.add(  # type: ignore
                    "max-disc-temperature",  # type: ignore
                    "volume-max",
                    "field",
                    "temperature",
                    "zone-names",  # type: ignore
                    "disc1",
                    "disc2",
                )

                session.tui.solve.report_plots.add(  # type: ignore
                    "max-temperature",  # type: ignore
                    "report-defs",
                    "max-pad-temperature",
                    "max-disc-temperature",
                    "()",  # type: ignore
                )

                max_temperature_file_path = (
                    fluent_3ddp_solver_instance.storage_scope.get_storage_root() / "max-temperature.out"
                )
                session.tui.solve.report_files.add(  # type: ignore
                    "max-temperature",  # type: ignore
                    "report-defs",
                    "max-pad-temperature",
                    "max-disc-temperature",
                    "()",  # type: ignore
                    "file-name",
                    str(max_temperature_file_path),
                )

                session.results.graphics.contour["contour-1"] = {  # type: ignore
                    "boundary_values": True,
                    "color_map": {
                        "color": "field-velocity",
                        "font_automatic": True,
                        "font_name": "Helvetica",
                        "font_size": 0.032,
                        "format": "%0.2e",
                        "length": 0.54,
                        "log_scale": False,
                        "position": 1,
                        "show_all": True,
                        "size": 100,
                        "user_skip": 9,
                        "visible": True,
                        "width": 6.0,
                    },
                    "coloring": {"smooth": False},
                    "contour_lines": False,
                    "display_state_name": "None",
                    "draw_mesh": False,
                    "field": "temperature",
                    "filled": True,
                    "mesh_object": "",
                    "node_values": True,
                    "range_option": {"auto_range_on": {"global_range": True}},
                }

                session.tui.display.objects.create(  # type: ignore
                    "contour",  # type: ignore
                    "temperature",
                    "field",
                    "temperature",
                    "surface-list",  # type: ignore
                    "wall*",
                    "()",
                    "color-map",
                    "format",
                    "%0.1f",
                    "q",
                    "range-option",
                    "auto-range-off",
                    "minimum",
                    300,
                    "maximum",
                    400,
                    "q",
                    "q",
                )

                session.tui.display.views.restore_view("top")  # type: ignore
                session.tui.display.views.camera.zoom_camera(2)  # type: ignore
                session.tui.display.views.save_view("animation-view")  # type: ignore

                session.tui.solve.animate.objects.create(  # type: ignore
                    "animate-temperature",  # type: ignore
                    "animate-on",
                    "temperature",
                    "frequency-of",
                    "flow-time",  # type: ignore
                    "flow-time-frequency",
                    0.05,
                    "view",
                    "animation-view",
                    "q",
                )

                # Run simulation
                simulation_output_path = fluent_3ddp_solver_instance.storage_scope.get_storage_root() / "brake-final.cas.h5"
                session.tui.solve.set.transient_controls.time_step_size(0.01)  # type: ignore
                session.tui.solve.dual_time_iterate(20, 5)  # type: ignore
                session.tui.file.write_case_data(str(simulation_output_path))  # type: ignore

                self.simulation_output = fluent_3ddp_solver_instance.storage_scope.store(simulation_output_path)
                self.max_temperature_file = fluent_3ddp_solver_instance.storage_scope.store(max_temperature_file_path)

                output = {
                    "simulation_output": self.storage_scope.get_cached(self.simulation_output),
                    "max_temperature_file": self.storage_scope.get_cached(self.max_temperature_file),
                }

            except Exception as e:
                self.transaction.raise_event(message=f"Run simulation failed: {e}", stream_name="fluent-output-stream")
                self.transaction.raise_event(message="Run simulation failed.", stream_name="fluent-instance-stream")
                return

            self.transaction.raise_event(message="Run simulation success.", stream_name="fluent-instance-stream")
            self.transaction.raise_event(message="Run simulation success.", stream_name="fluent-output-stream")

        @transaction()
        @instance("fluent_3ddp_solver_instance")
        def shutdown_instance(self, fluent_3ddp_solver_instance: Fluent3DDPSolverManager) -> None:
            """Shutdown the Fluent 3DDP Solver instance."""
            self.transaction.raise_event(message="Clear Messages", stream_name="fluent-output-stream")
            self.transaction.raise_event(message="Starting to shutdown the instance.", stream_name="fluent-output-stream")

            try:
                fluent_3ddp_solver_instance.shutdown()
            except Exception as e:
                self.transaction.raise_event(message="Fluent shutdown failed.", stream_name="fluent-instance-stream")
                self.transaction.raise_event(message=f"Fluent shutdown failed: {e}", stream_name="fluent-output-stream")
                return
            self.transaction.raise_event(message="Fluent Shutdown.", stream_name="fluent-instance-stream")
            self.transaction.raise_event(message="Fluent instance shutdown complete.", stream_name="fluent-output-stream")


.. _saf-ex-fluent-product-instance-frontend:

:material-outlined:`web;1.25em;sd-text-primary` Frontend
----------------------------------------------------------

Expose the solution definition in the UI.

.. key-concept:: Callback

    A **callback** is a Dash-decorated function that fires in response to a UI event. In a
    SAF solution, callbacks reach the backend through ``project.steps.<step_name>``, read or
    write fields, and invoke transaction methods — no manual HTTP calls needed.

.. key-concept:: Event listener

    ``DashClient.create_event_listener()`` subscribes a page to a backend stream. Each message
    fires a callback, which is how the solver transcript and the button states stay in sync with
    a long-running transaction.

.. dropdown:: Define the step layout
  :open:

  The user interface has four main buttons. Each one triggers a transaction in the step model.

  .. code-block:: python
    :lineno-start: 4
    :caption: layout from ``fluent_instance_page.py``

    from typing import List, Tuple

    from ansys.saf.glow.client import DashClient, callback
    import ansys_web_components_dash as AwcDash
    from ansys_web_components_dash import AwcDashEnum
    from dash_extensions.enrich import Input, Output, State, dcc, html, no_update
    from dash_iconify import DashIconify
    import dash_mantine_components as dmc

    from ansys.solutions.examples.solution.definition import ExamplesSolution, FluentInstanceStep


    def layout(step: FluentInstanceStep):
        """Layout of the first step UI."""
        logs_container = AwcDash.Card(
            [
                html.Div(
                    dmc.Title(f"Console Logs", order=3),
                ),
                dmc.Space(h=20),
                html.Div(
                    html.Pre(
                        id="console-logs",
                        style={"whiteSpace": "pre-wrap", "wordBreak": "break-all", "fontSize": "10px"},
                    ),
                    style={
                        "height": "600px",
                        "width": "100%",
                    },
                ),
            ],
            elevation=AwcDashEnum.ElevationSize.SMALL.value,
            borderRadius=AwcDashEnum.BorderRadius.SMALL.value,
            awcSizingWidth="100%",
            padding=AwcDashEnum.Size._2x.value,
        )
        return html.Div(
            [
                html.Div(
                    "⚠️ This example requires Fluent 2025 R2 Service Pack 4 (25R2 SP4) to run.",
                    style={
                        "backgroundColor": "#fff3cd",
                        "color": "#856404",
                        "padding": "12px",
                        "border": "1px solid #ffeeba",
                        "textAlign": "center",
                        "fontWeight": "bold",
                        "marginBottom": "10px",
                    },
                ),
                html.Br(),
                html.H1(
                    "Fluent Instance Manager", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}
                ),
                html.Br(),
                html.Hr(className="my-2"),
                html.Br(),
                html.P(
                    "This example demonstrates how to leverage PIM to control Fluent. Click the Initialize button to\
                    start the instance. A transaction method will start Fluent which can be used across all transaction\
                    methods of the solution. Run Fluent operations with the Import Mesh and\
                    Run Simulation buttons. Close Fluent using the Shutdown button.",
                    className="lead",
                    style={"font-size": "20px"},
                ),
                html.Div(
                    [
                        dmc.Button(
                            "Launch Fluent",
                            id="launch_fluent_button",
                            variant="filled",
                            radius="xl",
                            style={"color": "#FFFFFF", "width": "20%"},
                            leftIcon=DashIconify(icon="streamline:startup-solid"),
                        ),
                        dmc.Button(
                            "Shutdown Fluent",
                            id="shutdown_fluent_button",
                            variant="filled",
                            radius="xl",
                            style={"color": "#FFFFFF", "width": "200px", "marginLeft": "20px"},
                            leftIcon=DashIconify(icon="mdi:shutdown"),
                            disabled=True,
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
                html.P(
                    "Once the instance is created, you can use the buttons below to import a mesh and run a simulation.",
                    className="lead",
                    style={"font-size": "20px"},
                ),
                html.Br(),
                dmc.Grid(
                    [
                        dmc.Col(
                            dmc.Stack(
                                [
                                    dmc.Button(
                                        "Import Mesh",
                                        id="import_mesh_button",
                                        variant="filled",
                                        radius="xl",
                                        style={"color": "#FFFFFF", "width": "50%"},
                                        leftIcon=DashIconify(icon="game-icons:mesh-network"),
                                        disabled=True,
                                    ),
                                    html.Div(id="import_mesh_result", children=""),
                                    dmc.Button(
                                        "Run Simulation",
                                        id="run_simulation_button",
                                        variant="filled",
                                        radius="xl",
                                        style={"color": "#FFFFFF", "width": "50%"},
                                        leftIcon=DashIconify(icon="codicon:run-all"),
                                        disabled=True,
                                    ),
                                    html.Div(id="run_simulation_result", children=""),
                                ],
                                align="center",
                            ),
                            span=6,
                        ),
                        dmc.Col(logs_container, span=6),
                    ],
                    grow=True,
                    gutter="xs",
                ),
                html.Div(
                    [
                        DashClient.create_event_listener(
                            step, id="fluent-instance-listener", stream_name="fluent-instance-stream"
                        )
                    ]
                ),
                html.Div(
                    [DashClient.create_event_listener(step, id="output-listener", stream_name="fluent-output-stream")]
                ),
                dcc.Store(id="ui-button-state", storage_type="session"),
                dmc.NotificationsProvider(
                    dmc.Container(id="notification-container", children=[]),
                    position="bottom-left",  # can be 'top-left', 'bottom-left', etc.
                ),
            ],
        )

.. dropdown:: Define the initialization of the product instance callback
  :open:

  * When the :guilabel:`Initialize Instance` button is clicked, the initialization callback is activated.
  * The callback starts the long-running transaction to initialize the product instance.
  * After the product is initialized, it updates the UI with the result.

  .. code-block:: python
    :lineno-start: 96
    :caption: initialization callback from ``fluent_instance_page.py``

    @callback(
        Output("launch_fluent_button", "loading", allow_duplicate=True),
        Input("launch_fluent_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def init(n_clicks: int, pathname: str) -> bool:
        """Initialize the Fluent instance."""
        project = DashClient[ExamplesSolution].get_project(pathname)
        step = project.steps.fluent_step
        step.launch_fluent()
        return True

.. dropdown:: Define the import_mesh transaction button
  :open:

  * The callback starting the transaction imports a mesh and defines the models and boundary conditions.
  * All the logs generated by the method are printed in the ``console-logs`` container.

  .. code-block:: python
    :lineno-start: 110
    :caption: import_mesh transaction button callback from ``fluent_instance_page.py``

    @callback(
        Output("import_mesh_button", "loading", allow_duplicate=True),
        Input("import_mesh_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def import_mesh(n_clicks: int, pathname: str):
        """Import a mesh into the Fluent instance."""
        project = DashClient[ExamplesSolution].get_project(pathname)
        step = project.steps.fluent_step
        step.import_mesh()
        return True

.. dropdown:: Define the run_simulation transaction button
  :open:

  * The callback starting the transaction runs a Fluent 3D solver simulation.
  * All the logs generated by the method are printed in the ``console-logs`` container.

  .. code-block:: python
    :lineno-start: 124
    :caption: run_simulation transaction button callback from ``fluent_instance_page.py``

    @callback(
        Output("run_simulation_button", "loading", allow_duplicate=True),
        Input("run_simulation_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def run_simulation(n_clicks: int, pathname: str):
        """Run the Fluent simulation."""
        project = DashClient[ExamplesSolution].get_project(pathname)
        step = project.steps.fluent_step
        step.run_simulation()
        return True

.. dropdown:: Define the shutdown transaction button
  :open:

  * When the :guilabel:`Shutdown Instance` button is clicked, the shutdown callback is activated.
  * The callback starts the transaction to shut down the product instance.

  .. code-block:: python
    :lineno-start: 138
    :caption: shutdown transaction button callback from ``fluent_instance_page.py``

    @callback(
        Input("shutdown_fluent_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def shutdown(n_clicks: int, pathname: str):
        """Shutdown the Fluent instance."""
        if n_clicks is not None:
            project = DashClient[ExamplesSolution].get_project(pathname)
            step = project.steps.fluent_step
            step.shutdown_instance()


    @callback(
        Output("shutdown_fluent_button", "loading", allow_duplicate=True),
        Input("shutdown_fluent_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def load_shutdown(n_clicks: int, pathname: str):
        """Shutdown the Fluent instance."""
        return True

.. dropdown:: Define the logs system.
  :open:

  * Create the ``logs_container`` component and ``output-listener`` stream to display logs in the UI, as show in the layout.
  * To display the method logs from the backend, the ``output-listener`` stream must be called.
  * When the stream receives a message, the callback is activated and updates the logs container as expected.

  .. code-block:: python
    :lineno-start: 138
    :caption: display_the_fluent_output callback from ``fluent_instance_page.py``

    @callback(
        Output("console-logs", "children"),
        Input("output-listener", "message"),
        State("console-logs", "children"),
        State("url", "pathname"),
    )
    def display_the_fluent_output(message: dict, current_logs: str, pathname: str) -> str:
        """Display fluent output."""
        if message:
            new_content = message["data"].strip('"').replace("\\n", "\n")
            if new_content == "Clear Messages":
                return ""
            combined = (current_logs or "") + "\n" + new_content
            return combined
        return current_logs

.. dropdown:: Define the notification system.
  :open:

  * Create the ``dmc.NotificationsProvider`` and ``fluent-instance-listener`` stream component to display notifications in the UI, as show in the layout.
  * To display notifications when a method succeeds or fails, the ``fluent-instance-listener`` stream must be called.
  * When the stream receives a message, the callback is activated and generates the appropriate notification in the UI.

  .. code-block:: none
    :lineno-start: 138
    :caption: update_ui callback from ``fluent_instance_page.py``

    @callback(
        [
            Output(button_id, "loading")
            for button_id in [
                "launch_fluent_button",
                "shutdown_fluent_button",
                "import_mesh_button",
                "run_simulation_button",
            ]
        ],
        [
            Output(button_id, "disabled")
            for button_id in [
                "launch_fluent_button",
                "shutdown_fluent_button",
                "import_mesh_button",
                "run_simulation_button",
            ]
        ],
        Output("notification-container", "children"),
        Output("ui-button-state", "data"),
        Input("fluent-instance-listener", "message"),
        Input("url", "pathname"),
        State("ui-button-state", "data"),
    )
    def update_ui(
        message: dict, pathname: str, prev_state: dict | None
    ) -> Tuple[List[bool], List[bool], dmc.Notification, dict]:
        """Update the ui."""
        button_ids = ["launch_fluent_button", "shutdown_fluent_button", "import_mesh_button", "run_simulation_button"]
        default_states = {
            "launch_fluent_button": {
                "loading": False,
                "disabled": False,
            },
            "shutdown_fluent_button": {
                "loading": False,
                "disabled": True,
            },
            "import_mesh_button": {
                "loading": False,
                "disabled": True,
            },
            "run_simulation_button": {
                "loading": False,
                "disabled": True,
            },
        }
        notification = dmc.Notification(
            id="my-notification",
            title="Success",
            message="PlaceHolder",
            color="green",
            action="show",
            icon=None,
        )
        if prev_state is None:
            prev_state = default_states.copy()
        if message:
            message_content = message["data"].strip('"').replace("\\n", "\n")
            if message_content == "Fluent initialized.":
                prev_state["launch_fluent_button"]["disabled"] = True
                prev_state["shutdown_fluent_button"]["disabled"] = False
                prev_state["import_mesh_button"]["disabled"] = False
                notification.message = "Fluent instance launched successfully!"
                notification.icon = DashIconify(icon="streamline:startup-solid")
            elif message_content == "Fluent initialization failed":
                prev_state["launch_fluent_button"]["disabled"] = False
                notification.message = "Fluent initialization failed. Please check the logs."
                notification.icon = DashIconify(icon="streamline:startup-solid")
                notification.color = "red"
                notification.title = "Error"
            elif message_content == "Mesh import success.":
                prev_state["import_mesh_button"]["disabled"] = True
                prev_state["run_simulation_button"]["disabled"] = False
                notification.message = "Mesh imported successfully!"
                notification.icon = DashIconify(icon="game-icons:mesh-network")
            elif message_content == "Mesh import failed.":
                prev_state["import_mesh_button"]["disabled"] = False
                notification.message = "Mesh import failed. Please check the logs."
                notification.icon = DashIconify(icon="game-icons:mesh-network")
                notification.color = "red"
                notification.title = "Error"
            elif message_content == "Run simulation success.":
                notification.message = "Simulation run successfully!"
                notification.icon = DashIconify(icon="codicon:run-all")
            elif message_content == "Run simulation failed.":
                notification.message = "Simulation run failed. Please check the logs."
                notification.icon = DashIconify(icon="codicon:run-all")
                notification.color = "red"
                notification.title = "Error"
            elif message_content == "Fluent Shutdown.":
                prev_state = default_states
                notification.message = "Fluent instance shutdown successfully!"
                notification.icon = DashIconify(icon="mdi:shutdown")
            elif message_content == "Fluent shutdown failed.":
                prev_state["shutdown_fluent_button"]["disabled"] = False
                notification.message = "Fluent instance shutdown failed. Please check the logs."
                notification.icon = DashIconify(icon="mdi:shutdown")
                notification.color = "red"
                notification.title = "Error"
        disabled_states = [prev_state[button_id]["disabled"] for button_id in button_ids]
        return (
            *[False, False, False, False],
            *disabled_states,
            notification if message else no_update,
            prev_state if prev_state else default_states,
        )

  Now that your implementation is complete, continue to the :ref:`saf-ex-fluent-product-instance-testing` section.


.. _saf-ex-fluent-product-instance-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-fluent-product-instance-feature-highlight>` section.
