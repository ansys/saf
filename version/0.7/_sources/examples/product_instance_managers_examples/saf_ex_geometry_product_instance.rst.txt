.. _saf-ex-geometry-product-instance:


Geometry Product Instance Manager
##################################

.. topic:: Objective

  Drive an Ansys Geometry service from a solution. Launch the modeler in a long-running
  transaction, extrude a sketch into a slot through the Geometry API, read back the active
  design, and shut the instance down.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-geometry-product-instance-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

PyGeometry is a versatile library for geometric modeling and spatial computation, supporting a wide range of applications including shape representation, transformation operations, and spatial analysis across simulations involving multiple physical phenomena.

This example demonstrates how to create a **product instance manager** for Geometry products using SAF. The product instance manager enables management of the Geometry product instance lifecycle, including starting, stopping, and accessing the product's API.

In this example, you learn how to:

- :material-outlined:`rocket_launch;1.25em;saf-objective-icon` Launch a Geometry instance from a
  **long-running transaction** decorated with ``@create_instance``.
- :material-outlined:`hub;1.25em;saf-objective-icon` Reuse the running instance in the other
  **transaction methods** through the ``@instance`` decorator.
- :material-outlined:`api;1.25em;saf-objective-icon` Call the **Geometry API** to extrude a sketch
  into a slot and to read the active design.
- :material-outlined:`data_object;1.25em;saf-objective-icon` Store the resulting face count, edge
  count, and design name in **typed step fields**.
- :material-outlined:`stream;1.25em;saf-objective-icon` Stream progress messages to the UI with
  ``raise_event`` and a ``DashClient`` **event listener**.
- :material-outlined:`notifications;1.25em;saf-objective-icon` Drive **button states and
  notifications** from the event stream, then shut the instance down.


.. _saf-ex-geometry-product-instance-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

.. note::
    This example requires the Geometry 2025 R2 Service Pack 4 (25R2 SP4) product to be installed on your machine.
    To work with a Geometry product instance, be sure to install the ``core-pim`` and ``instance-management-geometry`` extras from the ``ansys-saf-sdk`` package. You can do this by manually editing your ``pyproject.toml``.

    .. code-block:: toml

        ansys-saf-sdk = {version = "^0.3.0", extras = ["core-pim", "instance-management-geometry"]}

    This will install the supported version of ``ansys-geometry-core`` to control the Geometry product instances.
    This example uses PIM as the product instance management system. If you want to use HPS instead, replace the ``core-pim`` extra with ``core-hps``.
    For more information, see :ref:`instance_management_configuration`.


.. _saf-ex-geometry-product-instance-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To create a product instance manager for Geometry products and interact with it, work through the following sequence of sections.


.. _saf-ex-geometry-product-instance-backend:

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

.. key-concept:: Termination event

    Passing ``enable_termination_event=True`` to ``@transaction`` makes SAF automatically raise a
    structured ``MethodState`` event on a stream named after the transaction once it completes or
    fails, so the frontend can track its outcome without parsing log text. ``launch_geometry``,
    ``extrude_slot``, and ``get_active_design`` are long-running and opt into this behavior;
    ``shutdown_geometry`` is a regular transaction and does not raise a termination event.

.. dropdown:: Define the step fields
  :open:

  ``geometry_available`` tracks whether a Geometry instance is currently running, while
  ``body_faces``, ``body_edges``, and ``active_design_name`` store the results of the Geometry
  API calls.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/geometry_step.py
    :language: python
    :caption: solution/instance_management/geometry_step.py
    :lines: 33-37
    :dedent:

.. dropdown:: Define the step model
  :open:

  * The ``launch_geometry`` long-running transaction is decorated with ``@create_instance`` to create an instance of the Geometry product manager, ``GeometryManager``, while the ``shutdown_geometry`` transaction is decorated with ``@instance`` to reuse and shut down the existing instance. Unlike the other transactions, ``shutdown_geometry`` is not long-running and does not raise a termination event.
  * The ``extrude_slot`` and ``get_active_design`` transactions are decorated with ``@instance`` to indicate they operate on the existing product instance, and call the Geometry API to extrude a slot and to read the active design, respectively.
  * ``launch_geometry``, ``extrude_slot``, and ``get_active_design`` pass ``enable_termination_event=True`` so the frontend can track their completion status.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/geometry_step.py
    :language: python
    :caption: solution/instance_management/geometry_step.py
    :pyobject: GeometryStep.launch_geometry

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/geometry_step.py
    :language: python
    :caption: solution/instance_management/geometry_step.py
    :pyobject: GeometryStep.extrude_slot

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/geometry_step.py
    :language: python
    :caption: solution/instance_management/geometry_step.py
    :pyobject: GeometryStep.get_active_design

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/geometry_step.py
    :language: python
    :caption: solution/instance_management/geometry_step.py
    :pyobject: GeometryStep.shutdown_geometry


