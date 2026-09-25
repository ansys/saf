.. _test_solution_ui:

Solution UI testing
####################


Test the UI using ``init_dashclient``
=====================================

The ``init_dashclient`` fixture sets up the Dash client environment and ensures that all API calls are routed
through the test infrastructure, allowing you to test Dash logic with real responses and no external dependencies.

All the examples below assume that you are testing a multi-page Dash application, which typically has a ``dash.register_page`` call at the top level of each page module. In this case, you need to use the ``dash.testing.ignore_register_page`` context manager to ignore ``register_page`` calls when importing the page modules in your tests. This is necessary because Dash raises an error if ``register_page`` is called before a Dash app is instantiated (for example, when importing page modules in a test). If you are testing a single-page Dash application, or your ``dash.register_page`` calls are in a separate file, you can omit this context manager.

.. warning::

   SAF doesn't support executing your callback with ``kwargs`` when using project injection.


Example
--------

For the tests, we are going to use a minimal SAF-based solution created with the SAF CLI ``saf new`` command.
This solution generated from the template has a simple Dash UI page, which includes a callback to execute a transaction
and set and retrieve some step fields.

.. code-block:: python

    @callback(
        Output("result", "children"),
        Input("calculate", "n_clicks"),
        State("first-arg", "value"),
        State("second-arg", "value"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def calculate(n_clicks: int, first_arg: int, second_arg: int, project: MySolution):
        """Using project injection."""
        step = project.steps.first_step
        step.first_arg = first_arg
        step.second_arg = second_arg
        step.calculate()
        return step.result


To test it, use the fixture ``init_dashclient`` in your test function and run your callback. You must use the fixture ``project_name`` as a value of ``pathname``.

.. code-block:: python

    from dash.testing import ignore_register_page

    with ignore_register_page():
        from ansys.solutions.my_solution.ui.pages.first_page import calculate

    pytestmark = [pytest.mark.usefixtures("init_dashclient")]


    def test_callback(project_name: str):
        assert calculate(1, 1, 2, project_name) == (3.0, True)  # This works!
        assert calculate(n_clicks=1, first_arg=1, second_arg=2, pathname=project_name) == (3.0, True)  # This does not work!

.. note:: Even if SAF GLOW Engine automatically injects the project when running the solution, you still need to pass the pathname argument when manually calling the callback function.


Test WebSocket event consumption on the UI
=============================================

The ``dash_http_client`` fixture sets up a Dash test client that allows you to test WebSocket event streams
emitted from transactions in your solution.


Example
--------

Given a Dash callback that triggers the ``trigger_event`` transaction which raises an event:

.. code-block:: python

    @callback(
        Input("start-transaction", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def trigger_transaction_event(n_clicks: int, project: MySolution) -> None:
        if n_clicks > 0:
            step = project.steps.first_step
            step.trigger_event()

.. code-block:: python

    @transaction(self=StepSpec())
    def trigger_event(self) -> None:
        self.transaction.raise_event(message={"message": "testing!"}, stream_name="my-stream")

Then, the event message can be tested as follows:

.. code-block:: python

    from dash.testing import ignore_register_page

    with ignore_register_page():
        from ansys.solutions.my_solution.ui.pages import first_page

    pytestmark = [pytest.mark.usefixtures("init_dashclient")]


    def test_event_triggered_from_callback(dash_http_client: TestClient, project_name: str):
        # Set the WebSocket URL for the event stream
        ws_url = f"/events/{project_name}/steps/first-step/streams/my-stream"
        with dash_http_client.websocket_connect(ws_url) as ws:
            # Trigger the callback that starts the transaction
            first_page.trigger_transaction_event(1, project_name)
            # Receive the event from the stream
            event = ws.receive_json()
            assert event["message"] == "testing!"

If the transaction raises multiple events, you can receive and verify them in sequence:

.. code-block:: python

    @transaction(self=StepSpec())
    def trigger_event(self) -> None:
        self.transaction.raise_event(message={"message": "first_message"}, stream_name="my-stream")
        self.transaction.raise_event(message={"message": "second_message"}, stream_name="my-stream")

.. code-block:: python

    from dash.testing import ignore_register_page

    with ignore_register_page():
        from ansys.solutions.my_solution.ui.pages import first_page

    pytestmark = [pytest.mark.usefixtures("init_dashclient")]


    def test_multiple_events_from_transaction(dash_http_client: TestClient, project_name: str):
        # Set the WebSocket URL for the event stream
        ws_url = f"/events/{project_name}/steps/first-step/streams/my-stream"
        with dash_http_client.websocket_connect(ws_url) as ws:
            # Trigger the callback that starts the transaction
            first_page.trigger_transaction_event(1, project_name)
            # Receive the first event from the stream
            event_1 = ws.receive_json()
            assert event_1["message"] == "first_message"
            # Receive the second event from the stream
            event_2 = ws.receive_json()
            assert event_2["message"] == "second_message"

If the transaction raises a termination event, you can also connect to that WebSocket stream and verify the termination event.

.. code-block:: python

    @transaction(enable_termination_event=True, self=StepSpec())
    def trigger_event(self) -> None:
        self.transaction.raise_event(message={"message": "testing!"}, stream_name="my-stream")

.. code-block:: python

    from dash.testing import ignore_register_page

    with ignore_register_page():
        from ansys.solutions.my_solution.ui.pages import first_page

    pytestmark = [pytest.mark.usefixtures("init_dashclient")]


    def test_transaction_termination_event(dash_http_client: TestClient, project_name: str):
        # Set the WebSocket URL for the termination event stream
        termination_event_ws_url = f"/events/{project_name}/steps/first-step/streams/trigger-event"
        with dash_http_client.websocket_connect(termination_event_ws_url) as termination_ws:
            # Trigger the callback that starts the transaction
            first_page.trigger_transaction_event(1, project_name)
            # Receive the termination event from the trigger-event stream
            termination_event = termination_ws.receive_json()
            assert termination_event["status"] == "completed"

.. note:: The stream name for the termination event is derived from the transaction method name.

It is also possible to emulate the behavior of Dash event listeners by passing the received event data to a callback function,
putting the event data inside a dictionary with the key ``data``:

.. code-block:: python

    @callback(
        Output("event_message", "children"),
        Input("my_ws", "event"),
        prevent_initial_call=True,
    )
    def message(event: dict) -> str:
        if message:
            return f"Received message: {message['data']}"
        else:
            return "No message received yet."

.. code-block:: python

    from dash.testing import ignore_register_page

    with ignore_register_page():
        from ansys.solutions.my_solution.ui.pages import first_page

    pytestmark = [pytest.mark.usefixtures("init_dashclient")]


    def test_event_callback_emulation(dash_http_client: TestClient, project_name: str):
        # Set the WebSocket URL for the event stream
        ws_url = f"/events/{project_name}/steps/first-step/streams/my-stream"
        with dash_http_client.websocket_connect(ws_url) as ws:
            # Trigger the callback that starts the transaction
            first_page.trigger_transaction_event(1, project_name)
            # Receive the event from the stream
            event = ws.receive_json()
            # Emulate dash-extensions event listener behavior, which passes {"data": event} to the callback
            assert first_page.message({"data": event}) == "Received message: {'message': 'testing!'}"
