.. _saf-ex-mechanical-product-instance:


Mechanical Product Instance Manager
###################################

.. topic:: Objective

  Drive an Ansys Mechanical product from a solution. Start the product instance in a
  long-running transaction, upload a geometry file, run a custom Mechanical script that solves
  a static structural analysis, download the ``solve.out`` file, then shut the instance down.

  Source code for this example is in the `example solution <https://github.com/ansys/saf/tree/main/examples>`_.


.. _saf-ex-mechanical-product-instance-feature-highlight:

:material-outlined:`emoji_objects;1.25em;sd-text-primary` Feature highlight
============================================================================

Ansys Mechanical is a powerful simulation tool for structural analysis, supporting a wide range of applications including stress analysis, vibration, thermal, and fatigue simulations.

This example shows how to create a **product instance manager** for Mechanical products using SAF. The product instance manager enables management of the Mechanical product instance lifecycle, including starting, stopping, and accessing the product's API.

In this example, you learn how to:

- :material-outlined:`rocket_launch;1.25em;saf-objective-icon` Start a product instance from a
  **long-running transaction** decorated with ``@create_instance``.
- :material-outlined:`hub;1.25em;saf-objective-icon` Reuse the running instance in the other
  **transaction methods** through the ``@instance`` decorator.
- :material-outlined:`api;1.25em;saf-objective-icon` Call the **Mechanical API** to upload a
  geometry file and run a custom Python script that solves the model.
- :material-outlined:`cloud_upload;1.25em;saf-objective-icon` Move files between the solution
  and the product with the ``storage_scope`` and an ``EntityHandle`` field.
- :material-outlined:`stream;1.25em;saf-objective-icon` Publish progress on named **event
  streams** with ``transaction.raise_event``.
- :material-outlined:`bolt;1.25em;saf-objective-icon` Wire one **callback** per button and use
  **event listeners** to refresh the console logs and the notifications.


.. _saf-ex-mechanical-product-instance-prerequisites:

:material-outlined:`task;1.25em;sd-text-primary` Prerequisites
=========================================================================

.. note::
    This example requires the Mechanical 2025 R2 Service Pack 4 (25R2 SP4) product to be installed on your machine.
    To work with a Mechanical product instance, be sure to install the ``core-pim`` and ``instance-management-mechanical`` extras from the ``ansys-saf-sdk`` package. You can do this by manually editing your ``pyproject.toml``.

    .. code-block:: toml

        ansys-saf-sdk = {version = "^0.3.0", extras = ["core-pim", "instance-management-mechanical"]}

    This will install the supported version of ``ansys-mechanical-core`` to control the Mechanical product instances.
    This example uses PIM as the product instance management system. If you want to use HPS instead, replace the ``core-pim`` extra with ``core-hps``.
    For more information, see :ref:`instance_management_configuration`.

The geometry file required for the example script, ``example_01_geometry.agdb``, is bundled with the solution as a method asset and retrieved with ``self.transaction.get_asset_entity_handle("example_01_geometry.agdb")`` in ``upload_example_file_to_mechanical``, so no manual setup is required.


.. _saf-ex-mechanical-product-instance-solution:

:octicon:`code-square;1em;sd-text-primary` Coding
======================================================

To create a product instance manager for Mechanical products and interact with it, work through the following sequence of sections.


.. _saf-ex-mechanical-product-instance-backend:

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

  ``instance_created`` tracks whether a Mechanical instance is currently running, and
  ``output_handle`` stores the downloaded ``solve.out`` file.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/mechanical_step.py
    :language: python
    :caption: solution/instance_management/mechanical_step.py
    :lines: 33-35
    :dedent:

.. dropdown:: Define the step model
  :open:

  * The ``launch_mechanical`` long-running transaction is decorated with ``@create_instance`` to create an instance of the Mechanical product manager, ``MechanicalManager``, while the ``shutdown_mechanical`` transaction is decorated with ``@instance`` to reuse and shut down the existing instance.
  * ``upload_example_file_to_mechanical`` and ``initialize_variable_workflow`` are decorated with ``@instance`` and upload the example geometry to the instance, then set up the ``part_file_path`` variable used by the script.
  * ``run_script`` is decorated with ``@instance`` and calls the Mechanical API to run a custom Python script that solves a static structural analysis.
  * ``download_output_file`` is decorated with ``@instance`` and downloads the ``solve.out`` file produced by the solve, storing it in an ``EntityHandle`` field.
  * The ``launch_mechanical``, ``run_script``, ``download_output_file``, and ``shutdown_mechanical`` transactions pass ``enable_termination_event=True`` so the frontend can track their completion status.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/mechanical_step.py
    :language: python
    :caption: solution/instance_management/mechanical_step.py
    :pyobject: MechanicalStep.launch_mechanical

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/mechanical_step.py
    :language: python
    :caption: solution/instance_management/mechanical_step.py
    :pyobject: MechanicalStep.upload_example_file_to_mechanical

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/mechanical_step.py
    :language: python
    :caption: solution/instance_management/mechanical_step.py
    :pyobject: MechanicalStep.initialize_variable_workflow

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/mechanical_step.py
    :language: python
    :caption: solution/instance_management/mechanical_step.py
    :pyobject: MechanicalStep.run_script

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/mechanical_step.py
    :language: python
    :caption: solution/instance_management/mechanical_step.py
    :pyobject: MechanicalStep.download_output_file

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/solution/instance_management/mechanical_step.py
    :language: python
    :caption: solution/instance_management/mechanical_step.py
    :pyobject: MechanicalStep.shutdown_mechanical


