.. _best_practices_frontend:

########
Frontend
########


.. _best_practices_project_injection:

Project injection (required pattern)
=====================================

.. admonition:: Best practice
   :class: best-practice

   - Always use ``State("url", "pathname")`` + type-hint with the Solution class.
   - Never use ``DashClient.get_project()``—removed in SAF GLOW Engine 2.0.

The type-hint on the callback parameter tells SAF GLOW Engine to inject the current project
automatically. The parameter type must be your ``Solution`` class (not ``StepModel``).

.. code-block:: python
   :caption: Correct — project injection via type-hint

   from ansys.saf.glow.client import callback
   from dash_extensions.enrich import Input, Output, State


   @callback(
       Output("result-output", "children"),
       Input("compute-btn", "n_clicks"),
       State("url", "pathname"),
       prevent_initial_call=True,
   )
   def on_compute(n_clicks: int, project: MySolution) -> str:
       step = project.steps.setup
       step.compute()
       return f"Result: {step.result}"

.. code-block:: python
   :caption: Transferring user input to the step data model

   @callback(
       Output("hps-progress", "children", allow_duplicate=True),
       Input("second-arg-input", "value"),
       State("url", "pathname"),
       prevent_initial_call=True,
   )
   def bind_second_arg(second_arg: str, project: MySolution) -> str:
       """Transfer the newly entered value into the step data model."""
       step = project.steps.hps_job_submission_step
       step.reset()
       if second_arg != "":
           step.second_arg = float(second_arg)
       return step.status


.. _best_practices_event_listeners:

Event listeners for long-running methods
=========================================

.. admonition:: Best practice
   :class: best-practice

   - Do NOT use ``dcc.Interval`` for monitoring long-running methods.
   - Use ``dmc.Notification`` (via ``dmc.NotificationsProvider``) to display status updates
     triggered by WebSocket events—avoid ``dmc.Alert`` for transient status messages, as
     notifications are non-intrusive and auto-dismiss.

The backend transaction must explicitly enable the termination event so the frontend can
listen for completion:

.. code-block:: python
   :caption: Backend — ``enable_termination_event=True`` is required

   @transaction(self=StepSpec(upload=["result", "progress"]), enable_termination_event=True)
   @long_running
   def heavy_computation(self) -> None:
       for i in range(100):
           self.progress = i / 100.0
           self.transaction.upload(["progress"])
       self.result = [1.0, 2.0, 3.0]

.. code-block:: python
   :caption: Frontend layout — register the WebSocket event listener

   DashClient.create_event_listener(step, stream_name="heavy-computation", id="computation-ws")

.. code-block:: python
   :caption: Frontend callback — react to the WebSocket event

   @callback(
       Output("status", "children"),
       Input("computation-ws", "message"),
       State("url", "pathname"),
       prevent_initial_call=True,
   )
   def on_completion(message: dict, project: MySolution) -> str:
       method_state = MethodState.model_validate_json(message["data"])
       if method_state.status.value == "Completed":
           return f"Result: {project.steps.analysis.result}"
       return f"Status: {method_state.status.value}"

``enable_termination_event=True`` must be set on the ``@transaction`` decorator for the
event listener to receive completion/failure notifications. Events are pushed via
WebSocket—no polling loop is needed.


.. _best_practices_dict_fields:

Dict fields—copy before modify
==================================

.. admonition:: Best practice
   :class: best-practice

   - Never mutate nested values in place—GLOW tracks field-level changes, not nested
     mutations.

SAF GLOW Engine detects changes at the field level, not inside nested structures. Always read the full
value, modify the copy, and write the whole value back.

.. code-block:: python
   :caption: Incorrect — in-place mutation (change is not detected)

   step = project.steps.my_step
   step.data_form["number_input"] = new_value  # GLOW does NOT detect this

.. code-block:: python
   :caption: Correct — read, modify, write back

   step = project.steps.my_step
   data = step.data_form  # Read the whole dict
   data["number_input"] = new_value  # Modify the copy
   step.data_form = data  # Write the whole dict back


.. _best_practices_component_priority:

Component priority
===================

.. admonition:: Best practice
   :class: best-practice

   - Prefer Mantine components (``dmc``) over Bootstrap (``dbc``) for all UI elements. Use
     standard Dash components (``dcc``, ``html``) only for primitives.
   - Use ``ansys.solutions.dash_super_components`` for advanced components like
     ``InputForm`` and ``Tree``.
   - Use ``DashIconify`` for icons to access a wide range of icon sets.
   - Use ``Visordash`` for server-side 3D visualization.
   - Use Dash Super Components to simplify UI development and reduce boilerplate code.
     Super Components provide higher-level abstractions for common UI patterns, making it
     easier to build complex interfaces with less code.


.. _best_practices_app_level_rules:

App-level rules
================

SAF GLOW Engine  starts the Dash server automatically. The ``callback`` decorator must be imported from
``ansys.saf.glow.client``, not from Dash directly.

.. admonition:: Best practice
   :class: best-practice

   - Never call ``app.run_server()``—GLOW starts the server.
   - Never reference ``app`` outside ``app.py``.
   - Always import ``callback`` from ``ansys.saf.glow.client``.
   - Type callback parameters and return values—while not strictly enforced by the
     framework, typing all callback arguments and return types is strongly recommended for
     clarity, traceability, and IDE support.
   - Use ``prevent_initial_call=True`` for action callbacks.
   - Batch reads with ``get_fields()`` (each access is an HTTP call).
   - Disable trigger buttons during long-running execution.
   - Never use ``raise PreventUpdate``—use ``return dash.no_update`` instead.
