.. _saf-ex-aedt-product-instance:


AEDT Product Instance Manager
#############################

.. topic:: Objective

  Drive an Ansys Electronics Desktop (AEDT) product, such as Maxwell 2D, from a solution.
  Start the product instance in a long-running transaction, call the AEDT API to add a
  rectangle to the design and analyze it, then shut the instance down.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-aedt-product-instance-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

Ansys Electronics Desktop is a unified simulation platform that integrates multiple Ansys solvers for electromagnetic, thermal, and circuit analysis, enabling seamless collaboration and coupled physics simulations.

This example shows how to create a **product instance manager** for AEDT products, such as Maxwell 2D, using the SAF framework. The product instance manager allows you to manage the lifecycle of an AEDT product instance, including starting, stopping, and accessing the product's API.

In this example, you learn how to:

- :material-outlined:`rocket_launch;1.25em;saf-objective-icon` Start a product instance from a
  **long-running transaction** decorated with ``@create_instance``.
- :material-outlined:`hub;1.25em;saf-objective-icon` Reuse the running instance in the other
  **transaction methods** through the ``@instance`` decorator.
- :material-outlined:`api;1.25em;saf-objective-icon` Call the **AEDT API** to add a rectangle to
  the design and to analyze it.
- :material-outlined:`power_settings_new;1.25em;saf-objective-icon` **Shut down** the product
  instance from a dedicated transaction method.
- :material-outlined:`bolt;1.25em;saf-objective-icon` Wire one **callback** per button so the UI
  triggers a transaction and reports its outcome.


.. _saf-ex-aedt-product-instance-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

.. note::
    This example requires the AEDT 2025 R1 (25R1) product to be installed on your machine.
    To work with an AEDT product instance, be sure to install the ``core-pim`` and ``instance-management-aedt`` extras from the ``ansys-saf-sdk`` package. You can do this by manually editing your ``pyproject.toml``.

    .. code-block:: toml

        ansys-saf-sdk = {version = "^0.3.0", extras = ["core-pim", "instance-management-aedt"]}

    This will install the supported version of PyAEDT to control the AEDT product instances.
    This example uses PIM as the product instance management system. If you want to use HPS instead, replace the ``core-pim`` extra with ``core-hps``.
    For more information, see :ref:`instance_management_configuration`.


.. _saf-ex-aedt-product-instance-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To create a product instance manager for AEDT products and interact with it, work through the following sequence of sections.


.. _saf-ex-aedt-product-instance-backend:

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

.. key-concept:: Event stream and termination event

    ``self.transaction.raise_event()`` publishes a free-form progress message on a named
    **stream**. Passing ``enable_termination_event=True`` to ``@transaction`` additionally makes
    SAF raise a structured ``MethodState`` event on a stream named after the transaction once it
    completes or fails, so the frontend can track its outcome without parsing log text. The
    persisted state can also be read at any time with
    ``step.get_long_running_method_state(transaction_name)``.

.. dropdown:: Define the step fields
  :open:

  ``instance_created`` tracks whether an AEDT instance is currently running.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/aedt_step.py
    :language: python
    :caption: solution/instance_management/aedt_step.py
    :lines: 29-32
    :dedent:

.. dropdown:: Define the step model
  :open:

  * The ``launch_aedt`` long-running transaction is decorated with ``@create_instance`` to create an instance of the AEDT product manager, ``Maxwell2DManager``, while the ``shutdown_aedt`` transaction is decorated with ``@instance`` to reuse and shut down the existing instance.
  * The ``add_rectangle`` and ``analyze_design`` transactions are decorated with ``@instance`` to indicate they operate on the existing product instance, and call the AEDT API to add a rectangle to the design and to analyze it, respectively.
  * All four long-running transactions pass ``enable_termination_event=True`` so the frontend can track their completion status.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/aedt_step.py
    :language: python
    :caption: solution/instance_management/aedt_step.py
    :pyobject: Maxwell2DSetupVerificationStep.launch_aedt

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/aedt_step.py
    :language: python
    :caption: solution/instance_management/aedt_step.py
    :pyobject: Maxwell2DSetupVerificationStep.add_rectangle

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/aedt_step.py
    :language: python
    :caption: solution/instance_management/aedt_step.py
    :pyobject: Maxwell2DSetupVerificationStep.analyze_design

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/aedt_step.py
    :language: python
    :caption: solution/instance_management/aedt_step.py
    :pyobject: Maxwell2DSetupVerificationStep.shutdown_aedt


