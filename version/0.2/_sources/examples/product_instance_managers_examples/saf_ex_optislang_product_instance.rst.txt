.. _saf-ex-optislang-product-instance:


optiSLang Product Instance Manager
##################################

.. _saf-ex-optislang-product-instance-summary:

.. topic:: Objective

    Create a product instance manager for Ansys optiSLang to support applications involving design optimization, sensitivity analysis, and robust parameter studies across simulations involving multiple physical domains.

    Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-optislang-product-instance-objective:

:material-outlined:`ads_click;1.25em;sd-text-primary` Objective
==================================================================
Ansys optiSLang is a powerful tool for design optimization and robustness evaluation, supporting a wide range of applications including sensitivity analysis, parameter studies, and uncertainty quantification across simulations involving multiple physical phenomena.

This example demonstrates how to create a product instance manager for optiSLang products using SAF. The product instance manager enables management of the optiSLang product instance lifecycle, including starting, stopping, and accessing the product's API.

.. list-table:: **optiSLang Product Instance Manager**
   :widths: 20 80
   :header-rows: 1

   * - Component
     - Description
   * - Step model
     - * Long-running transaction to initialize the product instance.
       * Transaction to shut down the product instance.
       * Long-running transaction to call the optiSLang API to evaluate a design.
       * Long-running transaction to call the optiSLang API to refine a design.
   * - User interface
     - * Button to initialize the product instance.
       * Button to shut down the product instance.
       * Button to evaluate a design.
       * Button to refine a design.

.. figure:: /_static/images/usage_saf_ex_optislang_product_instance_output_1.png
  :width: 100%

  Status before the initialization of the product instance

.. figure:: /_static/images/usage_saf_ex_optislang_product_instance_output_2.png
  :width: 100%

  Status after the initialization of the product instance

.. figure:: /_static/images/usage_saf_ex_optislang_product_instance_output_3.png
  :width: 100%

  Status after calling the ``evaluate_design`` and ``refine_design`` methods of the product instance

.. figure:: /_static/images/usage_saf_ex_optislang_product_instance_output_4.png
  :width: 100%

  Status after shutting down the product instance

.. _saf-ex-optislang-product-instance-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

.. note::
    This example requires the optiSLang 2024 R2 (24R2) product to be installed on your machine.
    To work with an optiSLang product instance, be sure to install the ``core-pim`` and ``instance-management-optislang`` extras from the ``ansys-saf-sdk`` package. You can do this by manually editing your ``pyproject.toml``.

    .. code-block:: toml

        ansys-saf-sdk = {version = "^0.2.0", extras = ["core-pim", "instance-management-optislang"]}

    This will install the supported version of ``ansys-optislang-core`` to control the optiSLang product instances.
    This example uses PIM as the product instance management system. If you want to use HPS instead, replace the ``core-pim`` extra with ``core-hps``.
    For more information, see :ref:`instance_management_configuration`.


.. _saf-ex-optislang-product-instance-solution:

:octicon:`code-square;1em;sd-text-primary` Solution
======================================================

To create a product instance manager for optiSLang products and interact with it, walk through the following sequence of tabs.

