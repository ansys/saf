.. _saf-ex-mechanical-product-instance:


Mechanical Product Instance Manager
###################################

.. topic:: Objective

  Drive an Ansys Mechanical product from a solution. Start the product instance in a
  long-running transaction, upload a geometry file, run a custom Mechanical script that solves
  a static structural analysis, download the ``solve.out`` file, then shut the instance down.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-mechanical-product-instance-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

Ansys Mechanical is a powerful simulation tool for structural analysis, supporting a wide range of applications including stress analysis, vibration, thermal, and fatigue simulations.

This example shows how to create a **product instance manager** for Mechanical products using SAF. The product instance manager enables management of the Mechanical product instance lifecycle, including starting, stopping, and accessing the product's API.

In this example, you learn how to:

- :material-outlined:`rocket_launch;1.25em;saf-objective-icon` Start a product instance from a
  **long-running transaction** decorated with ``@create_instance``.
- :material-outlined:`hub;1.25em;saf-objective-icon` Reuse the running instance in the other
  **transaction methods** through the ``@instance`` decorator.
- :material-outlined:`api;1.25em;saf-objective-icon` Call the **Mechanical API** to upload a
  geometry file and run a custom Python script that solves the model.
- :material-outlined:`cloud_upload;1.25em;saf-objective-icon` Move files between the solution
  and the product with the ``storage_scope`` and an ``EntityHandle`` field.
- :material-outlined:`stream;1.25em;saf-objective-icon` Publish progress on named **event
  streams** with ``transaction.raise_event``.
- :material-outlined:`bolt;1.25em;saf-objective-icon` Wire one **callback** per button and use
  **event listeners** to refresh the console logs and the notifications.

When you complete this example, you can expect the following output in the solution UI:

.. _saf-ex-mechanical-product-instance-output-1:

.. figure:: /_static/images/usage_saf_ex_mechanical_product_instance_output_1.png
  :width: 100%

  Status before the initialization of the product instance

.. figure:: /_static/images/usage_saf_ex_mechanical_product_instance_output_2.png
  :width: 100%

  Status after the initialization of the product instance

.. figure:: /_static/images/usage_saf_ex_mechanical_product_instance_output_3.png
  :width: 100%

  Status after calling the ``run_script`` and ``download_output_solve`` methods of the product instance

.. figure:: /_static/images/usage_saf_ex_mechanical_product_instance_output_4.png
  :width: 100%

  Status after shutting down the product instance


.. _saf-ex-mechanical-product-instance-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

.. note::
    This example requires the Mechanical 2025 R2 Service Pack 4 (25R2 SP4) product to be installed on your machine.
    To work with a Mechanical product instance, be sure to install the ``core-pim`` and ``instance-management-mechanical`` extras from the ``ansys-saf-sdk`` package. You can do this by manually editing your ``pyproject.toml``.

    .. code-block:: toml

        ansys-saf-sdk = {version = "^0.2.0", extras = ["core-pim", "instance-management-mechanical"]}

    This will install the supported version of ``ansys-mechanical-core`` to control the Mechanical product instances.
    This example uses PIM as the product instance management system. If you want to use HPS instead, replace the ``core-pim`` extra with ``core-hps``.
    For more information, see :ref:`instance_management_configuration`.

Additionally, ensure that the geometry file required for the example script is available. Without this file, the script execution will fail. Place the geometry file in the appropriate directory or provide its path in the ``run_script`` callback.


.. _saf-ex-mechanical-product-instance-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To create a product instance manager for Mechanical products and interact with it, work through the following sequence of sections.


.. _saf-ex-mechanical-product-instance-backend:

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

    A transaction method reports progress with ``self.transaction.raise_event``. Each event is
    published on a named **stream**, so the frontend can react while the transaction is still
    running.