.. _saf-ex-geometry-product-instance-frontend:

:material-outlined:`web;1.25em;sd-text-primary` Frontend
----------------------------------------------------------

Expose the solution definition in the UI.

.. key-concept:: Callback

    A **callback** is a Dash-decorated function that fires in response to a UI event. In a
    SAF solution, callbacks reach the backend through ``project.steps.<step_name>``, read or
    write fields, and invoke transaction methods. No manual HTTP calls are needed.

.. key-concept:: Event listener

    ``DashClient.create_event_listener()`` subscribes a page to a backend stream. Each message
    fires a callback, which is how the console logs and the button states stay in sync with a
    long-running transaction.

.. dropdown:: Define the step layout
  :open:

  * The layout builds a controls card, with icon buttons to launch and shut down the instance and
    buttons to extrude a slot and get the active design, and a logs card.
  * Unlike the other instance management pages, the event listeners are created directly in the
    layout instead of through a separate ``mount_event_listeners`` callback: ``output-listener``
    subscribes to the free-form progress messages on ``geometry-output-stream``, while
    ``launch-geometry-listener``, ``extrude-slot-listener``, and ``get-active-design-listener``
    each subscribe to the termination event of one long-running transaction.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/geometry_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/geometry_instance_page.py
    :pyobject: layout

.. dropdown:: Launch the instance
  :open:

  * When the :guilabel:`Launch Geometry` button is clicked, ``start_geometry`` starts the
    ``launch_geometry`` long-running transaction and shows a loading notification.
  * When the ``launch-geometry-listener`` receives the termination event, ``enable_geometry_extrude_slot``
    turns it into a success or error notification and enables the shutdown and extrude slot
    buttons.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/geometry_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/geometry_instance_page.py
    :pyobject: start_geometry

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/geometry_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/geometry_instance_page.py
    :pyobject: enable_geometry_extrude_slot

.. dropdown:: Extrude a slot
  :open:

  * When the :guilabel:`Extrude Slot` button is clicked, ``extrude_slot`` starts the
    ``extrude_slot`` transaction and shows a loading notification.
  * When the ``extrude-slot-listener`` receives the termination event, ``display_extrude_slot_notification``
    turns it into a success or error notification and enables the get active design button.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/geometry_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/geometry_instance_page.py
    :pyobject: extrude_slot

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/geometry_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/geometry_instance_page.py
    :pyobject: display_extrude_slot_notification

.. dropdown:: Get the active design
  :open:

  * When the :guilabel:`Get Active Design` button is clicked, ``get_active_design`` starts the
    ``get_active_design`` transaction and shows a loading notification.
  * When the ``get-active-design-listener`` receives the termination event,
    ``display_get_active_design_notification`` turns it into a success or error notification.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/geometry_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/geometry_instance_page.py
    :pyobject: get_active_design

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/geometry_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/geometry_instance_page.py
    :pyobject: display_get_active_design_notification

.. dropdown:: Shut down the instance
  :open:

  * When the :guilabel:`Shutdown Geometry` button is clicked, ``shutdown_geometry`` calls
    ``step.shutdown_geometry()`` directly and shows the result as a notification. Because
    ``shutdown_geometry`` is not a long-running transaction, no event listener is needed: the
    callback updates the button states as soon as the call returns.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/geometry_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/geometry_instance_page.py
    :pyobject: shutdown_geometry

.. dropdown:: Define the logs system.
  :open:

  * ``display_geometry_output`` appends every message received on the ``output-listener`` stream
    to the console logs container, and ``clear_console_logs`` resets it.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/geometry_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/geometry_instance_page.py
    :pyobject: display_geometry_output

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/geometry_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/geometry_instance_page.py
    :pyobject: clear_console_logs

  Now that your implementation is complete, continue to the :ref:`saf-ex-geometry-product-instance-testing` section.


.. _saf-ex-geometry-product-instance-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-geometry-product-instance-feature-highlight>` section.

