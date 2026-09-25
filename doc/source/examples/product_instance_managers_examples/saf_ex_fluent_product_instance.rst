.. _saf-ex-fluent-product-instance:


Fluent Product Instance Manager
###############################

.. topic:: Objective

  Drive an Ansys Fluent session from a solution. Launch the solver in a long-running
  transaction, import a mesh, set up the physics, and run a transient simulation, while the
  solver transcript is streamed live to the user interface.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-fluent-product-instance-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

Ansys Fluent is a powerful simulation tool for computational fluid dynamics (CFD), supporting a wide range of applications including fluid flow, heat transfer, and multiphase phenomena.

This example demonstrates how to create a **product instance manager** for Fluent products using the SAF framework. The product instance manager enables management of the Fluent product instance lifecycle, including starting, stopping, and accessing the product's API.

In this example, you learn how to:

- :material-outlined:`rocket_launch;1.25em;saf-objective-icon` Launch a Fluent session from a
  **long-running transaction** decorated with ``@create_instance``.
- :material-outlined:`hub;1.25em;saf-objective-icon` Reuse the running session in the other
  **transaction methods** through the ``@instance`` decorator.
- :material-outlined:`api;1.25em;saf-objective-icon` Call the **Fluent API** to import a mesh, set
  up the physics, and run a transient simulation.
- :material-outlined:`save;1.25em;saf-objective-icon` Store the solver output files in
  **entity handle fields** through the storage scope.
- :material-outlined:`stream;1.25em;saf-objective-icon` Stream the solver transcript to the UI with
  ``raise_event`` and a ``DashClient`` **event listener**.
- :material-outlined:`notifications;1.25em;saf-objective-icon` Drive **button states and
  notifications** from the event stream, then shut the instance down.


.. _saf-ex-fluent-product-instance-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

.. note::
    This example requires the Fluent 2025 R2 Service Pack 4 (25R2 SP4) product to be installed on your machine.
    To work with a Fluent product instance, be sure to install the ``core-pim`` and ``instance-management-fluent`` extras from the ``ansys-saf-sdk`` package. You can do this by manually editing your ``pyproject.toml``.

    .. code-block:: toml

        ansys-saf-sdk = {version = "^0.3.0", extras = ["core-pim", "instance-management-fluent"]}

    This will install the supported version of ``ansys-fluent-core`` to control the Fluent product instances.
    This example uses PIM as the product instance management system. If you want to use HPS instead, replace the ``core-pim`` extra with ``core-hps``.
    For more information, see :ref:`instance_management_configuration`.


.. _saf-ex-fluent-product-instance-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To create a product instance manager for Fluent products and interact with it, work through the following sequence of sections.


.. _saf-ex-fluent-product-instance-backend:

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
    fails. This is independent from the free-form messages sent with ``raise_event`` on the
    ``fluent-output-stream``, and lets the frontend react to success or failure without parsing
    log text. The persisted state can also be read at any time with
    ``step.get_long_running_method_state(transaction_name)``.

.. dropdown:: Define the step fields
  :open:

  ``instance_created`` tracks whether a Fluent instance is currently running, and the other
  fields store the solver output files produced by the transactions below.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/fluent_step.py
    :language: python
    :caption: solution/instance_management/fluent_step.py
    :lines: 30-35
    :dedent:

.. dropdown:: Define the step model
  :open:

  * The ``launch_fluent`` long-running transaction is decorated with ``@create_instance`` to create an instance of the Fluent product manager, ``Fluent3DDPSolverManager``, while the ``shutdown_fluent`` transaction is decorated with ``@instance`` to reuse and shut down the existing instance.
  * The ``import_mesh`` and ``run_simulation`` transactions are decorated with ``@instance`` to indicate they operate on the existing product instance, and call the Fluent API to import a mesh and to run a transient simulation, respectively.
  * All four long-running transactions pass ``enable_termination_event=True`` so the frontend can track their completion status.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/fluent_step.py
    :language: python
    :caption: solution/instance_management/fluent_step.py
    :pyobject: FluentStep.launch_fluent

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/fluent_step.py
    :language: python
    :caption: solution/instance_management/fluent_step.py
    :pyobject: FluentStep.import_mesh

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/fluent_step.py
    :language: python
    :caption: solution/instance_management/fluent_step.py
    :pyobject: FluentStep.run_simulation

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/fluent_step.py
    :language: python
    :caption: solution/instance_management/fluent_step.py
    :pyobject: FluentStep.shutdown_fluent