.. dropdown:: Define the step model
  :open:

  * There are two transactions that are used to manage the product instance lifecycle: ``launch_mechanical`` and ``close_mechanical``.

    * The first one initializes the product instance, while the second one shuts it down.
    * The ``launch_mechanical`` long-running transaction is decorated with ``@create_instance`` to create an instance of the Mechanical product manager, in this case, ``MechanicalManager``.
    * The ``close_mechanical`` transaction is decorated with @instance and is used to shut down the existing Mechanical instance.

  * The other two transactions, ``run_script`` and ``download_output_solve``, are used to execute a custom script and download the output file to the current working directory, respectively.

    * Both are decorated with ``@instance`` to indicate they operate on an existing product instance.

  .. code-block:: python
    :lineno-start: 5
    :caption: ``mechanical_step.py``

    from pathlib import Path
    from time import sleep

    from ansys.bdm.api import NO_ENTITY, EntityHandle
    from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
    from ansys.saf.glow.solution.beta.mechanical import MechanicalManager


    class MechanicalInstanceStep(StepModel):
        """Step to manage a Mechanical instance."""

        version: str = "252"
        example_file: EntityHandle = NO_ENTITY
        output_handle: EntityHandle = NO_ENTITY
        test_file: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(download=["version"], upload=["test_file"]))
        @create_instance("mechanical_instance", MechanicalManager)
        @long_running
        def launch_mechanical(self, mechanical_instance: MechanicalManager) -> None:
            """Launch the Mechanical instance."""
            self.transaction.raise_event(message="Clear Messages", stream_name="mechanical-output-stream")
            self.transaction.raise_event(
                message="Initializing Mechanical instance.", stream_name="mechanical-output-stream"
            )
            try:
                mechanical_instance.initialize(version=self.version)
                test_file_path = self.storage_scope.get_storage_root() / "test_file.txt"
                test_file_path.write_text("my_test_file")
                self.test_file = self.storage_scope.store(test_file_path)
            except Exception as e:
                self.transaction.raise_event(
                    message="Mechanical initialization failed", stream_name="mechanical-instance-stream"
                )
                self.transaction.raise_event(
                    message=f"Mechanical initialization failed: {e}", stream_name="mechanical-output-stream"
                )
                return
            self.transaction.raise_event(message="Mechanical initialized.", stream_name="mechanical-instance-stream")
            self.transaction.raise_event(message="Mechanical initialized.", stream_name="mechanical-output-stream")

        @transaction(self=StepSpec(download=["example_file"]))
        @instance("mechanical_instance")
        def upload_example_file_to_mechanical(self, mechanical_instance: MechanicalManager) -> None:
            """Upload the example file to Mechanical instance."""
            self.transaction.raise_event(message="Uploading file.", stream_name="mechanical-instance-stream")
            self.transaction.raise_event(message="Uploading file.", stream_name="mechanical-output-stream")

            mechanical = mechanical_instance.instance
            geometry_path = self.storage_scope.get_cached(self.example_file)
            mechanical.upload(file_name=geometry_path)  # type: ignore

        @transaction(self=StepSpec(download=["example_file"]))
        @instance("mechanical_instance")
        def initialize_variable_workflow(self, mechanical_instance: MechanicalManager) -> None:
            """Initialize the variable workflow in Mechanical instance."""
            self.transaction.raise_event(message="Clear Messages", stream_name="mechanical-output-stream")
            self.transaction.raise_event(
                message="Starting to initialize variables.", stream_name="mechanical-output-stream"
            )

            mechanical = mechanical_instance.instance

            try:
                self.transaction.raise_event(
                    message="Initializing variable workflow in Mechanical instance.", stream_name="mechanical-output-stream"
                )
                geometry_path = mechanical_instance.storage_scope.get_cached(self.example_file)
                self.transaction.raise_event(
                    message=f"Geometry path: {geometry_path}", stream_name="mechanical-output-stream"
                )
                project_directory = mechanical.project_directory  # type: ignore
                self.transaction.raise_event(
                    message=f"Project directory: {project_directory}", stream_name="mechanical-output-stream"
                )

                # Build the path relative to project directory.
                combined_path = str(Path(project_directory) / geometry_path.name)  # type: ignore
                path_in_mechanical = combined_path.replace("\\", "\\\\")
                mechanical.run_python_script(f"part_file_path='{path_in_mechanical}'")
            except Exception as e:
                self.transaction.raise_event(
                    message="Mechanical variables initialized failed.", stream_name="mechanical-instance-stream"
                )
                self.transaction.raise_event(
                    message=f"Mechanical variables initialized failed: {e}", stream_name="mechanical-output-stream"
                )
                return

        @transaction()
        @instance("mechanical_instance")
        @long_running
        def run_script(self, mechanical_instance: MechanicalManager) -> None:
            """Run a script in the Mechanical instance."""
            mechanical = mechanical_instance.instance

            self.transaction.raise_event(
                message="Running script in Mechanical instance.", stream_name="mechanical-output-stream"
            )

            try:
                # Run the script
                output = mechanical.run_python_script(
                    """
    import json

    # Section 1: Read geometry information
    geometry_import_group_11 = Model.GeometryImportGroup
    geometry_import_19 = geometry_import_group_11.AddGeometryImport()

    geometry_import_19_format = Ansys.Mechanical.DataModel.Enums.GeometryImportPreference.\
        Format.Automatic
    geometry_import_19_preferences = Ansys.ACT.Mechanical.Utilities.GeometryImportPreferences()
    geometry_import_19_preferences.ProcessNamedSelections = True
    geometry_import_19_preferences.ProcessCoordinateSystems = True

    geometry_import_19.Import(part_file_path, geometry_import_19_format, geometry_import_19_preferences)

    Model.AddStaticStructuralAnalysis()
    STAT_STRUC = Model.Analyses[0]
    CS_GRP = Model.CoordinateSystems
    ANALYSIS_SETTINGS = STAT_STRUC.Children[0]
    SOLN= STAT_STRUC.Solution

    # Section 2: Set up the unit system.

    ExtAPI.Application.ActiveUnitSystem = MechanicalUnitSystem.StandardMKS
    ExtAPI.Application.ActiveAngleUnit = AngleUnitType.Radian

    # Section 3: Define named selection and coordinate system.

    NS1 = Model.NamedSelections.Children[0]
    NS2 = Model.NamedSelections.Children[1]
    NS3 = Model.NamedSelections.Children[2]
    NS4 = Model.NamedSelections.Children[3]
    GCS = CS_GRP.Children[0]
    LCS1 = CS_GRP.Children[1]

    # Section 4: Define remote point.

    RMPT_GRP = Model.RemotePoints
    RMPT_1 = RMPT_GRP.AddRemotePoint()
    RMPT_1.Location = NS1
    RMPT_1.XCoordinate=Quantity("7 [m]")
    RMPT_1.YCoordinate=Quantity("0 [m]")
    RMPT_1.ZCoordinate=Quantity("0 [m]")

    #  Section 5: Define mesh settings.

    MSH = Model.Mesh
    MSH.ElementSize =Quantity("0.5 [m]")
    MSH.GenerateMesh()

    #  Section 6: Define boundary conditions.

    # Insert fixed support.
    FIX_SUP = STAT_STRUC.AddFixedSupport()
    FIX_SUP.Location = NS2

    # Insert frictionless support.
    FRIC_SUP = STAT_STRUC.AddFrictionlessSupport()
    FRIC_SUP.Location = NS3

    #  Section 7: Define remote force.

    REM_FRC1 = STAT_STRUC.AddRemoteForce()
    REM_FRC1.Location = RMPT_1
    REM_FRC1.DefineBy =LoadDefineBy.Components
    REM_FRC1.XComponent.Output.DiscreteValues = [Quantity("1e10 [N]")]

    #  Section 8: Define thermal condition.

    THERM_COND = STAT_STRUC.AddThermalCondition()
    THERM_COND.Location = NS4
    THERM_COND.Magnitude.Output.DefinitionType=VariableDefinitionType.Formula
    THERM_COND.Magnitude.Output.Formula="50*(20+z)"
    THERM_COND.XYZFunctionCoordinateSystem=LCS1
    THERM_COND.RangeMinimum=Quantity("-20 [m]")
    THERM_COND.RangeMaximum=Quantity("1 [m]")

    #  Section 9: Insert directional deformation.

    DIR_DEF = STAT_STRUC.Solution.AddDirectionalDeformation()
    DIR_DEF.Location = NS1
    DIR_DEF.NormalOrientation =NormalOrientationType.XAxis

    # Section 10: Add total deformation and force reaction probe.

    TOT_DEF = STAT_STRUC.Solution.AddTotalDeformation()

    # Add force reaction.
    FRC_REAC_PROBE = STAT_STRUC.Solution.AddForceReaction()
    FRC_REAC_PROBE.BoundaryConditionSelection = FIX_SUP
    FRC_REAC_PROBE.ResultSelection =ProbeDisplayFilter.XAxis

    # Section 11: Solve and get the results.

    # Solve static analysis.
    STAT_STRUC.Solution.Solve(True)

    dir_deformation_details = {
    "Minimum": str(DIR_DEF.Minimum),
    "Maximum": str(DIR_DEF.Maximum),
    "Average": str(DIR_DEF.Average),
    }

    json.dumps(dir_deformation_details)""",
                )
            except Exception as e:
                self.transaction.raise_event(message="Run Script failed.", stream_name="mechanical-instance-stream")
                self.transaction.raise_event(message=f"Run Script failed: {e}", stream_name="mechanical-output-stream")
                return

            self.transaction.raise_event(message="Run Script succeeded.", stream_name="mechanical-instance-stream")
            self.transaction.raise_event(message=f"Run Script succeeded. {output}", stream_name="mechanical-output-stream")

        @transaction(self=StepSpec(upload=["output_handle"]))
        @instance("mechanical_instance")
        def download_output_solve(self, mechanical_instance: MechanicalManager) -> None:
            """Download the output file from Mechanical instance."""
            mechanical = mechanical_instance.instance

            self.transaction.raise_event(message="Clear Messages", stream_name="mechanical-output-stream")
            self.transaction.raise_event(
                message="Downloading file to the current working directory.", stream_name="mechanical-output-stream"
            )

            try:
                solve_out_path = ""
                n = 0
                nmax = 10
                while not solve_out_path and n < nmax:
                    for file_path in mechanical.list_files():  # type: ignore
                        if file_path.find("solve.out") != -1:  # type: ignore
                            solve_out_path = file_path  # type: ignore
                            break
                    n += 1
                    sleep(0.1)
                if not solve_out_path:
                    raise RuntimeError("solve.out not found.")

                downloaded_files = mechanical.download(
                    solve_out_path, target_dir=self.storage_scope.get_storage_root()
                )  # type: ignore
                self.output_handle = self.storage_scope.store(downloaded_files[0])  # type: ignore
            except Exception as e:
                self.transaction.raise_event(message="File download failed.", stream_name="mechanical-instance-stream")
                self.transaction.raise_event(message=f"File download failed: {e}", stream_name="mechanical-output-stream")
                return

            self.transaction.raise_event(message=f"File download succeeded.", stream_name="mechanical-instance-stream")
            self.transaction.raise_event(
                message=f"File downloaded to {downloaded_files[0]}.", stream_name="mechanical-output-stream"
            )

        @transaction(self=StepSpec())
        @instance("mechanical_instance")
        def close_mechanical(self, mechanical_instance: MechanicalManager) -> None:
            """Close the Mechanical instance."""
            self.transaction.raise_event(message="Clear Messages", stream_name="mechanical-output-stream")
            self.transaction.raise_event(
                message="Starting to shutdown the instance.", stream_name="mechanical-output-stream"
            )

            try:
                mechanical_instance.shutdown()
            except Exception as e:
                self.transaction.raise_event(
                    message="Mechanical shutdown failed.", stream_name="mechanical-instance-stream"
                )
                self.transaction.raise_event(
                    message=f"Mechanical shutdown failed: {e}", stream_name="mechanical-output-stream"
                )
                return
            self.transaction.raise_event(message="Mechanical Shutdown.", stream_name="mechanical-instance-stream")
            self.transaction.raise_event(
                message="Mechanical instance shutdown complete.", stream_name="mechanical-output-stream"
            )


