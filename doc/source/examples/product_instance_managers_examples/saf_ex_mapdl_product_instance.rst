.. _saf-ex-mapdl-product-instance:


MAPDL Product Instance Manager
################################

.. topic:: Objective

  Drive an Ansys Mechanical APDL (MAPDL) product from a solution. Start the product instance in
  a long-running transaction, call the MAPDL API to build, solve, and postprocess a 2D solenoid
  actuator model, stream the solver output to the UI, then shut the instance down.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-mapdl-product-instance-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

PyMAPDL provides a robust Python interface to Ansys Mechanical APDL, allowing users to automate finite element analyses, integrate seamlessly with Python data processing libraries, and optimize workflows across structural, thermal, and coupled physics simulations.

This example shows how to create a **product instance manager** for PyMAPDL using SAF. The product instance manager enables management of the MAPDL product instance lifecycle, including starting, stopping, and accessing the product's API.

In this example, you learn how to:

- :material-outlined:`rocket_launch;1.25em;saf-objective-icon` Start a product instance from a
  **long-running transaction** decorated with ``@create_instance``.
- :material-outlined:`hub;1.25em;saf-objective-icon` Reuse the running instance in the other
  **transaction methods** through the ``@instance`` decorator.
- :material-outlined:`api;1.25em;saf-objective-icon` Call the **MAPDL API** to set up the finite
  element model, solve it, and postprocess the results.
- :material-outlined:`stream;1.25em;saf-objective-icon` Publish progress on named **event
  streams** with ``transaction.raise_event``.
- :material-outlined:`power_settings_new;1.25em;saf-objective-icon` **Shut down** the product
  instance from a dedicated transaction method.
- :material-outlined:`bolt;1.25em;saf-objective-icon` Wire one **callback** per button and use
  **event listeners** to refresh the console logs and the notifications.


.. _saf-ex-mapdl-product-instance-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

.. note::
    This example requires the MAPDL 2025 R2 SP4 (25R2 SP4) product to be installed on your machine.
    To work with a MAPDL product instance, be sure to install the ``core-pim`` and ``instance-management-mapdl`` extras from the ``ansys-saf-sdk`` package. You can do this by manually editing your ``pyproject.toml``.

    .. code-block:: toml

        ansys-saf-sdk = {version = "^0.2.0", extras = ["core-pim", "instance-management-mapdl"]}

    This will install the supported version of ``ansys-mapdl-core`` to control the MAPDL product instances.
    This example uses PIM as the product instance management system. If you want to use HPS instead, replace the ``core-pim`` extra with ``core-hps``.
    For more information, see :ref:`instance_management_configuration`.


.. _saf-ex-mapdl-product-instance-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To create a product instance manager for MAPDL products and interact with it, work through the following sequence of sections.


.. _saf-ex-mapdl-product-instance-backend:

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

.. key-concept:: Termination event

    Passing ``enable_termination_event=True`` to ``@transaction`` makes SAF automatically raise a
    structured ``MethodState`` event on a stream named after the transaction once it completes or
    fails, so the frontend can track its outcome without parsing log text. The persisted state
    can also be read at any time with ``step.get_long_running_method_state(transaction_name)``.

.. dropdown:: Define the step fields
  :open:

  ``instance_created`` tracks whether a MAPDL instance is currently running.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/mapdl_step.py
    :language: python
    :caption: solution/instance_management/mapdl_step.py
    :lines: 32-35
    :dedent:

.. dropdown:: Define the step model
  :open:

  * The ``launch_mapdl`` long-running transaction is decorated with ``@create_instance`` to create an instance of the MAPDL product manager, ``MapdlManager``, and sets up the finite element model of the 2D solenoid actuator, while the ``shutdown_mapdl`` transaction is decorated with ``@instance`` to reuse and shut down the existing instance.
  * The ``solve_model`` and ``postprocessing`` transactions are decorated with ``@instance`` to indicate they operate on the existing product instance, and call the MAPDL API to solve the model and postprocess the results, respectively.
  * All four long-running transactions pass ``enable_termination_event=True`` so the frontend can track their completion status.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/mapdl_step.py
    :language: python
    :caption: solution/instance_management/mapdl_step.py
    :pyobject: MapdlStep.launch_mapdl

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/mapdl_step.py
    :language: python
    :caption: solution/instance_management/mapdl_step.py
    :pyobject: MapdlStep.solve_model

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/mapdl_step.py
    :language: python
    :caption: solution/instance_management/mapdl_step.py
    :pyobject: MapdlStep.postprocessing

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/mapdl_step.py
    :language: python
    :caption: solution/instance_management/mapdl_step.py
    :pyobject: MapdlStep.shutdown_mapdl