.. _saf-ex-fluent-product-instance-frontend:

:material-outlined:`web;1.25em;sd-text-primary` Frontend
----------------------------------------------------------

Expose the solution definition in the UI.

.. key-concept:: Callback

    A **callback** is a Dash-decorated function that fires in response to a UI event. In a
    SAF solution, callbacks reach the backend through ``project.steps.<step_name>``, read or
    write fields, and invoke transaction methods — no manual HTTP calls needed.

.. key-concept:: Event listener

    ``DashClient.create_event_listener()`` subscribes a page to a backend stream. Each message
    fires a callback, which is how the solver transcript, the termination events, and the button
    states stay in sync with a long-running transaction.

.. dropdown:: Compute the initial control states
  :open:

  * ``get_fluent_page_controls_with_default`` is a helper, shared by every instance management
    page, that returns the default ``disabled``/``loading`` state of each button together with
    the name of the transaction it triggers.
  * ``initialize_fluent_controls`` starts from those defaults, then looks up the persisted state
    of each transaction with ``step.get_long_running_method_state()`` so the buttons show the
    correct enabled/disabled/loading state even after a page reload.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/fluent_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/fluent_instance_page.py
    :pyobject: initialize_fluent_controls

.. dropdown:: Define the step layout
  :open:

  The layout builds a controls card, with icon buttons to launch and shut down the instance and
  buttons to import a mesh and run the simulation, and a logs card, using the initial control
  states computed above.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/fluent_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/fluent_instance_page.py
    :pyobject: layout

.. dropdown:: Mount the event listeners
  :open:

  * ``fluent-output-listener`` subscribes to the free-form progress messages raised on the
    ``fluent-output-stream`` by the step model.
  * The other four listeners each subscribe to the termination event of one long-running
    transaction: ``launch_fluent``, ``shutdown_fluent``, ``import_mesh``, and ``run_simulation``.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/fluent_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/fluent_instance_page.py
    :pyobject: mount_event_listeners

.. dropdown:: Trigger a transaction from a button click
  :open:

  * When the :guilabel:`Launch Fluent` button is clicked, the callback starts the
    ``launch_fluent`` long-running transaction and shows a loading notification.
  * The ``import_mesh``, ``run_simulation``, and ``shutdown_fluent`` callbacks follow the same
    pattern: each one calls the matching transaction on the step and shows a loading
    notification.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/fluent_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/fluent_instance_page.py
    :pyobject: launch_fluent

.. dropdown:: Keep the button states in sync
  :open:

  * ``sync_controls_on_clicks`` optimistically disables the buttons as soon as one is clicked, so
    the user cannot trigger two transactions at once while the backend catches up.
  * ``sync_controls_on_backend_events`` reconciles the button states once a termination event is
    received, re-enabling the buttons that make sense for the new instance state.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/fluent_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/fluent_instance_page.py
    :pyobject: sync_controls_on_clicks

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/fluent_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/fluent_instance_page.py
    :pyobject: sync_controls_on_backend_events

.. dropdown:: Define the notification system.
  :open:

  * ``sync_notifications_on_backend_events`` reacts to the same termination events and turns each
    ``MethodState`` into a success or error notification through the shared
    ``handle_method_event`` helper.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/fluent_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/fluent_instance_page.py
    :pyobject: sync_notifications_on_backend_events

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/helpers.py
    :language: python
    :caption: ui/helpers.py
    :pyobject: handle_method_event

.. dropdown:: Define the logs system.
  :open:

  * ``store_outputs`` appends every message received on the ``fluent-output-listener`` stream to
    a ``dcc.Store``, ``display_output`` mirrors that store into the console logs container, and
    ``clear_console_logs`` resets it.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/fluent_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/fluent_instance_page.py
    :pyobject: store_outputs

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/fluent_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/fluent_instance_page.py
    :pyobject: display_output

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/fluent_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/fluent_instance_page.py
    :pyobject: clear_console_logs

  Now that your implementation is complete, continue to the :ref:`saf-ex-fluent-product-instance-testing` section.


.. _saf-ex-fluent-product-instance-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-fluent-product-instance-feature-highlight>` section.