.. _saf-ex-mechanical-product-instance-frontend:

:material-outlined:`web;1.25em;sd-text-primary` Frontend
----------------------------------------------------------

Expose the solution definition in the UI.

.. key-concept:: Callback

    A **callback** is a Dash-decorated function that fires in response to a UI event. In a
    SAF solution, callbacks reach the backend through ``project.steps.<step_name>``, read or
    write fields, and invoke transaction methods — no manual HTTP calls needed.

.. key-concept:: Event listener

    ``DashClient.create_event_listener`` subscribes a component to an event stream raised by
    the backend. Each message received by the listener triggers a callback, so the console
    logs, the button states, and the notifications stay in sync with the running transaction.

.. dropdown:: Define the step layout
  :open:

  The user interface has four main buttons. Each one triggers a transaction in the step model.

  .. code-block:: python
    :lineno-start: 4
    :caption: layout from ``mechanical_instance_page.py``

    from pathlib import Path
    from typing import List, Tuple

    from ansys.saf.glow.client import DashClient, callback
    import ansys_web_components_dash as AwcDash
    from ansys_web_components_dash import AwcDashEnum
    from dash_extensions.enrich import Input, Output, State, dcc, html, no_update  # pyright: ignore[reportMissingTypeStubs]
    from dash_iconify import DashIconify
    import dash_mantine_components as dmc

    from ansys.solutions.examples.solution.definition import ExamplesSolution, MechanicalInstanceStep


    def layout(step: MechanicalInstanceStep) -> html.Div:
        """Layout for the Mechanical Instance Manager page."""
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
        layout = html.Div(
            [
                html.Div(
                    "⚠️ This example requires Mechanical 2025 R2 Service Pack 4 (25R2 SP4) to run.",
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
                    "Mechanical Instance Manager", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}
                ),
                html.Br(),
                html.Hr(className="my-2"),
                html.Br(),
                html.P(
                    [
                        "This example demonstrates how to leverage ",
                        html.A(
                            "PIM",
                            href="https://dev-docs.solutions.ansys.com/version/stable/user_guide/"
                            "using_ansys_products/product_instance_management/index.html",
                            target="_blank",
                            style={"color": "blue"},
                        ),
                        " to control Mechanical. Click the Launch Mechanical button to start the instance. A "
                        "transaction method will start Mechanical which can be used across all transaction "
                        "methods of the solution. Run Mechanical operations with the Run Example Script and "
                        "Download File buttons. Close Mechanical using the Shutdown button.",
                    ],
                    style={"font-size": "20px"},
                ),
                html.Div(
                    [
                        dmc.Button(
                            "Launch Mechanical",
                            id="launch_mechanical_button",
                            variant="filled",
                            radius="xl",
                            style={"color": "#FFFFFF", "width": "20%"},
                            leftIcon=DashIconify(icon="streamline:startup-solid"),
                        ),
                        dmc.Button(
                            "Shutdown Mechanical",
                            id="shutdown_mechanical_button",
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
                    "Once the instance is created, you can use the buttons below to run a script and download the\
                    output file to the current working directory.",
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
                                        "Run Example Script",
                                        id="run_script_button",
                                        variant="filled",
                                        radius="xl",
                                        style={"color": "#FFFFFF", "width": "50%"},
                                        leftIcon=DashIconify(icon="codicon:run-all"),
                                        disabled=True,
                                    ),
                                    dmc.Button(
                                        "Download File",
                                        id="download_file_button",
                                        variant="filled",
                                        radius="xl",
                                        style={"color": "#FFFFFF", "width": "50%"},
                                        leftIcon=DashIconify(icon="material-symbols:download"),
                                        disabled=True,
                                    ),
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
                            step, id="mechanical-instance-listener", stream_name="mechanical-instance-stream"
                        )
                    ]
                ),
                html.Div(
                    [
                        DashClient.create_event_listener(
                            step, id="mechanical-output-listener", stream_name="mechanical-output-stream"
                        )
                    ]
                ),
                dcc.Store(id="mechanical-ui-button-state", storage_type="session"),
                dmc.NotificationsProvider(
                    dmc.Container(id="mechanical-notification-container", children=[]),
                    position="bottom-left",
                ),
            ],
        )

        return layout