.. _saf-ex-mapdl-product-instance-frontend:

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

.. dropdown:: Compute the initial control states
  :open:

  * ``get_mapdl_page_controls_with_default`` is a helper, shared by every instance management
    page, that returns the default ``disabled``/``loading`` state of each button together with
    the name of the transaction it triggers.
  * ``initialize_mapdl_controls`` starts from those defaults, then looks up the persisted state
    of each transaction with ``step.get_long_running_method_state()`` so the buttons show the
    correct enabled/disabled/loading state even after a page reload.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mapdl_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mapdl_instance_page.py
    :pyobject: initialize_mapdl_controls

.. dropdown:: Define the step layout
  :open:

  The layout builds a controls card, with icon buttons to launch and shut down the instance and
  buttons to solve the model and postprocess the results, and a logs card, using the initial
  control states computed above.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mapdl_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mapdl_instance_page.py
    :pyobject: layout

.. dropdown:: Mount the event listeners
  :open:

  * ``mapdl-output-listener`` subscribes to the free-form progress messages raised on the
    ``mapdl-output-stream`` by the step model.
  * The other four listeners each subscribe to the termination event of one long-running
    transaction: ``launch_mapdl``, ``shutdown_mapdl``, ``solve_model``, and ``postprocessing``.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mapdl_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mapdl_instance_page.py
    :pyobject: mount_event_listeners

.. dropdown:: Trigger a transaction from a button click
  :open:

  * When the :guilabel:`Launch MAPDL` button is clicked, the callback starts the ``launch_mapdl``
    long-running transaction and shows a loading notification.
  * The ``solve_model``, ``postprocessing``, and ``shutdown_mapdl`` callbacks follow the same
    pattern: each one calls the matching transaction on the step and shows a loading
    notification.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mapdl_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mapdl_instance_page.py
    :pyobject: launch_mapdl

.. dropdown:: Keep the button states in sync
  :open:

  * ``sync_controls_on_clicks`` optimistically disables the buttons as soon as one is clicked, so
    the user cannot trigger two transactions at once while the backend catches up.
  * ``sync_controls_on_backend_events`` reconciles the button states once a termination event is
    received, re-enabling the buttons that make sense for the new instance state.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mapdl_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mapdl_instance_page.py
    :pyobject: sync_controls_on_clicks

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mapdl_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mapdl_instance_page.py
    :pyobject: sync_controls_on_backend_events

.. dropdown:: Define the notification system.
  :open:

  * ``sync_notifications_on_backend_events`` reacts to the same termination events and turns each
    ``MethodState`` into a success or error notification through the shared
    ``handle_method_event`` helper.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mapdl_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mapdl_instance_page.py
    :pyobject: sync_notifications_on_backend_events

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/helpers.py
    :language: python
    :caption: ui/helpers.py
    :pyobject: handle_method_event

.. dropdown:: Define the logs system.
  :open:

  * ``store_outputs`` appends every message received on the ``mapdl-output-listener`` stream to a
    ``dcc.Store``, ``display_output`` mirrors that store into the console logs container, and
    ``clear_console_logs`` resets it.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mapdl_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mapdl_instance_page.py
    :pyobject: store_outputs

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mapdl_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mapdl_instance_page.py
    :pyobject: display_output

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mapdl_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mapdl_instance_page.py
    :pyobject: clear_console_logs

  Now that your implementation is complete, continue to the :ref:`saf-ex-mapdl-product-instance-testing` section.


.. _saf-ex-mapdl-product-instance-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-mapdl-product-instance-feature-highlight>` section.
