.. _saf-ex-visor-product-instance:


VISOR Product Instance Manager
###################################

.. topic:: Objective

  Drive a VISOR product instance from a solution. Start VISOR in a
  long-running transaction, show the VISOR viewer, display a simple 
  shape in the viewer, and shut the instance down.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-visor-product-instance-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

Visual Interactive Simulation Object Renderer (VISOR) is a 3D visualization web 
component for Ansys solutions and apps.

This example shows how to create a **product instance manager** for VISOR
using SAF. The product instance manager enables management of the VISOR product 
instance lifecycle, including starting, stopping, and interacting with the instance.

In this example, you learn how to:

- :material-outlined:`rocket_launch;1.25em;saf-objective-icon` Start a
  product instance from a **long-running transaction** decorated with
  ``@create_instance``.
- :material-outlined:`hub;1.25em;saf-objective-icon` Reuse the running
  instance in other **transaction methods** through the ``@instance`` decorator.
- :material-outlined:`web;1.25em;saf-objective-icon` Display the VISOR viewer
  in an isolated iframe using the current instance host and port.
- :material-outlined:`api;1.25em;saf-objective-icon` Interact with the viewer to
  display 3D scenes.
- :material-outlined:`stream;1.25em;saf-objective-icon` Publish progress
  on named **event stream** with ``transaction.raise_event``.
- :material-outlined:`bolt;1.25em;saf-objective-icon` Wire one **callback** per
  button and use **event listeners** to refresh the console logs and notifications.


.. _saf-ex-visor-product-instance-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

.. note::
    To work with a VISOR product instance, be sure to install the ``core-pim`` and
    ``instance-management-visor`` extras from the ``ansys-saf-sdk`` package.
    You can do this by manually editing your ``pyproject.toml``.

    The Dash viewer also requires the ``ansys-visor-viewer`` package:

    .. code-block:: toml

        ansys-saf-sdk = {version = "^0.3.0", extras = ["core-pim", "instance-management-visor"]}
        ansys-visor-viewer = "^1.0.1"

    This will install everything needed to control the VISOR product instance and viewer.
    This example uses PIM as the product instance management system.


.. _saf-ex-visor-product-instance-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To create a product instance manager for VISOR and interact with it,
work through the following sequence of sections.


.. _saf-ex-visor-product-instance-backend:

:material-outlined:`dns;1.25em;sd-text-primary` Backend
---------------------------------------------------------

Create the solution definition.

.. key-concept:: Product instance manager

    A **product instance manager** wraps a running Ansys product session. The
    ``@create_instance`` decorator starts the product and binds the session to a name,
    while the ``@instance`` decorator injects that same session into any other
    transaction method.

.. key-concept:: Instance lifecycle

    A product instance outlives the transaction method that created it. It stays
    available to every transaction method of the solution until a transaction
    explicitly shuts it down.

.. key-concept:: Event streams

    A transaction method reports progress with ``self.transaction.raise_event``.
    Each event is published on a named **stream**, so the frontend can react while
    the transaction is still running.

.. key-concept:: Termination event

    Passing ``enable_termination_event=True`` to ``@transaction`` makes SAF
    automatically raise a structured ``MethodState`` event on a stream
    named after the transaction once it completes or fails, so the frontend
    can track its outcome without parsing log text. The persisted state can
    also be read at any time with ``step.get_long_running_method_state(transaction_name)``.

.. dropdown:: Define the step fields
  :open:

  The step stores the VISOR version, whether the instance is running, and the
  host and port reported by the product manager.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/visor_step.py
    :language: python
    :caption: solution/instance_management/visor_step.py
    :lines: 31-36
    :dedent:

.. dropdown:: Define the step model
  :open:

  * ``start_visor`` is a long-running transaction decorated with
    ``@create_instance("visor_manager", VisorManager)``. It initializes VISOR,
    stores the current host and port, marks the instance as started, and
    emits progress messages.
  * ``show_shape`` reuses the running manager with ``@instance("visor_manager")``
    and sends the bundled ``cube.vtm`` scene to VISOR with
    ``Metadata(name="Cube", unit="m")``.
  * ``shutdown_visor`` reuses the same manager, shuts down VISOR, and sets
    ``visor_started`` to ``False``.
  * The shape files are stored in the step package under
    ``instance_management/shapes``. The ``cube.vtm`` file references the
    ``cube/cube_0.vtp`` geometry file.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/visor_step.py
    :language: python
    :caption: solution/instance_management/visor_step.py
    :pyobject: VisorStep.start_visor

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/visor_step.py
    :language: python
    :caption: solution/instance_management/visor_step.py
    :pyobject: VisorStep.show_shape

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/visor_step.py
    :language: python
    :caption: solution/instance_management/visor_step.py
    :pyobject: VisorStep.shutdown_visor


.. _saf-ex-visor-product-instance-frontend:

:material-outlined:`web;1.25em;sd-text-primary` Frontend
----------------------------------------------------------

Expose the solution definition in the UI.

.. key-concept:: Callback

    A **callback** is a Dash-decorated function that fires in response to a UI
    event. In a SAF solution, callbacks reach the backend through
    ``project.steps.visor_step``, invoke transaction methods, and update the
    component properties that control the page.

.. key-concept:: Event listener

    ``DashClient.create_event_listener`` subscribes a component to a backend
    event stream. This page listens to ``visor-output-stream`` for console
    messages and ``start-visor`` for the structured startup termination event.