.. _saf-ex-mechanical-product-instance-frontend:

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

  * ``get_mechanical_page_controls_with_default`` is a helper, shared by every instance
    management page, that returns the default ``disabled``/``loading`` state of each button
    together with the name of the transaction it triggers.
  * ``initialize_mechanical_controls`` starts from those defaults, then looks up the persisted
    state of each transaction with ``step.get_long_running_method_state()`` so the buttons show
    the correct enabled/disabled/loading state even after a page reload.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mechanical_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mechanical_instance_page.py
    :pyobject: initialize_mechanical_controls

.. dropdown:: Define the step layout
  :open:

  The layout builds a controls card, with icon buttons to launch and shut down the instance and
  buttons to run the script and download the output file, and a logs card, using the initial
  control states computed above.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mechanical_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mechanical_instance_page.py
    :pyobject: layout

.. dropdown:: Mount the event listeners
  :open:

  * ``mechanical-output-listener`` subscribes to the free-form progress messages raised on the
    ``mechanical-output-stream`` by the step model.
  * The other four listeners each subscribe to the termination event of one long-running
    transaction: ``launch_mechanical``, ``shutdown_mechanical``, ``run_script``, and
    ``download_output_file``.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mechanical_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mechanical_instance_page.py
    :pyobject: mount_event_listeners

.. dropdown:: Trigger a transaction from a button click
  :open:

  * When the :guilabel:`Launch Mechanical` button is clicked, the callback starts the
    ``launch_mechanical`` long-running transaction and shows a loading notification.
  * When the :guilabel:`Run Script` button is clicked, the ``_run_script`` helper chains
    ``upload_example_file_to_mechanical``, ``initialize_variable_workflow``, and ``run_script`` on
    the step, so the geometry is uploaded and the workflow variables are set before the
    long-running script transaction starts.
  * The ``download_output_file`` and ``shutdown_mechanical`` callbacks follow the simpler
    pattern: each one calls the matching transaction on the step and shows a loading
    notification.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mechanical_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mechanical_instance_page.py
    :pyobject: _run_script

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mechanical_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mechanical_instance_page.py
    :pyobject: run_script

.. dropdown:: Keep the button states in sync
  :open:

  * ``sync_controls_on_clicks`` optimistically disables the buttons as soon as one is clicked, so
    the user cannot trigger two transactions at once while the backend catches up.
  * ``sync_controls_on_backend_events`` reconciles the button states once a termination event is
    received, re-enabling the buttons that make sense for the new instance state.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mechanical_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mechanical_instance_page.py
    :pyobject: sync_controls_on_clicks

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mechanical_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mechanical_instance_page.py
    :pyobject: sync_controls_on_backend_events

.. dropdown:: Define the notification system.
  :open:

  * ``sync_notifications_on_backend_events`` reacts to the same termination events and turns each
    ``MethodState`` into a success or error notification through the shared
    ``handle_method_event`` helper.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mechanical_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mechanical_instance_page.py
    :pyobject: sync_notifications_on_backend_events

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/helpers.py
    :language: python
    :caption: ui/helpers.py
    :pyobject: handle_method_event

.. dropdown:: Define the logs system.
  :open:

  * ``store_outputs`` appends every message received on the ``mechanical-output-listener``
    stream to a ``dcc.Store``, ``display_output`` mirrors that store into the console logs
    container, and ``clear_console_logs`` resets it.

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mechanical_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mechanical_instance_page.py
    :pyobject: store_outputs

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mechanical_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mechanical_instance_page.py
    :pyobject: display_output

  .. literalinclude:: ../../../../examples/src/saf/solutions/examples/ui/pages/instance_management/mechanical_instance_page.py
    :language: python
    :caption: ui/pages/instance_management/mechanical_instance_page.py
    :pyobject: clear_console_logs

  Now that your implementation is complete, continue to the :ref:`saf-ex-mechanical-product-instance-testing` section.


.. _saf-ex-mechanical-product-instance-testing:

:octicon:`verified;1em;sd-text-primary`  Testing
==================================================

Finally, test your implementation to confirm it works as expected.

Run the solution and compare your results with the results shown in the
:ref:`Feature highlight <saf-ex-mechanical-product-instance-feature-highlight>` section.
