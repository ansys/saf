.. _events:

Events
#######

SAF GLOW Engine  supports event propagation from a transaction method via websockets, allowing events to be consumed by connecting to the websocket, for instance, from a Dash application.

Details:

* Websockets are specific to a given project, step, and stream name. Only events matching these criteria will be received.
* Multiple websocket connections can be established for the same event stream, and messages are sent to all connected websockets.
* Events are discarded if no websockets are connected. Once one websocket is connected, only messages received since then are sent. Subsequent websockets will only receive new events.
* Events are cleared when the GLOW API server stops.


Raise an event in a transaction method
======================================

For raising an event in a transaction method use ``self.transaction.raise_event(message: Any, stream_name: str | None = None)``:

.. code-block:: python

    class MyStep(StepModel):

        @transaction(self=StepSpec())
        def my_transaction(self) -> None:
            ...
            self.transaction.raise_event(message="testing!")
            ...

Where ``message`` is a ``jsonable`` object. Therefore, you can also send custom data types.

.. code-block:: python

    class CustomTypeXYZ(BaseModel):
        x: int
        y: int
        z: int


    class MyStep(StepModel):

        @transaction(self=StepSpec(download=["my_custom_object"]))
        def stream_custom_data(self) -> None:
            self.transaction.raise_event(message=CustomTypeXYZ(x=1, y=2, z=3))

By default, the stream name is the method name with hyphens instead of underscores. Thus, the messages for the code above can be received by connecting to the websockets: ``/events/projects/{project_id}/steps/my-step/streams/my-transaction`` and ``/events/projects/{project_id}/steps/my-step/streams/stream-custom-data`` respectively.

You can also specify a custom stream name using the ``stream_name`` parameter:

.. code-block:: python

    class MyStep(StepModel):

        @transaction(self=StepSpec())
        def my_transaction(self) -> None:
            ...
            self.transaction.raise_event(message="testing!", stream_name="my-stream")
            ...

The websocket URL will then be: ``/events/projects/{project_id}/steps/my-step/streams/my-stream``.


Raise transaction termination events
====================================

It is possible to configure a transaction to send an event when it finishes. This event contains a serialization of the ``MethodState``
object corresponding to the execution of that transaction. This is configured by setting the ``enable_termination_event`` keyword
argument to ``True`` when calling the ``transaction`` method decorator as in the example below. ``enable_termination_event`` defaults
to ``False``.

.. code:: python

    class MyStep(StepModel):

        @transaction(self=StepSpec(), enable_termination_event=True)
        def transaction_with_termination_event(self) -> None:
            ...
            return

The event is sent whether the transaction finishes successfully or due to an error, and it is sent through the transaction's default
stream, that is, the one using the transaction name as the stream name replacing underscores with hyphens. The contents of the ``MethodState`` object can be accessed then using:  ``/events/projects/{project_id}/steps/my-step/streams/transaction-with-termination-event``.


Receive events in a Dash application
====================================

The ``DashClient`` provides a method called ``DashClient.create_event_listener(step: StepModel, stream_name: str, id: str)`` for creating websockets. The parameters are the ``step``, ``stream_name`` and a websocket ``id`` that you can later use in other callbacks to handle the messages received through the websocket.

For example, you can include the websocket when defining the page layout and parse the messages in a callback:

.. code-block:: python

    def layout(step: MyStep):
        return [html.Div([DashClient.create_event_listener(step, stream_name="my-stream", id="ws")])]


    @callback(
        Output("event_message", "children"),
        Input("ws", "message"),
        prevent_initial_call=True,
    )
    def message(message):
        if message:
            return f"Received message: {message}"

You can also create a websocket within a callback:

.. code-block:: python

    def layout(step: MyStep):
        return [
            html.Button("Create event listener", id="create_event_listener"),
            html.Div(id="event_listener"),
        ]


    @callback(
        Input("create_event_listener", "n_clicks"),
        Output("event_listener", "children"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def receive_events(trigger, project: MySolution):
        step = project.steps.my_step
        ws = DashClient.create_event_listener(step, stream_name="my-stream", id="ws")
        return ws

In the case of termination events, the ``MethodState`` object can be deserialized as follows:

.. code-block:: python

    def layout(step: MyStep):
        return [
            html.Div([DashClient.create_event_listener(step, stream_name="transaction-with-termination-event", id="ws")])
        ]


    @callback(
        Output("event_message", "children"),
        Input("ws", "message"),
        prevent_initial_call=True,
    )
    def message(message):
        if message:
            method_state = MethodState.model_validate_json(message["data"])
            return f"Transaction finished with status '{method_state.status.value}'"


In the case of custom data types, if the custom type is a ``BaseModel`` type, Pydantic features can be used for building the concrete type of the object:

.. code-block:: python

    from ansys.solutions.my_solution.solution.my_step import CustomTypeXYZ


    def layout(step: MyStep):
        return [html.Div([DashClient.create_event_listener(step, stream_name="my-stream", id="my_ws")])]


    @callback(
        Output("event_message", "children"),
        Input("my_ws", "message"),
        prevent_initial_call=True,
    )
    def message_custom_data(message):
        my_custom_type_object = CustomTypeXYZ.model_validate_json(message["data"])
        return my_custom_type_object

For more information, see `Dash documentation for websockets <https://www.dash-extensions.com/components/websocket>`_.


Receive events in on-prem deployments
=====================================

It's important to consider that websockets are created client-side in the UI application, so the address used to establish the websocket with the API server must be accessible from the user/client, not the UI server. This holds true even if the address is configured during the UI server launch.

For Desktop deployments, the Solution user and UI server can use the same address, and SAF GLOW Engine  automatically resolves the address required from the GLOW_API_URL used when launching the UI server. However, in DockerCompose deployments, the Solution user and UI server do not share the same connectivity with the API server. In this case, you must configure the :envvar:`GLOW_WS_EVENTS_ADDR` in the UI server environment with the correct value. For example, the UI container may connect internally with the API container using ``http://api-container-name:internal_api_port``, while the websocket might use ``ws://localhost:external_api_port`` in single-node deployments.

When using secure connections such as ``https``, you need to configure the :envvar:`GLOW_WS_EVENTS_ADDR` with the ``wss://`` protocol.

Refer to the :ref:`environment_variables` section for a detailed list of SAF GLOW Engine  configuration options.
