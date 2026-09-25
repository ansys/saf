.. _saf-ex-mapdl-product-instance:


MAPDL Product Instance Manager
################################

.. _saf-ex-mapdl-product-instance-summary:

.. topic:: Objective

    Create a product instance manager for PyMAPDL to support applications involving finite element analysis, automation of simulation workflows, and integration with Python-based data processing for structural, thermal, and coupled physics problems.

    Source code for this example is in the `solution-examples <https://github.com/ansys/solution-examples>`_ repository.


.. _saf-ex-mapdl-product-instance-objective:

:material-outlined:`ads_click;1.25em;sd-text-primary` Objective
===============================================================
PyMAPDL provides a robust Python interface to Ansys Mechanical APDL, allowing users to automate finite element analyses, integrate seamlessly with Python data processing libraries, and optimize workflows across structural, thermal, and coupled physics simulations.

This example demonstrates how to create a product instance manager for PyMAPDL using SAF. The product instance manager enables management of the PyMAPDL product instance lifecycle, including starting, stopping, and accessing the product's API.

.. list-table:: **MAPDL Product Instance Manager**
   :widths: 20 80
   :header-rows: 1

   * - Component
     - Description
   * - Step model
     - * Long-running transaction to initialize the product instance.
       * Transaction to shut down the product instance.
       * Long-running transaction to call the MAPDL API to solve a model.
       * Long-running transaction that calls the MAPDL API to perform result postprocessing.
   * - User interface
     - * Button to initialize the product instance.
       * Button to shut down the product instance.
       * Button to solve a model.
       * Button to perform the result postprocessing.

.. figure:: /_static/images/usage_saf_ex_mapdl_product_instance_output_1.png
  :width: 100%

  Status before the initialization of the product instance

.. figure:: /_static/images/usage_saf_ex_mapdl_product_instance_output_2.png
  :width: 100%

  Status after the initialization of the product instance

.. figure:: /_static/images/usage_saf_ex_mapdl_product_instance_output_3.png
  :width: 100%

  Status after calling the ``solve_model`` and ``postprocess`` methods of the product instance

.. figure:: /_static/images/usage_saf_ex_mapdl_product_instance_output_4.png
  :width: 100%

  Status after shutting down the product instance

.. _saf-ex-mapdl-product-instance-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
==============================================================

.. note::
    This example requires the MAPDL 2025 R2 SP4 (25R2 SP4) product to be installed on your machine.
    To work with a MAPDL product instance, be sure to install the ``mapdl`` extra from the ``ansys-saf-product-manager`` package. You can do this by manually editing your ``pyproject.toml``.

    .. code-block:: toml

        ansys-saf-glow-engine = {version = "^2.30", extras = ["pim"]}
        ansys-saf-product-manager = {version = "^0.5", extras = ["mapdl"]}

    This will install the supported version of ``ansys-mapdl-core`` to control the MAPDL product instances.
    This example uses PIM as the product instance management system. If you want to use HPS instead, replace the ``pim`` extra with ``hps``.
    For more information, see :ref:`instance_management_configuration`.

.. _saf-ex-mapdl-product-instance-solution:

:octicon:`code-square;1em;sd-text-primary` Solution
===================================================

To create a product instance manager for MAPDL products and interact with it, walk through the following sequence of tabs.

