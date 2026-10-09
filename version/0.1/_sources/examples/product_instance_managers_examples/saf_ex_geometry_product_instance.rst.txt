.. _saf-ex-geometry-product-instance:


Geometry Product Instance Manager
##################################

.. _saf-ex-geometry-product-instance-summary:

.. topic:: Objective

  Create a product instance manager for PyGeometry to support applications involving geometric modeling, transformation operations, and spatial analysis across simulations involving multiple physical domains.

  .. _saf-ex-geometry-product-instance-objective:

:material-outlined:`ads_click;1.25em;sd-text-primary` Objective
===============================================================
PyGeometry is a versatile library for geometric modeling and spatial computation, supporting a wide range of applications including shape representation, transformation operations, and spatial analysis across simulations involving multiple physical phenomena.

This example demonstrates how to create a product instance manager for Geometry products using SAF. The product instance manager enables management of the Geometry product instance lifecycle, including starting, stopping, and accessing the product's API.

.. list-table:: **Geometry Product Instance Manager**
   :widths: 20 80
   :header-rows: 1

   * - Component
     - Description
   * - Step model
     - * Long-running transaction to initialize the product instance.
       * Transaction to shut down the product instance.
       * Transaction to call the Geometry API to create a slot by extruding a sketch.
       * Transaction to call the Geometry API to get the active design.
   * - User interface
     - * Button to initialize the product instance.
       * Button to shut down the product instance.
       * Button to create a slot by extruding a sketch.
       * Button to get the active design.

.. figure:: /_static/images/usage_saf_ex_geometry_product_instance_output_1.png
  :width: 100%

  Status before the initialization of the product instance

.. figure:: /_static/images/usage_saf_ex_geometry_product_instance_output_2.png
  :width: 100%

  Status after the initialization of the product instance

.. figure:: /_static/images/usage_saf_ex_geometry_product_instance_output_3.png
  :width: 100%

  Status after calling the ``extrude_slot`` and ``get_active_design`` methods of the product instance

.. figure:: /_static/images/usage_saf_ex_geometry_product_instance_output_4.png
  :width: 100%

  Status after shutting down the product instance

.. _saf-ex-geometry-product-instance-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
==============================================================

.. note::
    This example requires the Geometry 2025 R2 Service Pack 4 (25R2 SP4) product to be installed on your machine.
    To work with a Geometry product instance, be sure to install the ``geometry`` extra from the ``ansys-saf-product-manager`` package. You can do this by manually editing your ``pyproject.toml``.

    .. code-block:: toml

        ansys-saf-glow-engine = {version = "^2.30", extras = ["pim"]}
        ansys-saf-product-manager = {version = "^0.5", extras = ["geometry"]}

    This will install the supported version of ``ansys-geometry-core`` to control the Geometry product instances.
    This example uses PIM as the product instance management system. If you want to use HPS instead, replace the ``pim`` extra with ``hps``.
    For more information, see :ref:`instance_management_configuration`.


.. _saf-ex-geometry-product-instance-solution:

:octicon:`code-square;1em;sd-text-primary` Solution
===================================================

To create a product instance manager for Geometry products and interact with it, walk through the following sequence of tabs.