.. dropdown:: Define the initialization of the product instance callback
  :open:

  * When the :guilabel:`Initialize Instance` button is clicked, the initialization callback is activated.
  * The callback starts the long-running transaction to initialize the product instance.
  * After the product is initialized, it updates the UI with the result.

  .. code-block:: python
    :lineno-start: 173
    :caption: initialization callback from ``mechanical_instance_page.py``

    @callback(
        Output("launch_mechanical_button", "loading"),
        Input("launch_mechanical_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def init(n_clicks: int, pathname: str):
        """Initialize the Mechanical instance."""
        if n_clicks:
            project = DashClient[ExamplesSolution].get_project(pathname)
            step = project.steps.mechanical_step
            step.launch_mechanical()
            return True

.. dropdown:: Define the run_script transaction button
  :open:

  * The callback starting the transaction runs a custom script in the Mechanical instance.
  * To run the script, ensure that the example file is available in the project storage.
  * All the logs generated by the method are printed in the ``console-logs`` container.

  .. code-block:: python
    :lineno-start: 188
    :caption: run_script transaction button callback from ``mechanical_instance_page.py``

    def handle_mechanical_step(project, file_path: Path):
        """Handle all operations related to the Mechanical step.run_script."""
        step = project.steps.mechanical_step
        with project.get_storage_scope() as storage_scope, Path(
            file_path,
        ).open("rb") as f:
            step.example_file = storage_scope.store_stream(f.read(), Path("example_01_geometry.agdb"))
        step.upload_example_file_to_mechanical()
        step.initialize_variable_workflow()
        step.run_script()


    @callback(
        Output("mechanical-notification-container", "children"),
        Input("run_script_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def run_script(n_clicks: int, pathname: str) -> dmc.Notification | None:
        """Run a script in the Mechanical instance."""
        project = DashClient[ExamplesSolution].get_project(pathname)
        file_path = Path(__file__).parent.parent.parent.parent / "solution/method_assets/example_01_geometry.agdb"
        if not file_path.exists():
            return dmc.Notification(
                id="my-notification",
                title="File not found",
                message="Geometry file not found. Please check the file path.",
                color="red",
                action="show",
                icon=DashIconify(icon="codicon:run-all"),
            )

        if n_clicks:
            handle_mechanical_step(project, file_path)

        return no_update

.. dropdown:: Define the download_file transaction button
  :open:

  * The callback starting the transaction downloads the output file from the Mechanical instance to the current working directory.
  * All the logs generated by the method are printed in the ``console-logs`` container.

  .. code-block:: python
    :lineno-start: 229
    :caption: download_file transaction button callback from ``mechanical_instance_page.py``

    @callback(
        Input("download_file_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def download_file(n_clicks: int, pathname: str):
        """Download a file from the Mechanical instance."""
        if n_clicks:
            project = DashClient[ExamplesSolution].get_project(pathname)
            step = project.steps.mechanical_step
            step.download_output_solve()


    @callback(
        Output("download_file_button", "loading", allow_duplicate=True),
        Input("download_file_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def load_mechanical_download(n_clicks: int, pathname: str):
        """Set loading state for the download file button."""
        return True

.. dropdown:: Define the shutdown transaction button
  :open:

  * When the :guilabel:`Shutdown Instance` button is clicked, the shutdown callback is activated.
  * The callback starts the transaction to shut down the product instance.

  .. code-block:: python
    :lineno-start: 253
    :caption: shutdown transaction button callback from ``mechanical_instance_page.py``

    @callback(
        Input("shutdown_mechanical_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def shutdown(n_clicks: int, pathname: str):
        """Shutdown the Mechanical instance."""
        if n_clicks is not None:
            project = DashClient[ExamplesSolution].get_project(pathname)
            step = project.steps.mechanical_step
            step.close_mechanical()


    @callback(
        Output("shutdown_mechanical_button", "loading", allow_duplicate=True),
        Input("shutdown_mechanical_button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def load_mechanical_shutdown(n_clicks: int, pathname: str):
        """Set loading state for the shutdown button."""
        return True

.. dropdown:: Define the logs system.
  :open:

  * Create the ``logs_container`` component and an event listener for the ``mechanical-output-listener`` stream to display logs in the UI, as shown in the layout.
  * The method logs will be received through the ``mechanical-output-listener`` listener.
  * When the listener receives a message, the callback is activated and updates the logs container as expected.

  .. code-block:: python
    :lineno-start: 277
    :caption: display_the_mechanical_output callback from ``mechanical_instance_page.py``

    @callback(
        Output("console-logs", "children"),
        Input("mechanical-output-listener", "message"),
        State("console-logs", "children"),
        State("url", "pathname"),
    )
    def display_the_mechanical_output(message: dict, current_logs: str, pathname: str) -> str:
        """Display mechanical output."""
        if message:
            new_content = message["data"].strip('"').replace("\\n", "\n")
            if new_content == "Clear Messages":
                return ""
            combined = (current_logs or "") + "\n" + new_content
            return combined
        return current_logs

.. dropdown:: Define the notification system.
  :open:

  * Create the ``dmc.NotificationsProvider`` and an event listener for the ``mechanical-instance-listener`` stream to display notifications in the UI, as shown in the layout.
  * To display notifications when a method succeeds or fails, the ``mechanical-instance-listener`` must be triggered.
  * When the listener receives a message, the callback is activated and generates the appropriate notification in the UI.

  .. code-block:: python
    :lineno-start: 294
    :caption: update_mechanical_ui callback from ``mechanical_instance_page.py``

    @callback(
        [
            Output(button_id, "loading")
            for button_id in [
                "launch_mechanical_button",
                "shutdown_mechanical_button",
                "run_script_button",
                "download_file_button",
            ]
        ],
        [
            Output(button_id, "disabled")
            for button_id in [
                "launch_mechanical_button",
                "shutdown_mechanical_button",
                "run_script_button",
                "download_file_button",
            ]
        ],
        Output("mechanical-notification-container", "children"),
        Output("mechanical-ui-button-state", "data"),
        Input("mechanical-instance-listener", "message"),
        Input("url", "pathname"),
        State("mechanical-ui-button-state", "data"),
    )
    def update_mechanical_ui(
        message: dict, pathname: str, prev_state: dict | None
    ) -> Tuple[List[bool], List[bool], dmc.Notification, dict]:
        """Update the ui."""
        button_ids = ["launch_mechanical_button", "shutdown_mechanical_button", "run_script_button", "download_file_button"]
        default_states = {
            "launch_mechanical_button": {
                "loading": False,
                "disabled": False,
            },
            "shutdown_mechanical_button": {
                "loading": False,
                "disabled": True,
            },
            "run_script_button": {
                "loading": False,
                "disabled": True,
            },
            "download_file_button": {
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
            if message_content == "Mechanical initialized.":
                prev_state["launch_mechanical_button"]["disabled"] = True
                prev_state["shutdown_mechanical_button"]["disabled"] = False
                prev_state["run_script_button"]["disabled"] = False
                notification.message = "Mechanical instance launched successfully!"
                notification.icon = DashIconify(icon="streamline:startup-solid")
            elif message_content == "Mechanical initialization failed":
                prev_state["launch_mechanical_button"]["disabled"] = False
                notification.message = "Mechanical initialization failed. Please check the logs."
                notification.icon = DashIconify(icon="streamline:startup-solid")
                notification.color = "red"
                notification.title = "Error"
            elif message_content == "Uploading file.":
                notification.action = "hide"
                disabled_states = [prev_state[button_id]["disabled"] for button_id in button_ids]
                return (
                    *[False, False, True, False],
                    *disabled_states,
                    notification if message else no_update,
                    prev_state if prev_state else default_states,
                )
            elif message_content == "Run Script succeeded.":
                prev_state["run_script_button"]["disabled"] = True
                prev_state["download_file_button"]["disabled"] = False
                notification.message = "Script run successfully!"
                notification.icon = DashIconify(icon="codicon:run-all")
            elif message_content == "Mechanical variables initialized failed." or message_content == "Run Script failed.":
                prev_state["run_script_button"]["disabled"] = False
                notification.message = "Script run failed. Please check the logs."
                notification.icon = DashIconify(icon="codicon:run-all")
                notification.color = "red"
                notification.title = "Error"
            elif message_content == "File download succeeded.":
                notification.message = "File download succeeded!"
                notification.icon = DashIconify(icon="material-symbols:download")
            elif message_content == "File download failed.":
                notification.message = "File download failed. Please check the logs."
                notification.icon = DashIconify(icon="materials-symbols:download")
                notification.color = "red"
                notification.title = "Error"
            elif message_content == "Mechanical Shutdown.":
                prev_state = default_states
                notification.message = "Mechanical instance shutdown successfully!"
                notification.icon = DashIconify(icon="mdi:shutdown")
            elif message_content == "Mechanical shutdown failed.":
                prev_state["shutdown_mechanical_button"]["disabled"] = False
                notification.message = "Mechanical instance shutdown failed. Please check the logs."
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

  Now that your implementation is complete, continue to the :ref:`saf-ex-mechanical-product-instance-testing` section.


.. _saf-ex-mechanical-product-instance-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-mechanical-product-instance-feature-highlight>` section.