.. key-concept:: Isolated viewer

    The VISOR viewer is placed in an iframe instead of directly mounting the
    generated Dash component in the page. The iframe has its own DOM, React
    state, WebSocket, and WebAssembly runtime. Removing and recreating the
    iframe therefore removes stale browser state when VISOR is stopped,
    restarted, or revisited after navigation.

.. dropdown:: Register the VISOR viewer endpoints
  :open:

  The VISOR package provides the JavaScript, CSS, theme, and font endpoints
  used by the iframe. Register them on the Dash server before the UI starts.
  ``GLOW_UI_PATH_PREFIX`` is passed to both endpoint registration and the
  iframe so the viewer also works when the UI is mounted below a URL prefix.

  .. code-block:: python

      import os

      from visordash import init_endpoints

      VISOR_BASE_PATH = os.getenv("GLOW_UI_PATH_PREFIX", "/").rstrip("/")
      init_endpoints(app, base_path=VISOR_BASE_PATH)

  These endpoints must remain registered even though the viewer itself is
  created in ``visor_instance_page.py``.

.. dropdown:: Create the isolated viewer
  :open:

  ``_create_visor_viewer`` serializes the current VISOR host, port, and UI
  prefix into ``window.__visorArgs``. The iframe then loads the Visordash CSS
  and JavaScript assets and creates its own ``VisorContainer`` element.
  Because the host and port come from the persisted step fields, the viewer
  connects to the new instance after a stop-and-restart cycle.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/visor_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/visor_instance_page.py
    :pyobject: _create_visor_viewer

.. dropdown:: Compute the initial layout
  :open:

  ``layout`` reads the persisted ``visor_started``, ``visor_host``, and
  ``visor_port`` fields. If VISOR is already running when the page is opened,
  it recreates the isolated viewer with the current connection information.
  This makes the page recover the viewer after navigation without starting a
  second instance.

  The controls card contains:

  * A rocket action icon to start VISOR.
  * A shutdown action icon to stop VISOR.
  * A **Show Shape** button to display the cube.

  The logs card displays VISOR output and provides a clear-logs action. The
  viewer card is placed below the controls and logs and fills the available
  width. The controls and logs use responsive grid spans: they stack at
  smaller widths and use 3/9 columns at the ``lg`` breakpoint and above.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/visor_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/visor_instance_page.py
    :pyobject: layout

.. dropdown:: Mount the event listeners
  :open:

  The layout mounts two event listeners:

  * ``output-listener`` subscribes to ``visor-output-stream`` and receives
    human-readable messages such as initialization, cube loading, and shutdown
    progress.
  * ``start-visor-listener`` subscribes to ``start-visor`` and receives the
    structured termination event for the long-running startup transaction.

  The startup listener is used by both the control-state callback and the
  viewer-display callback.

.. dropdown:: Start VISOR from the launch action
  :open:

  When the start action is clicked, ``start_visor`` calls the backend
  transaction and immediately shows a loading notification. The start button
  is disabled and its loading spinner replaces the rocket icon while the
  long-running transaction executes.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/visor_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/visor_instance_page.py
    :pyobject: start_visor

.. dropdown:: Synchronize startup controls and notifications
  :open:

  ``sync_start_controls_on_backend_event`` parses the structured
  ``MethodState`` event from the ``start-visor`` listener.

  * While startup is running, all three controls remain disabled and the start
    action continues to show its loading state.
  * On success, the start action stops loading, while Stop and Show Shape are
    enabled.
  * On failure, the start action becomes available again and Stop and Show
    Shape remain disabled.
  * ``handle_method_event`` replaces the loading notification with a success
    or failure notification.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/visor_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/visor_instance_page.py
    :pyobject: sync_start_controls_on_backend_event

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/helpers.py
    :language: python
    :caption: ui/helpers.py
    :pyobject: handle_method_event

.. dropdown:: Display the viewer after startup
  :open:

  ``display_visor_viewer`` listens to the completed startup event. It reads
  the persisted host and port and creates a new isolated iframe. It does not
  create the viewer on a failed startup, and it raises an explicit error if a
  completed transaction did not persist connection information.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/visor_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/visor_instance_page.py
    :pyobject: display_visor_viewer

.. dropdown:: Display the cube
  :open:

  The **Show Shape** callback invokes the synchronous ``show_shape`` transaction.
  The transaction updates the running VISOR scene with the bundled cube, while
  the callback displays a success notification.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/visor_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/visor_instance_page.py
    :pyobject: show_visor_shape

.. dropdown:: Stop VISOR and clear the viewer
  :open:

  The shutdown callback calls ``shutdown_visor`` on the step. On success, it
  displays a success notification, removes the iframe, enables Start, and
  disables Stop and Show Shape. On failure, it displays an error notification
  and leaves the existing viewer and control state unchanged.

  Removing the iframe is important because it disposes of the browser-side
  viewer state and prevents the next VISOR instance from reusing an old
  WebSocket or React runtime.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/visor_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/visor_instance_page.py
    :pyobject: shutdown_visor

.. dropdown:: Define the logs system
  :open:

  ``display_visor_output`` appends each message received on
``visor-output-stream`` to the console log. The log panel shows messages
received during the current page session, and ``clear_console_logs`` resets
the visible log content when the clear action is selected.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/visor_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/visor_instance_page.py
    :pyobject: display_visor_output

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/visor_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/visor_instance_page.py
    :pyobject: clear_console_logs

  Now that your implementation is complete, continue to the
  :ref:`saf-ex-visor-product-instance-testing` section.


.. _saf-ex-visor-product-instance-testing:

:octicon:`verified;1em;sd-text-primary` Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-visor-product-instance-feature-highlight>` section.