.. tab-set::

  .. tab-item:: 1️⃣Backend
    :name: saf-ex-mapdl-product-instance-backend-tab

    Define the step model.

    .. dropdown:: Define the step model
     :open:

     * There are two transactions that are used to manage the product instance lifecycle: ``launch_mapdl`` and ``close_mapdl``.

       * The first one initializes the product instance, while the second one shuts it down.
       * The ``launch_mapdl`` long-running transaction is decorated with ``@create_instance`` to create an instance of the MAPDL product manager, in this case, ``MapdlManager``.
       * The ``close_mapdl`` transaction is decorated with @instance and is used to shut down the existing MAPDL instance.

     * The other two transactions, ``solve_model`` and ``postprocessing``, are used to call the MAPDL API to solve a model and postprocess the results, respectively.

       * Both are decorated with ``@instance`` to indicate they operate on an existing product instance.

     .. code-block:: python
        :lineno-start: 5
        :caption: ``mapdl_step.py``

        from ansys.bdm.api import NO_ENTITY, EntityHandle
        from ansys.mapdl.core.plotting.theme import PyMAPDL_cmap  # pyright: ignore[reportMissingTypeStubs]
        from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
        from ansys.saf.glow.solution.beta.mapdl import MapdlManager
        import numpy as np
        import pyvista as pv


        class MapdlStep(StepModel):
            """MAPDL step for the advanced solution example."""

            version: str = "252"
            nodal_values: list[float] = []
            test_file: EntityHandle = NO_ENTITY
            solved: bool = False

            @transaction(self=StepSpec(download=["version"], upload=["test_file"]))
            @create_instance("mapdl_instance", MapdlManager)
            @long_running
            def launch_mapdl(self, mapdl_instance: MapdlManager) -> None:
                """Launch a MAPDL instance with the specified version."""
                self.transaction.raise_event(message="Clear Messages", stream_name="mapdl-output-stream")
                self.transaction.raise_event(message="Initializing MAPDL instance.", stream_name="mapdl-output-stream")
                try:
                    mapdl_instance.initialize(version=self.version)
                    test_file = self.storage_scope.get_storage_root() / "test_file.txt"
                    test_file.write_text("my_test_file")
                    self.test_file = self.storage_scope.store(test_file)
                except Exception as e:
                    self.transaction.raise_event(message="MAPDL initialization failed", stream_name="mapdl-instance-stream")
                    self.transaction.raise_event(message=f"MAPDL initialization failed: {e}", stream_name="mapdl-output-stream")
                    return
                self.transaction.raise_event(message="MAPDL initialized.", stream_name="mapdl-instance-stream")
                self.transaction.raise_event(message="MAPDL initialized.", stream_name="mapdl-output-stream")

            @transaction()
            @instance("mapdl_instance")
            def prepare_env(self, mapdl_instance: MapdlManager) -> None:
                """Prepare the environment for the MAPDL instance."""
                mapdl = mapdl_instance.instance
                mapdl.clear()  # type: ignore
                mapdl.prep7()  # type: ignore
                mapdl.title("2-D Solenoid Actuator Static Analysis")  # type: ignore

            @transaction()
            @instance("mapdl_instance")
            def setup_fe_model(self, mapdl_instance: MapdlManager) -> None:
                """Set up the finite element model for the solenoid actuator."""
                mapdl = mapdl_instance.instance

                # Set up the FE model
                mapdl.et(1, "PLANE233")  # Define PLANE233 as element type  # type: ignore
                mapdl.keyopt(1, 3, 1)  # Use axisymmetric analysis option  # type: ignore
                mapdl.keyopt(1, 7, 1)  # Condense forces at the corner nodes  # type: ignore

                # Set material properties
                mapdl.mp("MURX", 1, 1)  # Define material properties (permeability), Air  # type: ignore
                mapdl.mp("MURX", 2, 1000)  # Permeability of backiron  # type: ignore
                mapdl.mp("MURX", 3, 1)  # Permeability of coil  # type: ignore
                mapdl.mp("MURX", 4, 2000)  # Permeability of armature  # type: ignore

                # Set parameters
                n_turns = 650  # Number of coil turns
                i_current = 1.0  # Current per turn
                ta = 0.75  # Model dimensions (centimeters)
                tb = 0.75
                tc = 0.50
                td = 0.75
                wc = 1
                hc = 2
                gap = 0.25
                space = 0.25
                ws = wc + 2 * space
                hs = hc + 0.75
                w = ta + ws + tc
                hb = tb + hs
                h = hb + gap + td
                acoil = wc * hc  # Cross-section area of coil (cm**2)
                jdens = n_turns * i_current / acoil  # Current density (A/cm**2)

                smart_size = 4  # Smart Size Level for Meshing

                # Create geometry
                mapdl.rectng(0, w, 0, tb)  # Create rectangular areas  # type: ignore
                mapdl.rectng(0, w, tb, hb)  # type: ignore
                mapdl.rectng(ta, ta + ws, 0, h)  # type: ignore
                mapdl.rectng(ta + space, ta + space + wc, tb + space, tb + space + hc)  # type: ignore
                mapdl.aovlap("ALL")  # type: ignore
                mapdl.rectng(0, w, 0, hb + gap)  # type: ignore
                mapdl.rectng(0, w, 0, h)  # type: ignore
                mapdl.aovlap("ALL")  # type: ignore
                mapdl.numcmp("AREA")  # Compress out unused area numbers  # type: ignore

                # Mesh
                mapdl.asel("S", "AREA", "", 2)  # Assign attributes to coil  # type: ignore
                mapdl.aatt(3, 1, 1, 0)  # type: ignore

                mapdl.asel("S", "AREA", "", 1)  # Assign attributes to armature  # type: ignore
                mapdl.asel("A", "AREA", "", 12, 13)  # type: ignore
                mapdl.aatt(4, 1, 1)  # type: ignore

                mapdl.asel("S", "AREA", "", 3, 5)  # Assign attributes to backiron  # type: ignore
                mapdl.asel("A", "AREA", "", 7, 8)  # type: ignore
                mapdl.aatt(2, 1, 1, 0)  # type: ignore

                mapdl.pnum("MAT", 1)  # Turn material numbers on  # type: ignore
                mapdl.allsel("ALL")  # type: ignore

                mapdl.smrtsize(smart_size)  # Set smart size meshing  # type: ignore
                mapdl.amesh("ALL")  # Mesh all areas  # type: ignore

                # Scale mesh to meters
                mapdl.esel("S", "MAT", "", 4)  # Select armature elements  # type: ignore
                mapdl.cm("ARM", "ELEM")  # Define armature as a component  # type: ignore
                mapdl.allsel("ALL")  # type: ignore
                mapdl.arscale(na1="all", rx=0.01, ry=0.01, rz=1, imove=1)  # Scale model to MKS (meters)  # type: ignore
                mapdl.finish()  # type: ignore

                # Loads and boundary conditions
                mapdl.slashsolu()  # type: ignore

                # Apply current density (A/m**2)
                mapdl.esel("S", "MAT", "", 3)  # Select coil elements  # type: ignore
                mapdl.bfe("ALL", "JS", 1, "", "", jdens / 0.01**2)  # type: ignore

                mapdl.esel("ALL")  # type: ignore
                mapdl.nsel("EXT")  # Select exterior nodes  # type: ignore
                mapdl.d("ALL", "AZ", 0)  # Set potentials to zero (flux-parallel)  # type: ignore

            @transaction(self=StepSpec(upload=["solved"]))
            @instance("mapdl_instance")
            @long_running
            def solve_model(self, mapdl_instance: MapdlManager) -> None:
                """Solve the finite element model using MAPDL."""
                self.transaction.raise_event(message="Clear Messages", stream_name="mapdl-output-stream")
                self.transaction.raise_event(message="Solving Model...", stream_name="mapdl-output-stream")
                try:
                    mapdl = mapdl_instance.instance

                    mapdl.allsel("ALL")  # type: ignore
                    mapdl.solve()  # type: ignore
                    mapdl.finish()  # type: ignore

                    self.solved = True
                except Exception as e:
                    self.transaction.raise_event(message="Solve model failed.", stream_name="mapdl-instance-stream")
                    self.transaction.raise_event(message=f"Solve model failed: {e}", stream_name="mapdl-output-stream")
                    return
                self.transaction.raise_event(message="Solve model succeeded.", stream_name="mapdl-instance-stream")
                self.transaction.raise_event(message="Solve model succeeded.", stream_name="mapdl-output-stream")

            @transaction(self=StepSpec(upload=["nodal_values"]))
            @instance("mapdl_instance")
            def postprocessing(self, mapdl_instance: MapdlManager) -> None:
                """Post-process the results and create a plot of the magnetic flux in the X direction."""
                self.transaction.raise_event(message="Clear Messages", stream_name="mapdl-output-stream")
                self.transaction.raise_event(message="Postprocessing results...", stream_name="mapdl-output-stream")
                try:
                    mapdl = mapdl_instance.instance

                    mapdl.post1()  # type: ignore
                    mapdl.file("file", "rmg")  # type: ignore
                    mapdl.set("last")  # type: ignore

                    self.nodal_values = mapdl.post_processing.nodal_values("b", "x").tolist()  # type: ignore

                    # Create a MAPDL Power Graphics plot of the X-direction magnetic flux
                    mapdl.graphics("power")  # type: ignore
                    mapdl.rgb("INDEX", 100, 100, 100, 0)  # type: ignore
                    mapdl.rgb("INDEX", 80, 80, 80, 13)  # type: ignore
                    mapdl.rgb("INDEX", 60, 60, 60, 14)  # type: ignore
                    mapdl.rgb("INDEX", 0, 0, 0, 15)  # type: ignore

                    mapdl.edge(1, 1)  # type: ignore

                    # Obtain grid and scalar data
                    elem_mats = mapdl.mesh.material_type  # type: ignore
                    grids = []
                    scalars = []
                    for mat in np.unique(elem_mats):  # type: ignore
                        mapdl.esel("s", "mat", "", mat)  # type: ignore
                        mapdl.nsle()  # type: ignore
                        grids.append(mapdl.mesh.grid)  # type: ignore
                        scalars.append(mapdl.post_processing.nodal_values("b", "x"))  # type: ignore
                    mapdl.allsel()  # type: ignore

                    # Color map and result plot
                    plotter = pv.Plotter()  # type: ignore
                    for i, grid in enumerate(grids):  # type: ignore
                        plotter.add_mesh(  # type: ignore
                            grid,
                            scalars=scalars[i],
                            show_edges=True,
                            cmap=PyMAPDL_cmap,  # type: ignore
                            n_colors=9,
                            scalar_bar_args={
                                "color": "black",
                                "title": "B Flux X",
                                "vertical": False,
                                "n_labels": 10,
                            },
                        )

                    plotter.set_background(color="white")  # type: ignore
                    _ = plotter.camera_position = "xy"
                except Exception as e:
                    self.transaction.raise_event(message="Results postprocessing failed.", stream_name="mapdl-instance-stream")
                    self.transaction.raise_event(
                        message=f"Results postprocessing failed: {e}", stream_name="mapdl-output-stream"
                    )
                    return
                self.transaction.raise_event(message="Results postprocessing succeeded.", stream_name="mapdl-instance-stream")
                self.transaction.raise_event(message="Results postprocessing succeeded.", stream_name="mapdl-output-stream")

            @transaction(self=StepSpec())
            @instance("mapdl_instance")
            def close_mapdl(self, mapdl_instance: MapdlManager) -> None:
                """Close the MAPDL instance."""
                self.transaction.raise_event(message="Clear Messages", stream_name="mapdl-output-stream")
                self.transaction.raise_event(message="Starting to shutdown the instance.", stream_name="mapdl-output-stream")

                try:
                    mapdl = mapdl_instance.instance
                    mapdl.graphics("FULL")  # Returning to default mode.  # type: ignore

                    mapdl_instance.shutdown()
                except Exception as e:
                    self.transaction.raise_event(message="MAPDL shutdown failed.", stream_name="mapdl-instance-stream")
                    self.transaction.raise_event(message=f"MAPDL shutdown failed: {e}", stream_name="mapdl-output-stream")
                    return
                self.transaction.raise_event(message="MAPDL Shutdown.", stream_name="mapdl-instance-stream")
                self.transaction.raise_event(message="MAPDL instance shutdown complete.", stream_name="mapdl-output-stream")


  .. tab-item:: 2️⃣Frontend
    :name: saf-ex-mapdl-product-instance-frontend-tab

    Define the user interface.

    .. dropdown:: Define the step layout
      :open:

      The user interface has four main buttons. Each one triggers a transaction in the step model.

      .. code-block:: python
          :lineno-start: 4
          :caption: layout from ``mapdl_instance_page.py``

          from typing import List, Tuple
          from ansys.saf.glow.client import DashClient, callback
          import ansys_web_components_dash as AwcDash
          from ansys_web_components_dash import AwcDashEnum
          from dash_extensions.enrich import Input, Output, State, dcc, html, no_update  # pyright: ignore[reportMissingTypeStubs]
          from dash_iconify import DashIconify
          import dash_mantine_components as dmc

          from ansys.solutions.examples.solution.definition import ExamplesSolution, MapdlStep


          def layout(step: MapdlStep) -> html.Div:
              """Layout for the MAPDL Instance Manager page."""
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
                          "⚠️ This example requires MAPDL 2025 R2 SP4 (25R2 SP4) to run.",
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
                      html.H1("MAPDL Instance Manager", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}),
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
                              " to control MAPDL. Click the Launch MAPDL button to start the instance. A "
                              "transaction method will start MAPDL which can be used across all transaction "
                              "methods of the solution. Run MAPDL operations with the Solve Model and "
                              "Postprocess Results buttons. Close MAPDL using the Shutdown button.",
                          ],
                          style={"font-size": "20px"},
                      ),
                      html.Div(
                          [
                              dmc.Button(
                                  "Launch MAPDL",
                                  id="launch_mapdl_button",
                                  variant="filled",
                                  radius="xl",
                                  style={"color": "#FFFFFF", "width": "20%"},
                                  leftIcon=DashIconify(icon="streamline:startup-solid"),
                              ),
                              dmc.Button(
                                  "Shutdown MAPDL",
                                  id="shutdown_mapdl_button",
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
                          "Once the instance is created, you can use the buttons below to solve the model and postprocess "
                          "the results.",
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
                                              "Solve Model",
                                              id="solve_model_button",
                                              variant="filled",
                                              radius="xl",
                                              style={"color": "#FFFFFF", "width": "50%"},
                                              leftIcon=DashIconify(icon="carbon:result"),
                                              disabled=True,
                                          ),
                                          dmc.Button(
                                              "Postprocess Results",
                                              id="postprocess_results_button",
                                              variant="filled",
                                              radius="xl",
                                              style={"color": "#FFFFFF", "width": "50%"},
                                              leftIcon=DashIconify(icon="uil:process"),
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
                                  step, id="mapdl-instance-listener", stream_name="mapdl-instance-stream"
                              )
                          ]
                      ),
                      html.Div(
                          [DashClient.create_event_listener(step, id="mapdl-output-listener", stream_name="mapdl-output-stream")]
                      ),
                      dcc.Store(id="mapdl-ui-button-state", storage_type="session"),
                      dmc.NotificationsProvider(
                          dmc.Container(id="mapdl-notification-container", children=[]),
                          position="bottom-left",
                      ),
                  ],
              )

              return layout

    .. dropdown:: Define the initialization of the product instance callback
      :open:

      * When the :guilabel:`Launch MAPDL` button is clicked, the initialization callback is activated.
      * The callback starts the long-running transaction to initialize the product instance.
      * After the product is initialized, it updates the UI with the result.

      .. code-block:: python
          :lineno-start: 165
          :caption: initialization callback from ``mapdl_instance_page.py``

          @callback(
              Input("launch_mapdl_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def init(n_clicks: int, pathname: str):
              """Initialize the MAPDL instance."""
              if n_clicks:
                  project = DashClient[ExamplesSolution].get_project(pathname)
                  step = project.steps.mapdl_step
                  step.launch_mapdl().wait()
                  step.prepare_env()
                  step.setup_fe_model()


          @callback(
              Output("launch_mapdl_button", "loading"),
              Input("launch_mapdl_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def load_init(n_clicks: int, pathname: str):
              """Set loading state for the launch button."""
              return True

    .. dropdown:: Define the solve_model transaction button
      :open:

      * The callback starting the transaction solves the finite element model using the MAPDL API.
      * The ``console-logs`` container will display the output after the method has finalized.

      .. code-block:: python
          :lineno-start: 191
          :caption: solve_model transaction button callback from ``mapdl_instance_page.py``

          @callback(
              Output("solve_model_button", "loading"),
              Input("solve_model_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def solve_model(n_clicks: int, pathname: str) -> dmc.Notification | None:
              """Solve the model in the MAPDL instance."""
              project = DashClient[ExamplesSolution].get_project(pathname)
              step = project.steps.mapdl_step
              step.solve_model()
              return True

    .. dropdown:: Define the postprocess_results transaction button
      :open:

      * The callback starting the transaction postprocesses the results using the MAPDL API.
      * The ``console-logs`` container will display the output after the method has finalized.

      .. code-block:: python
          :lineno-start: 205
          :caption: postprocess_results transaction button callback from ``mapdl_instance_page.py``

          @callback(
              Input("postprocess_results_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def postprocess_results(n_clicks: int, pathname: str):
              """Postprocess results in the MAPDL instance."""
              if n_clicks:
                  project = DashClient[ExamplesSolution].get_project(pathname)
                  step = project.steps.mapdl_step
                  step.postprocessing()


          @callback(
              Output("postprocess_results_button", "loading", allow_duplicate=True),
              Input("postprocess_results_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def load_mapdl_postprocess(n_clicks: int, pathname: str):
              """Set loading state for the postprocess results button."""
              return True

    .. dropdown:: Define the shutdown transaction button
      :open:

      * When the :guilabel:`Shutdown Instance` button is clicked, the shutdown callback is activated.
      * The callback starts the transaction to shut down the product instance.

      .. code-block:: python
          :lineno-start: 229
          :caption: shutdown transaction button callback from ``mapdl_instance_page.py``

          @callback(
              Input("shutdown_mapdl_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def shutdown(n_clicks: int, pathname: str):
              """Shutdown the MAPDL instance."""
              if n_clicks is not None:
                  project = DashClient[ExamplesSolution].get_project(pathname)
                  step = project.steps.mapdl_step
                  step.close_mapdl()


          @callback(
              Output("shutdown_mapdl_button", "loading", allow_duplicate=True),
              Input("shutdown_mapdl_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def load_mapdl_shutdown(n_clicks: int, pathname: str):
              """Set loading state for the shutdown button."""
              return True

    .. dropdown:: Define the logs system.
      :open:

      * Create the ``logs_container`` component and an event listener for the ``mapdl-output-listener`` stream to display logs in the UI, as shown in the layout.
      * The method logs will be received through the ``mapdl-output-listener`` listener.
      * When the listener receives a message, the callback is activated and updates the logs container as expected.

      .. code-block:: python
          :lineno-start: 253
          :caption: display_the_mapdl_output callback from ``mapdl_instance_page.py``

          @callback(
              Output("console-logs", "children"),
              Input("mapdl-output-listener", "message"),
              State("console-logs", "children"),
              State("url", "pathname"),
          )
          def display_the_mapdl_output(message: dict, current_logs: str, pathname: str) -> str:
              """Display MAPDL output."""
              if message:
                  new_content = message["data"].strip('"').replace("\\n", "\n")
                  if new_content == "Clear Messages":
                      return ""
                  combined = (current_logs or "") + "\n" + new_content
                  return combined
              return current_logs

    .. dropdown:: Define the notification system.
      :open:

      * Create the ``dmc.NotificationsProvider`` and an event listener for the ``mapdl-instance-listener`` stream to display notifications in the UI, as shown in the layout.
      * To display notifications when a method succeeds or fails, the ``mapdl-instance-listener`` must be triggered.
      * When the listener receives a message, the callback is activated and generates the appropriate notification in the UI.

      .. code-block:: python
          :lineno-start: 270
          :caption: update_mapdl_ui callback from ``mapdl_instance_page.py``

          @callback(
              [
                  Output(button_id, "loading")
                  for button_id in [
                      "launch_mapdl_button",
                      "shutdown_mapdl_button",
                      "solve_model_button",
                      "postprocess_results_button",
                  ]
              ],
              [
                  Output(button_id, "disabled")
                  for button_id in [
                      "launch_mapdl_button",
                      "shutdown_mapdl_button",
                      "solve_model_button",
                      "postprocess_results_button",
                  ]
              ],
              Output("mapdl-notification-container", "children"),
              Output("mapdl-ui-button-state", "data"),
              Input("mapdl-instance-listener", "message"),
              Input("url", "pathname"),
              State("mapdl-ui-button-state", "data"),
          )
          def update_mapdl_ui(
              message: dict, pathname: str, prev_state: dict | None
          ) -> Tuple[List[bool], List[bool], dmc.Notification, dict]:
              """Update the ui."""

              button_ids = ["launch_mapdl_button", "shutdown_mapdl_button", "solve_model_button", "postprocess_results_button"]
              default_states = {
                  "launch_mapdl_button": {
                      "loading": False,
                      "disabled": False,
                  },
                  "shutdown_mapdl_button": {
                      "loading": False,
                      "disabled": True,
                  },
                  "solve_model_button": {
                      "loading": False,
                      "disabled": True,
                  },
                  "postprocess_results_button": {
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
                  if message_content == "MAPDL initialized.":
                      prev_state["launch_mapdl_button"]["disabled"] = True
                      prev_state["shutdown_mapdl_button"]["disabled"] = False
                      prev_state["solve_model_button"]["disabled"] = False
                      notification.message = "MAPDL instance launched successfully!"
                      notification.icon = DashIconify(icon="streamline:startup-solid")
                  elif message_content == "MAPDL initialization failed":
                      prev_state["launch_mapdl_button"]["disabled"] = False
                      notification.message = "MAPDL initialization failed. Please check the logs."
                      notification.icon = DashIconify(icon="streamline:startup-solid")
                      notification.color = "red"
                      notification.title = "Error"
                  elif message_content == "Solve model succeeded.":
                      prev_state["solve_model_button"]["disabled"] = True
                      prev_state["postprocess_results_button"]["disabled"] = False
                      notification.message = "Model solved successfully!"
                      notification.icon = DashIconify(icon="carbon:result")
                  elif message_content == "Solve model failed.":
                      prev_state["solve_model_button"]["disabled"] = False
                      notification.message = "Solve model failed. Please check the logs."
                      notification.icon = DashIconify(icon="carbon:result")
                      notification.color = "red"
                      notification.title = "Error"
                  elif message_content == "Results postprocessing succeeded.":
                      notification.message = "Results postprocessing succeeded!"
                      notification.icon = DashIconify(icon="uil:process")
                  elif message_content == "Results postprocessing failed.":
                      notification.message = "Results postprocessing failed. Please check the logs."
                      notification.icon = DashIconify(icon="uil:process")
                      notification.color = "red"
                      notification.title = "Error"
                  elif message_content == "MAPDL Shutdown.":
                      prev_state = default_states
                      notification.message = "MAPDL instance shutdown successfully!"
                      notification.icon = DashIconify(icon="mdi:shutdown")
                  elif message_content == "MAPDL shutdown failed.":
                      prev_state["shutdown_mapdl_button"]["disabled"] = False
                      notification.message = "MAPDL instance shutdown failed. Please check the logs."
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