.. _saf-ex-aedt-product-instance-frontend:

:material-outlined:`web;1.25em;sd-text-primary` Frontend
----------------------------------------------------------

Expose the solution definition in the UI.

.. key-concept:: Callback

    A **callback** is a Dash-decorated function that fires in response to a UI event. In a
    SAF solution, callbacks reach the backend through ``project.steps.<step_name>``, read or
    write fields, and invoke transaction methods — no manual HTTP calls needed.

.. key-concept:: Event listener

    ``DashClient.create_event_listener()`` subscribes a page to a backend stream. Each message
    fires a callback, which is how the solver output, the termination events, and the button
    states stay in sync with a long-running transaction.

.. dropdown:: Compute the initial control states
  :open:

  * ``get_aedt_page_controls_with_default`` is a helper, shared by every instance management
    page, that returns the default ``disabled``/``loading`` state of each button together with
    the name of the transaction it triggers.
  * ``initialize_aedt_controls`` starts from those defaults, then looks up the persisted state of
    each transaction with ``step.get_long_running_method_state()`` so the buttons show the
    correct enabled/disabled/loading state even after a page reload.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/aedt_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/aedt_instance_page.py
    :pyobject: initialize_aedt_controls

.. dropdown:: Define the step layout
  :open:

  The layout builds a controls card, with icon buttons to launch and shut down the instance and
  buttons to add a rectangle and analyze the design, and a logs card, using the initial control
  states computed above.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/aedt_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/aedt_instance_page.py
    :pyobject: layout

.. dropdown:: Mount the event listeners
  :open:

  * ``aedt-output-listener`` subscribes to the free-form progress messages raised on the
    ``aedt-output-stream`` by the step model.
  * The other four listeners each subscribe to the termination event of one long-running
    transaction: ``launch_aedt``, ``shutdown_aedt``, ``add_rectangle``, and ``analyze_design``.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/aedt_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/aedt_instance_page.py
    :pyobject: mount_event_listeners

.. dropdown:: Trigger a transaction from a button click
  :open:

  * When the :guilabel:`Launch AEDT` button is clicked, the callback starts the ``launch_aedt``
    long-running transaction and shows a loading notification.
  * The ``add_rectangle``, ``analyze_design``, and ``shutdown_aedt`` callbacks follow the same
    pattern: each one calls the matching transaction on the step and shows a loading
    notification.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/aedt_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/aedt_instance_page.py
    :pyobject: launch_aedt

.. dropdown:: Keep the button states in sync
  :open:

  * ``sync_controls_on_clicks`` optimistically disables the buttons as soon as one is clicked, so
    the user cannot trigger two transactions at once while the backend catches up.
  * ``sync_controls_on_backend_events`` reconciles the button states once a termination event is
    received, re-enabling the buttons that make sense for the new instance state.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/aedt_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/aedt_instance_page.py
    :pyobject: sync_controls_on_clicks

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/aedt_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/aedt_instance_page.py
    :pyobject: sync_controls_on_backend_events

.. dropdown:: Define the notification system.
  :open:

  * ``sync_notifications_on_backend_events`` reacts to the same termination events and turns each
    ``MethodState`` into a success or error notification through the shared
    ``handle_method_event`` helper.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/aedt_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/aedt_instance_page.py
    :pyobject: sync_notifications_on_backend_events

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/helpers.py
    :language: python
    :caption: ui/helpers.py
    :pyobject: handle_method_event

.. dropdown:: Define the logs system.
  :open:

  * ``store_outputs`` appends every message received on the ``aedt-output-listener`` stream to a
    ``dcc.Store``, ``display_output`` mirrors that store into the console logs container, and
    ``clear_console_logs`` resets it.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/aedt_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/aedt_instance_page.py
    :pyobject: store_outputs

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/aedt_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/aedt_instance_page.py
    :pyobject: display_output

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/aedt_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/aedt_instance_page.py
    :pyobject: clear_console_logs

  Now that your implementation is complete, continue to the :ref:`saf-ex-aedt-product-instance-testing` section.


.. _saf-ex-aedt-product-instance-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-aedt-product-instance-feature-highlight>` section.