.. tab-set::

  .. tab-item:: 1️⃣Backend
    :name: saf-ex-geometry-product-instance-backend-tab

    Define the step model.

    .. dropdown:: Define the step model
     :open:

     * There are two transactions that are used to manage the product instance lifecycle: ``launch_geometry`` and ``close_geometry``.

       * The first one initializes the product instance, while the second one shuts it down.
       * The ``launch_geometry`` long-running transaction is decorated with ``@create_instance`` to create an instance of the Geometry product manager, in this case, ``GeometryManager``.
       * The ``close_geometry`` transaction is decorated with ``@instance`` and is used to shut down the existing Geometry instance.

     * The other two transactions, ``extrude_slot`` and ``get_active_design``, are used to call the Geometry API to extrude a slot and get the active design, respectively.

       * Both are decorated with ``@instance`` to indicate they operate on an existing product instance.

     .. code-block:: python
        :lineno-start: 5
        :caption: ``geometry_step.py``

        from ansys.geometry.core.math import Point2D  # pyright: ignore[reportMissingTypeStubs]
        from ansys.geometry.core.misc import UNITS, Distance  # pyright: ignore[reportMissingTypeStubs]
        from ansys.geometry.core.sketch import Sketch  # pyright: ignore[reportMissingTypeStubs]
        from ansys.saf.glow.solution import StepModel, StepSpec, create_instance, instance, long_running, transaction
        from ansys.saf.glow.solution.beta.geometry import GeometryManager
        from pint import Quantity


        class GeometryInstanceStep(StepModel):
            """Geometry step for the advanced solution example."""

            version: str = "252"
            body_faces: int = 0
            body_edges: int = 0
            active_design_name: str = ""
            geometry_available: bool = False

            @transaction(self=StepSpec(download=["version"]))
            @create_instance("geometry_manager", GeometryManager)
            @long_running
            def launch_geometry(self, geometry_manager: GeometryManager) -> None:
                """Launch the Geometry instance and check its availability."""
                self.transaction.raise_event(message="Clear Messages", stream_name="geometry-output-stream")
                self.transaction.raise_event(message="Initializing Geometry instance.", stream_name="geometry-output-stream")
                try:
                    geometry_manager.initialize(version=self.version)
                except Exception as e:
                    self.transaction.raise_event(
                        message="Geometry initialization failed", stream_name="geometry-instance-stream"
                    )
                    self.transaction.raise_event(
                        message=f"Geometry initialization failed: {e}", stream_name="geometry-output-stream"
                    )
                    return
                self.transaction.raise_event(message="Geometry initialized.", stream_name="geometry-instance-stream")
                self.transaction.raise_event(message="Geometry initialized.", stream_name="geometry-output-stream")

            @transaction(self=StepSpec(upload=["body_faces", "body_edges"]))
            @instance("geometry_manager")
            def extrude_slot(self, geometry_manager: GeometryManager) -> None:
                """Create a slot in the Geometry instance by extruding a sketch."""
                self.transaction.raise_event(message="Clear Messages", stream_name="geometry-output-stream")
                self.transaction.raise_event(message="Starting extrude slot transaction.", stream_name="geometry-output-stream")
                try:
                    # Create design on Geometry instance
                    design = geometry_manager.instance.create_design("ExtrudeSlot")
                    # Create a Sketch object and draw a slot
                    sketch = Sketch()
                    sketch.slot(Point2D([10, 10], UNITS.mm), Quantity(10, UNITS.mm), Quantity(5, UNITS.mm))  # type: ignore
                    # Extrude the sketch
                    body = design.extrude_sketch(name="MySlot", sketch=sketch, distance=Distance(50, UNITS.mm))  # type: ignore
                    if not body:
                        raise RuntimeError("Body was not created.")
                    self.body_faces = len(body.faces)
                    self.body_edges = len(body.edges)
                except Exception as e:
                    self.transaction.raise_event(message="Extrude Slot failed.", stream_name="geometry-instance-stream")
                    self.transaction.raise_event(message=f"Extrude Slot failed: {e}", stream_name="geometry-output-stream")
                    return
                self.transaction.raise_event(message="Extrude Slot succeeded.", stream_name="geometry-instance-stream")
                self.transaction.raise_event(message="Extrude Slot succeeded.", stream_name="geometry-output-stream")

            @transaction(self=StepSpec(upload=["active_design_name"]))
            @instance("geometry_manager")
            def get_active_design(self, geometry_manager: GeometryManager) -> None:
                """Get the name of the currently active design."""
                self.transaction.raise_event(message="Clear Messages", stream_name="geometry-output-stream")
                self.transaction.raise_event(message="Getting active design name...", stream_name="geometry-output-stream")
                try:
                    self.active_design_name = geometry_manager.instance.read_existing_design().name

                    self.transaction.raise_event(
                        message=f"Active design name: {self.active_design_name}.", stream_name="geometry-output-stream"
                    )
                except Exception as e:
                    self.transaction.raise_event(message="Get active design failed.", stream_name="geometry-instance-stream")
                    self.transaction.raise_event(message=f"Get active design failed: {e}", stream_name="geometry-output-stream")
                    return
                self.transaction.raise_event(message="Get active design succeeded.", stream_name="geometry-instance-stream")
                self.transaction.raise_event(message="Get active design succeeded.", stream_name="geometry-output-stream")

            @transaction(self=StepSpec(upload=["geometry_available"]))
            @instance("geometry_manager")
            def close_geometry(self, geometry_manager: GeometryManager) -> None:
                """Close the Geometry instance."""
                self.transaction.raise_event(message="Clear Messages", stream_name="geometry-output-stream")
                self.transaction.raise_event(message="Starting to shutdown the instance.", stream_name="geometry-output-stream")
                try:
                    geometry_manager.shutdown()
                    self.geometry_available = False
                except Exception as e:
                    self.transaction.raise_event(message="Geometry shutdown failed", stream_name="geometry-instance-stream")
                    self.transaction.raise_event(message=f"Geometry shutdown failed: {e}", stream_name="geometry-output-stream")
                    return
                self.transaction.raise_event(message="Geometry shutdown.", stream_name="geometry-instance-stream")
                self.transaction.raise_event(
                    message="Geometry instance shutdown complete..", stream_name="geometry-output-stream"
                )
  .. tab-item:: 2️⃣Frontend
    :name: saf-ex-geometry-product-instance-frontend-tab

    Define the user interface.

    .. dropdown:: Define the step layout
      :open:

      The user interface has four main buttons. Each one triggers a transaction in the step model.

      .. code-block:: python
          :lineno-start: 4
          :caption: layout from ``geometry_instance_page.py``

          from typing import List, Tuple
          from ansys.saf.glow.client import DashClient, callback
          import ansys_web_components_dash as AwcDash
          from ansys_web_components_dash import AwcDashEnum
          from dash_extensions.enrich import Input, Output, State, dcc, html, no_update  # pyright: ignore[reportMissingTypeStubs]
          from dash_iconify import DashIconify
          import dash_mantine_components as dmc
          from ansys.solutions.examples.solution.definition import ExamplesSolution, GeometryInstanceStep


          def layout(step: GeometryInstanceStep) -> html.Div:
              """Layout for the Geometry Instance Manager page."""
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
                          "⚠️ This example requires Geometry 2025 R2 Service Pack 4 (25R2 SP4) to run.",
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
                          "Geometry Instance Manager", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}
                      ),
                      html.Br(),
                      html.Hr(className="my-2"),
                      html.Br(),
                      html.P(
                          [
                              "This example demonstrates how to leverage ",
                              html.A(
                                  "HPS",
                                  href="https://saf.glow.docs.solutions.ansys.com/version/stable/user_guide/"
                                  "using_ansys_products/product_instance_management/configuration.html#hpc-platform-services-hps",
                                  target="_blank",
                                  style={"color": "blue"},
                              ),
                              " to control Geometry. Click the Launch Geometry button to start the instance. A "
                              "transaction method will start Geometry which can be used across all transaction "
                              "methods of the solution. Run Geometry operations with the Extrude Slot and "
                              "Get Active Design buttons. Close Geometry using the Shutdown button.",
                          ],
                          style={"font-size": "20px"},
                      ),
                      html.Div(
                          [
                              dmc.Button(
                                  "Launch Geometry",
                                  id="launch_geometry_button",
                                  variant="filled",
                                  radius="xl",
                                  style={"color": "#FFFFFF", "width": "20%"},
                                  leftIcon=DashIconify(icon="streamline:startup-solid"),
                              ),
                              dmc.Button(
                                  "Shutdown Geometry",
                                  id="shutdown_geometry_button",
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
                          "Once the instance is created, you can use the buttons below to extrude a slot and get the active"
                          " design.",
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
                                              "Extrude Slot",
                                              id="extrude_slot_button",
                                              variant="filled",
                                              radius="xl",
                                              style={"color": "#FFFFFF", "width": "50%"},
                                              leftIcon=DashIconify(icon="mdi:design"),
                                              disabled=True,
                                          ),
                                          dmc.Button(
                                              "Get Active Design",
                                              id="get_active_design_button",
                                              variant="filled",
                                              radius="xl",
                                              style={"color": "#FFFFFF", "width": "50%"},
                                              leftIcon=DashIconify(icon="carbon:result"),
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
                                  step, id="geometry-instance-listener", stream_name="geometry-instance-stream"
                              )
                          ]
                      ),
                      html.Div(
                          [
                              DashClient.create_event_listener(
                                  step, id="geometry-output-listener", stream_name="geometry-output-stream"
                              )
                          ]
                      ),
                      dcc.Store(id="geometry-ui-button-state", storage_type="session"),
                      dmc.NotificationsProvider(
                          dmc.Container(id="geometry-notification-container", children=[]),
                          position="bottom-left",
                      ),
                  ],
              )

              return layout

    .. dropdown:: Define the initialization of the product instance callback
      :open:

      * When the :guilabel:`Launch Geometry` button is clicked, the initialization callback is activated.
      * The callback starts the long-running transaction to initialize the product instance.
      * After the product is initialized, it updates the UI with the result.

      .. code-block:: python
          :lineno-start: 96
          :caption: initialization callback from ``geometry_instance_page.py``

          @callback(
              Input("launch_geometry_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def init(n_clicks: int, pathname: str):
              """Initialize the Geometry instance."""
              if n_clicks:
                  project = DashClient[ExamplesSolution].get_project(pathname)
                  step = project.steps.geometry_step
                  step.launch_geometry().wait()


          @callback(
              Output("launch_geometry_button", "loading"),
              Input("launch_geometry_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def load_init(n_clicks: int, pathname: str):
              """Initialize the Geometry instance."""
              return True

    .. dropdown:: Define the extrude_slot transaction button
      :open:

      * The callback starting the transaction extrudes a slot by calling the Geometry API.
      * The ``console-logs`` container will display the output after the method has finalized.

      .. code-block:: python
          :lineno-start: 110
          :caption: extrude_slot transaction button callback from ``geometry_instance_page.py``

          @callback(
              Input("extrude_slot_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def extrude_slot(n_clicks: int, pathname: str):
              """Extrude a slot in the Geometry instance."""
              if n_clicks:
                  project = DashClient[ExamplesSolution].get_project(pathname)
                  step = project.steps.geometry_step
                  step.extrude_slot()


          @callback(
              Output("extrude_slot_button", "loading", allow_duplicate=True),
              Input("extrude_slot_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def load_extrude_slot(n_clicks: int, pathname: str):
              """Change loading status of the extrude slot button."""
              return True

    .. dropdown:: Define the get_active_design transaction button
      :open:

      * The callback starting the transaction gets the active design by calling the Geometry API.
      * The ``console-logs`` container will display the output after the method has finalized.

      .. code-block:: python
          :lineno-start: 124
          :caption: get_active_design transaction button callback from ``geometry_instance_page.py``

          @callback(
              Input("get_active_design_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def get_active_design(n_clicks: int, pathname: str):
              """Get the active design from the Geometry instance."""
              if n_clicks:
                  project = DashClient[ExamplesSolution].get_project(pathname)
                  step = project.steps.geometry_step
                  step.get_active_design()


          @callback(
              Output("get_active_design_button", "loading", allow_duplicate=True),
              Input("get_active_design_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def load_get_active_design(n_clicks: int, pathname: str):
              """Change loading status of the get active design button."""
              return True

    .. dropdown:: Define the shutdown transaction button
      :open:

      * When the :guilabel:`Shutdown Geometry` button is clicked, the shutdown callback is activated.
      * The callback starts the transaction to shut down the product instance.

      .. code-block:: python
          :lineno-start: 138
          :caption: shutdown transaction button callback from ``geometry_instance_page.py``

          @callback(
              Input("shutdown_geometry_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def shutdown(n_clicks: int, pathname: str):
              """Shutdown the Geometry instance."""
              if n_clicks is not None:
                  project = DashClient[ExamplesSolution].get_project(pathname)
                  step = project.steps.geometry_step
                  step.close_geometry()


          @callback(
              Output("shutdown_geometry_button", "loading", allow_duplicate=True),
              Input("shutdown_geometry_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def load_shutdown(n_clicks: int, pathname: str):
              """Change loading status of the shutdown button."""
              return True

    .. dropdown:: Define the logs system.
      :open:

      * Create the ``logs_container`` component and an event listener for the ``geometry-output-listener`` stream to display logs in the UI, as shown in the layout.
      * The method logs will be received through the ``geometry-output-listener`` listener.
      * When the listener receives a message, the callback is activated and updates the logs container as expected.

      .. code-block:: python
          :lineno-start: 138
          :caption: display_the_geometry_output callback from ``geometry_instance_page.py``

          @callback(
              Output("console-logs", "children"),
              Input("geometry-output-listener", "message"),
              State("console-logs", "children"),
              State("url", "pathname"),
          )
          def display_the_geometry_output(message: dict, current_logs: str, pathname: str) -> str:
              """Display geometry output."""
              if message:
                  new_content = message["data"].strip('"').replace("\\n", "\n")
                  if new_content == "Clear Messages":
                      return ""
                  combined = (current_logs or "") + "\n" + new_content
                  return combined
              return current_logs

    .. dropdown:: Define the notification system.
      :open:

      * Create the ``dmc.NotificationsProvider`` and an event listener for the ``geometry-instance-listener`` stream to display notifications in the UI, as shown in the layout.
      * To display notifications when a method succeeds or fails, the ``geometry-instance-listener`` must be triggered.
      * When the listener receives a message, the callback is activated and generates the appropriate notification in the UI.

      .. code-block:: python
          :lineno-start: 138
          :caption: update_geometry_ui callback from ``geometry_instance_page.py``

          @callback(
              [
                  Output(button_id, "loading")
                  for button_id in [
                      "launch_geometry_button",
                      "shutdown_geometry_button",
                      "extrude_slot_button",
                      "get_active_design_button",
                  ]
              ],
              [
                  Output(button_id, "disabled")
                  for button_id in [
                      "launch_geometry_button",
                      "shutdown_geometry_button",
                      "extrude_slot_button",
                      "get_active_design_button",
                  ]
              ],
              Output("geometry-notification-container", "children"),
              Output("geometry-ui-button-state", "data"),
              Input("geometry-instance-listener", "message"),
              Input("url", "pathname"),
              State("geometry-ui-button-state", "data"),
          )
          def update_geometry_ui(
              message: dict, pathname: str, prev_state: dict | None
          ) -> Tuple[List[bool], List[bool], dmc.Notification, dict]:
              """Update the ui."""

              button_ids = [
                  "launch_geometry_button",
                  "shutdown_geometry_button",
                  "extrude_slot_button",
                  "get_active_design_button",
              ]

              default_states = {
                  "launch_geometry_button": {
                      "loading": False,
                      "disabled": False,
                  },
                  "shutdown_geometry_button": {
                      "loading": False,
                      "disabled": True,
                  },
                  "extrude_slot_button": {
                      "loading": False,
                      "disabled": True,
                  },
                  "get_active_design_button": {
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
                  match message_content:
                      case "Geometry initialized.":
                          prev_state["launch_geometry_button"]["disabled"] = True
                          prev_state["shutdown_geometry_button"]["disabled"] = False
                          prev_state["extrude_slot_button"]["disabled"] = False
                          notification.message = "Geometry instance launched successfully!"
                          notification.icon = DashIconify(icon="streamline:startup-solid")
                      case "Geometry initialization failed":
                          prev_state["launch_geometry_button"]["disabled"] = False
                          notification.message = "Geometry initialization failed. Please check the logs."
                          notification.icon = DashIconify(icon="streamline:startup-solid")
                          notification.color = "red"
                          notification.title = "Error"
                      case "Extrude Slot succeeded.":
                          prev_state["extrude_slot_button"]["disabled"] = True
                          prev_state["get_active_design_button"]["disabled"] = False
                          notification.message = "Extrude Slot Design run successfully!"
                          notification.icon = DashIconify(icon="mdi:design")
                      case "Extrude Slot failed.":
                          prev_state["extrude_slot_button"]["disabled"] = False
                          notification.message = "Extrude Slot Design run failed. Please check the logs."
                          notification.icon = DashIconify(icon="mdi:design")
                          notification.color = "red"
                          notification.title = "Error"
                      case "Get active design succeeded.":
                          notification.message = "Get active design succeeded!"
                          notification.icon = DashIconify(icon="carbon:result")
                      case "Get active design failed.":
                          notification.message = "Get active design failed. Please check the logs."
                          notification.icon = DashIconify(icon="carbon:result")
                          notification.color = "red"
                          notification.title = "Error"
                      case "Geometry shutdown.":
                          prev_state = default_states
                          notification.message = "Geometry instance shutdown successfully!"
                          notification.icon = DashIconify(icon="mdi:shutdown")
                      case "Geometry shutdown failed.":
                          prev_state["shutdown_geometry_button"]["disabled"] = False
                          notification.message = "Geometry instance shutdown failed. Please check the logs."
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