.. tab-set::

  .. tab-item:: 1️⃣Backend
    :name: saf-ex-optislang-product-instance-backend-tab

    Define the step model.

    .. dropdown:: Define the step model
     :open:

     * There are two transactions that are used to manage the product instance lifecycle: ``initialize_osl_instance_with_project_file`` and ``close_osl``.

       * The first one initializes the product instance, while the second one shuts it down.
       * The ``initialize_osl_instance_with_project_file`` long-running transaction is decorated with ``@create_instance`` to create an instance of the optiSLang product manager, in this case, ``OptislangManager``.
       * The ``close_osl`` transaction is decorated with @instance and is used to shut down the existing optiSLang instance.

     * The other two transactions, ``evaluate_design`` and ``refine_design``, are used to call the optiSLang API to evaluate and refine a design, respectively.

       * Both are decorated with ``@instance`` to indicate they operate on an existing product instance.

     .. code-block:: python
        :lineno-start: 5
        :caption: ``optislang_step.py``

        from pathlib import Path
        from typing import TYPE_CHECKING

        from ansys.bdm.api import NO_ENTITY, EntityHandle
        import ansys.optislang.core.examples as examples  # type: ignore
        from ansys.saf.glow.solution import (
            StepModel,
            StepSpec,
            create_instance,
            instance,
            long_running,
            transaction,
        )
        from ansys.saf.glow.solution.beta.optislang import OptislangManager

        if TYPE_CHECKING:
            from ansys.optislang.core.project_parametric import Design  # pyright: ignore[reportMissingTypeStubs]


        class OptislangStep(StepModel):
            """optiSLang step for the advanced solution example."""

            version: str = "242"
            working_dir: str = ""
            objective: str = ""
            evaluate_design_example: EntityHandle = NO_ENTITY

            @transaction(self=StepSpec(upload=["evaluate_design_example"]))
            def download_example_file(self) -> None:
                """Download the example file for optiSLang evaluation."""
                self.transaction.raise_event(message="Clear Messages", stream_name="optislang-output-stream")
                self.transaction.raise_event(message="Initializing optiSLang instance.", stream_name="optislang-output-stream")
                try:
                    example_path: str = examples.get_files("ten_bar_truss")[1][0]  # type: ignore
                    with Path(example_path).open(mode="rb") as f:  # type: ignore
                        self.evaluate_design_example = self.storage_scope.store_stream(f, Path("project.opf"))
                except Exception as e:
                    self.transaction.raise_event(
                        message="optiSLang initialization failed", stream_name="optislang-instance-stream"
                    )
                    self.transaction.raise_event(
                        message=f"optiSLang initialization failed: {e}", stream_name="optislang-output-stream"
                    )
                    return

            @transaction(self=StepSpec(download=["version", "evaluate_design_example"], upload=["working_dir"]))
            @create_instance("osl_manager", OptislangManager)
            @long_running
            def initialize_osl_instance_with_project_file(self, osl_manager: OptislangManager) -> None:
                """Initialize the optiSLang instance with the project file."""
                try:
                    osl_manager.initialize(self.evaluate_design_example, self.version)
                    self.working_dir = osl_manager.instance.application.project.get_working_dir()  # type: ignore
                except Exception as e:
                    self.transaction.raise_event(
                        message="optiSLang initialization failed", stream_name="optislang-instance-stream"
                    )
                    self.transaction.raise_event(
                        message=f"optiSLang initialization failed: {e}", stream_name="optislang-output-stream"
                    )
                    return
                self.transaction.raise_event(message="optiSLang initialized.", stream_name="optislang-instance-stream")
                self.transaction.raise_event(message="optiSLang initialized.", stream_name="optislang-output-stream")

            @transaction(self=StepSpec(upload=["objective", "working_dir"]))
            @instance("osl_manager")
            def evaluate_reference_design(self, osl_manager: OptislangManager):
                """Evaluate the reference design of the optiSLang project."""
                self.transaction.raise_event(message="Clear Messages", stream_name="optislang-output-stream")
                self.transaction.raise_event(message="Evaluating design...", stream_name="optislang-output-stream")
                try:
                    osl = osl_manager.instance
                    project = osl.application.project
                    # Evaluate reference design
                    root_system = project.root_system  # type: ignore
                    design = root_system.get_reference_design()
                    evaluated_design = root_system.evaluate_design(design)
                    self.objective = str(evaluated_design.objectives[0].value)  # type: ignore
                except Exception as e:
                    self.transaction.raise_event(message="Design evaluation failed", stream_name="optislang-instance-stream")
                    self.transaction.raise_event(
                        message=f"Design evaluation failed: {e}", stream_name="optislang-output-stream"
                    )
                    return
                self.transaction.raise_event(message="Design evaluation succeeded.", stream_name="optislang-instance-stream")
                self.transaction.raise_event(message="Design evaluation succeeded.", stream_name="optislang-output-stream")
                self.transaction.raise_event(
                    message=f"Current objective: {self.objective}.", stream_name="optislang-output-stream"
                )

            @transaction(self=StepSpec(upload=["objective", "working_dir"]))
            @instance("osl_manager")
            @long_running
            def refine_design(self, osl_manager: OptislangManager):
                """Refine the design by modifying the parameters of the reference design."""
                successful_designs: list[Design] = []
                self.transaction.raise_event(message="Clear Messages", stream_name="optislang-output-stream")
                self.transaction.raise_event(message="Refining design...", stream_name="optislang-output-stream")
                try:
                    root_system = osl_manager.instance.application.project.root_system  # type: ignore
                    design = root_system.get_reference_design()
                    evaluated_design = root_system.evaluate_design(design)
                    successful_designs.append(evaluated_design)
                    for i in range(1):
                        design = successful_designs[-1].copy_unevaluated_design()
                        parameters = design.parameters
                        parameter_value = parameters[i].value  # type: ignore
                        parameters[i].value = parameter_value - 1  # type: ignore
                        evaluated_design = root_system.evaluate_design(design)
                        successful_designs.append(evaluated_design)
                        self.objective = str(evaluated_design.objectives[0].value)  # type: ignore

                except Exception as e:
                    self.transaction.raise_event(message="Design refine failed", stream_name="optislang-instance-stream")
                    self.transaction.raise_event(message=f"Design refine failed: {e}", stream_name="optislang-output-stream")
                    return
                self.transaction.raise_event(message="Design refine succeeded.", stream_name="optislang-instance-stream")
                self.transaction.raise_event(message="Design refine succeeded.", stream_name="optislang-output-stream")
                self.transaction.raise_event(
                    message=f"Current objective: {self.objective}.", stream_name="optislang-output-stream"
                )

            @transaction(self=StepSpec())
            @instance("osl_manager")
            def close_osl(self, osl_manager: OptislangManager) -> None:
                """Close the optiSLang instance."""
                self.transaction.raise_event(message="Clear Messages", stream_name="optislang-output-stream")
                self.transaction.raise_event(
                    message="Starting to shutdown the instance.", stream_name="optislang-output-stream"
                )

                try:
                    osl_manager.shutdown()
                except Exception as e:
                    self.transaction.raise_event(message="optiSLang shutdown failed.", stream_name="optislang-instance-stream")
                    self.transaction.raise_event(
                        message=f"optiSLang shutdown failed: {e}", stream_name="optislang-output-stream"
                    )
                    return
                self.transaction.raise_event(message="optiSLang Shutdown.", stream_name="optislang-instance-stream")
                self.transaction.raise_event(
                    message="optiSLang instance shutdown complete.", stream_name="optislang-output-stream"
                )

  .. tab-item:: 2️⃣Frontend
    :name: saf-ex-optislang-product-instance-frontend-tab

    Define the user interface.

    .. dropdown:: Define the step layout
      :open:

      The user interface has four main buttons. Each one triggers a transaction in the step model.

      .. code-block:: python
          :lineno-start: 4
          :caption: layout from ``optislang_instance_page.py``

          from ansys.saf.glow.client import DashClient, callback
          import ansys_web_components_dash as AwcDash

          from ansys_web_components_dash import AwcDashEnum
          from dash_extensions.enrich import Input, Output, State, dcc, html, no_update  # pyright: ignore[reportMissingTypeStubs]
          from dash_iconify import DashIconify

          import dash_mantine_components as dmc
          from ansys.solutions.examples.solution.definition import ExamplesSolution, OptislangStep


          def layout(step: OptislangStep):
              """Layout of the Opstislang step UI."""
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
                          "⚠️ This example requires Opstislang 2024 R2 (24R2) to run.",
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
                          "optiSLang Instance Manager", className="display-3", style={"font-size": "48px", "fontWeight": "bold"}
                      ),
                      html.Br(),
                      html.Hr(className="my-2"),
                      html.Br(),
                      html.P(
                          [
                              "This example demonstrates how to leverage ",
                              html.A(
                                  "PIM",
                                  href="https://dev-docs.solutions.ansys.com/version/stable/user_guide/using_ansys_products/product_instance_management/index.html",
                                  target="_blank",
                                  style={"color": "blue"},
                              ),
                              " to control optiSLang. Click the Launch optiSLang button to start the instance. A "
                              "transaction method will start optiSLang which can be used across all transaction "
                              "methods of the solution. Run optiSLang operations with the Evaluate Design and "
                              "Refine Design buttons. Close optiSLang using the Shutdown button.",
                          ],
                          style={"font-size": "20px"},
                      ),
                      html.Div(
                          [
                              dmc.Button(
                                  "Launch optiSLang",
                                  id="launch_optislang_button",
                                  variant="filled",
                                  radius="xl",
                                  style={"color": "#FFFFFF", "width": "20%"},
                                  leftIcon=DashIconify(icon="streamline:startup-solid"),
                              ),
                              dmc.Button(
                                  "Shutdown optiSLang",
                                  id="shutdown_optislang_button",
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
                          "Once the instance is created, you can use the buttons to evaluate the design and refine it afterward.",
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
                                              "Evaluate Design",
                                              id="evaluate_design_button",
                                              variant="filled",
                                              radius="xl",
                                              style={"color": "#FFFFFF", "width": "50%"},
                                              leftIcon=DashIconify(icon="hugeicons:chart-evaluation"),
                                              disabled=True,
                                          ),
                                          dmc.Button(
                                              "Refine Design",
                                              id="refine_design_button",
                                              variant="filled",
                                              radius="xl",
                                              style={"color": "#FFFFFF", "width": "50%"},
                                              leftIcon=DashIconify(icon="material-symbols:filter-alt"),
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
                                  step, id="optislang-instance-listener", stream_name="optislang-instance-stream"
                              )
                          ]
                      ),
                      html.Div(
                          [
                              DashClient.create_event_listener(
                                  step, id="optislang-output-listener", stream_name="optislang-output-stream"
                              )
                          ]
                      ),
                      dcc.Store(id="optislang-ui-button-state", storage_type="session"),
                      dmc.NotificationsProvider(
                          dmc.Container(id="optislang-notification-container", children=[]),
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
          :caption: initialization callback from ``optislang_instance_page.py``

          @callback(
              Input("launch_optislang_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def init(n_clicks: int, pathname: str) -> bool:
              """Initialize the optiSLang instance."""
              if n_clicks:
                  project = DashClient[ExamplesSolution].get_project(pathname)
                  step = project.steps.optislang_step
                  step.download_example_file()
                  step.initialize_osl_instance_with_project_file()


          @callback(
              Output("launch_optislang_button", "loading", allow_duplicate=True),
              Input("launch_optislang_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def load_init(n_clicks: int, pathname: str):
              """Load the launch optiSLang button."""
              return True

    .. dropdown:: Define the evaluate_design transaction button
      :open:

      * The callback starting the transaction evaluates the design using the optiSLang API.
      * The ``console-logs`` container will display the output after the method has finalized.

      .. code-block:: python
          :lineno-start: 110
          :caption: evaluate_design transaction button callback from ``optislang_instance_page.py``

          @callback(
              Input("evaluate_design_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def evaluate_design(n_clicks: int, pathname: str):
              """Evaluate the reference design in optiSLang."""
              if n_clicks:
                  project = DashClient[ExamplesSolution].get_project(pathname)
                  step = project.steps.optislang_step
                  step.evaluate_reference_design()


          @callback(
              Output("evaluate_design_button", "loading", allow_duplicate=True),
              Input("evaluate_design_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def load_evaluate_design(n_clicks: int, pathname: str):
              """Load the evaluate design button."""
              return True

    .. dropdown:: Define the refine_design transaction button
      :open:

      * The callback starting the transaction refines the design using the optiSLang API.
      * The ``console-logs`` container will display the output after the method has finalized.

      .. code-block:: python
          :lineno-start: 124
          :caption: refine_design transaction button callback from ``optislang_instance_page.py``

          @callback(
              Output("refine_design_button", "loading", allow_duplicate=True),
              Input("refine_design_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def refine_design(n_clicks: int, pathname: str):
              """Refine the design in optiSLang."""
              project = DashClient[ExamplesSolution].get_project(pathname)
              step = project.steps.optislang_step
              step.refine_design()
              return True

    .. dropdown:: Define the shutdown transaction button
      :open:

      * When the :guilabel:`Shutdown Instance` button is clicked, the shutdown callback is activated.
      * The callback starts the transaction to shut down the product instance.

      .. code-block:: python
          :lineno-start: 138
          :caption: shutdown transaction button callback from ``optislang_instance_page.py``

          @callback(
              Input("shutdown_optislang_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def shutdown(n_clicks: int, pathname: str):
              """Shutdown the optiSLang instance."""
              if n_clicks is not None:
                  project = DashClient[ExamplesSolution].get_project(pathname)
                  step = project.steps.optislang_step
                  step.close_osl()


          @callback(
              Output("shutdown_optislang_button", "loading", allow_duplicate=True),
              Input("shutdown_optislang_button", "n_clicks"),
              State("url", "pathname"),
              prevent_initial_call=True,
          )
          def load_shutdown(n_clicks: int, pathname: str):
              """Shutdown the optiSLang instance."""
              return True

    .. dropdown:: Define the logs system.
      :open:

      * Create the ``logs_container`` component and an event listener for the ``optislang-output-listener`` stream to display logs in the UI, as shown in the layout.
      * The method logs will be received through the ``optislang-output-listener`` listener.
      * When the listener receives a message, the callback is activated and updates the logs container as expected.

      .. code-block:: python
          :lineno-start: 138
          :caption: display_the_optislang_output callback from ``optislang_instance_page.py``

          @callback(
              Output("console-logs", "children"),
              Input("optislang-output-listener", "message"),
              State("console-logs", "children"),
              State("url", "pathname"),
          )
          def display_the_optislang_output(message: dict, current_logs: str, pathname: str) -> str:
              """Display optiSLang output."""
              if message:
                  new_content = message["data"].strip('"').replace("\\n", "\n")
                  if new_content == "Clear Messages":
                      return ""
                  combined = (current_logs or "") + "\n" + new_content
                  return combined
              return current_logs

    .. dropdown:: Define the notification system.
      :open:

      * Create the ``dmc.NotificationsProvider`` and an event listener for the ``optislang-instance-listener`` stream to display notifications in the UI, as shown in the layout.
      * To display notifications when a method succeeds or fails, the ``optislang-instance-listener`` must be triggered.
      * When the listener receives a message, the callback is activated and generates the appropriate notification in the UI.

      .. code-block:: python
          :lineno-start: 138
          :caption: update_optislang_ui callback from ``optislang_instance_page.py``

          @callback(
              [
                  Output(button_id, "loading")
                  for button_id in [
                      "launch_optislang_button",
                      "shutdown_optislang_button",
                      "evaluate_design_button",
                      "refine_design_button",
                  ]
              ],
              [
                  Output(button_id, "disabled")
                  for button_id in [
                      "launch_optislang_button",
                      "shutdown_optislang_button",
                      "evaluate_design_button",
                      "refine_design_button",
                  ]
              ],
              Output("optislang-notification-container", "children"),
              Output("optislang-ui-button-state", "data"),
              Input("optislang-instance-listener", "message"),
              Input("url", "pathname"),
              State("optislang-ui-button-state", "data"),
          )
          def update_optislang_ui(
              message: dict, pathname: str, prev_state: dict | None
          ) -> Tuple[List[bool], List[bool], dmc.Notification, dict]:
              """Update the ui."""
              button_ids = [
                  "launch_optislang_button",
                  "shutdown_optislang_button",
                  "evaluate_design_button",
                  "refine_design_button",
              ]
              default_states = {
                  "launch_optislang_button": {
                      "loading": False,
                      "disabled": False,
                  },
                  "shutdown_optislang_button": {
                      "loading": False,
                      "disabled": True,
                  },
                  "evaluate_design_button": {
                      "loading": False,
                      "disabled": True,
                  },
                  "refine_design_button": {
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
                  if message_content == "optiSLang initialized.":
                      prev_state["launch_optislang_button"]["disabled"] = True
                      prev_state["shutdown_optislang_button"]["disabled"] = False
                      prev_state["evaluate_design_button"]["disabled"] = False
                      notification.message = "optiSLang instance launched successfully!"
                      notification.icon = DashIconify(icon="streamline:startup-solid")
                  elif message_content == "optiSLang initialization failed":
                      prev_state["launch_optislang_button"]["disabled"] = False
                      notification.message = "optiSLang initialization failed. Please check the logs."
                      notification.icon = DashIconify(icon="streamline:startup-solid")
                      notification.color = "red"
                      notification.title = "Error"
                  elif message_content == "Design evaluation succeeded.":
                      prev_state["evaluate_design_button"]["disabled"] = True
                      prev_state["refine_design_button"]["disabled"] = False
                      notification.message = "Design evaluated successfully!"
                      notification.icon = DashIconify(icon="hugeicons:chart-evaluation")
                  elif message_content == "Design evaluation failed":
                      prev_state["evaluate_design_button"]["disabled"] = False
                      notification.message = "Design evaluation failed. Please check the logs."
                      notification.icon = DashIconify(icon="hugeicons:chart-evaluation")
                      notification.color = "red"
                      notification.title = "Error"
                  elif message_content == "Design refine succeeded.":
                      notification.message = "Design refined successfully!"
                      notification.icon = DashIconify(icon="material-symbols:filter-alt")
                  elif message_content == "Design refine failed":
                      notification.message = "Design refine failed. Please check the logs."
                      notification.icon = DashIconify(icon="material-symbols:filter-alt")
                      notification.color = "red"
                      notification.title = "Error"
                  elif message_content == "optiSLang Shutdown.":
                      prev_state = default_states
                      notification.message = "optiSLang instance shutdown successfully!"
                      notification.icon = DashIconify(icon="mdi:shutdown")
                  elif message_content == "optiSLang shutdown failed.":
                      prev_state["shutdown_optislang_button"]["disabled"] = False
                      notification.message = "optiSLang instance shutdown failed. Please check the logs."
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
