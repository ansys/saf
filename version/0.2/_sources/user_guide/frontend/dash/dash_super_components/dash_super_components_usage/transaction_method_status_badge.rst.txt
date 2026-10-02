.. _user_guide_frontend_dash_super_components_usage_transaction_method_status_badge:

Transaction Method Status Badge
###############################

``TransactionMethodStatusBadge`` is a Dash All-in-One (AIO) component that provides a compact,
visual status indicator for SAF GLOW transaction methods. It displays the current status of a method
as a badge with color-coded states and optional automatic monitoring. The component supports
both synchronous and asynchronous (long-running) methods.

Key features:

- **Compact visual indicator**: Badge showing method status (RUN-REQUIRED, RUNNING,
  COMPLETED, FAILED)
- **Color-coded states**: Automatic color assignment based on status (gray, blue, lime, red)
- **Automatic monitoring**: Optional polling with configurable intervals
- **Loading animation**: Visual feedback during method execution
- **Flexible control**: Manual or automatic monitoring start/stop
- **Customizable appearance**: Configurable badge, label, and interval properties

.. image:: /_static/dash-media/transaction_method_status_badge/badge_active_running.png
   :alt: Badge active running
   :width: 25%


Usage
=====

.. warning::

    The ``TransactionMethodStatusBadge`` component can only be used as part of a SAF-based solution.
    It requires access to the GLOW API server to monitor transaction method status.

Basic usage
-----------

The following example assumes the existence of an application with a solution definition named
``MySolution``, at least one step model named ``my_step``, and a transaction method named
``my_method``.

Import ``TransactionMethodStatusBadge``:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/super_components_with_saf/src/ansys/solutions/super_components_with_saf/ui/app.py
   :language: python
   :start-after: # [imports-status-badge-start]
   :end-before: # [imports-status-badge-end]

The ``TransactionMethodStatusBadge`` cannot be directly added to the page layout. It must be
initialized via a callback triggered on page load because it needs access to the project URL.
To control its width and alignment, wrap it in a container div with appropriate styles.

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/super_components_with_saf/src/ansys/solutions/super_components_with_saf/ui/app.py
   :language: python
   :start-after: # [layout-status-badge-start]
   :end-before: # [layout-status-badge-end]

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/super_components_with_saf/src/ansys/solutions/super_components_with_saf/ui/app.py
   :language: python
   :start-after: # [add-status-badge-callback-start]
   :end-before: # [add-status-badge-callback-end]


The following output is expected:

.. image:: /_static/dash-media/transaction_method_status_badge/default_configuration.png
   :alt: Default configuration
   :width: 25%


.. _ref_activate_monitoring_example_transaction_method_status_badge:

Activate monitoring
~~~~~~~~~~~~~~~~~~~

To activate monitoring when a transaction method is triggered, set the ``activate_monitoring``
store to ``True``:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/super_components_with_saf/src/ansys/solutions/super_components_with_saf/ui/app.py
   :language: python
   :start-after: # [activate-status-badge-callback-start]
   :end-before: # [activate-status-badge-callback-end]


When the button is clicked, the badge automatically updates its status and the badge appearance
changes accordingly. When the method is running, the expected output is similar to the following:



.. image:: /_static/dash-media/transaction_method_status_badge/default_configuration_running.png
   :alt: Default configuration running
   :width: 25%

.. note::

 Note that this example calls the transaction method and activates monitoring in a single callback.
 This only works for asynchronous ("long-running") transaction methods. For synchronous transaction
 methods, starting the transaction method and activating the badge monitoring must be done in two
 separate callbacks, see :ref:`ref_activate_monitoring_example_transaction_supervisor` for the
 ``TransactionSupervisor`` component.


Advanced usage
--------------

The following example shows a more customized badge with a label, a medium badge size, and a custom
polling interval, which does not automatically stop monitoring when the method completes or fails:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/super_components_with_saf/src/ansys/solutions/super_components_with_saf/ui/app.py
   :language: python
   :start-after: # [add-status-badge-advanced-callback-start]
   :end-before: # [add-status-badge-advanced-callback-end]


The following output is expected:


.. image:: /_static/dash-media/transaction_method_status_badge/custom_configuration.png
   :alt: Custom configuration
   :width: 25%


How it works
------------

1. **Initialization**: The badge is created with GLOW API URL and method details
2. **Status Display**: Shows current method status with appropriate color:

   - **Gray**: RUN-REQUIRED - method hasn't been executed
   - **Blue**: RUNNING - method is executing
   - **Lime**: COMPLETED - method finished successfully
   - **Red**: FAILED - method encountered an error

3. **Monitoring State Visual Feedback**: The badge appearance changes to indicate whether it's
   actively monitoring:

   - **Outline variant** (white background, colored border and text, no spinner): Badge is NOT
     actively monitoring. The displayed status reflects the last known state from the GLOW API.
   - **Filled variant** (colored background, white text, loading spinner): Badge IS actively
     monitoring. The status is being periodically refreshed from the GLOW API.


.. grid:: 2
   :gutter: 4

   .. grid-item::

      .. figure:: /_static/dash-media/transaction_method_status_badge/badge_active_running.png
         :alt: Badge in active monitoring state (filled, spinner shown)
         :width: 75%

         Badge in active monitoring state (filled, spinner shown)


   .. grid-item::

      .. figure:: /_static/dash-media/transaction_method_status_badge/badge_inactive_running.png
         :alt: Badge in inactive monitoring state (outline, no spinner)
         :width: 75%

         Badge in inactive monitoring state (outline, no spinner)

4. **Monitoring Activation**: Set ``activate_monitoring`` to ``True`` to start polling
5. **Automatic Polling**: When active, polls GLOW API at specified interval (default: 5000 ms)
6. **Auto-stop**: If ``auto_mode=True``, monitoring stops when method completes
   or fails
7. **Manual Control**: Set ``auto_mode=False`` to control monitoring manually


Properties
==========

Constructor parameters
----------------------

==============================  ===============================================================================  ====  =========
Parameter                       Description                                                                      Type  Required
==============================  ===============================================================================  ====  =========
url                             The URL of the GLOW API server. Typically obtained from ``project.url``.         str   Yes
step_name                       The name of the GLOW step (StepModel) that contains the method.                  str   Yes
method_name                     The name of the GLOW transaction method whose status is being monitored.         str   Yes
auto_mode                       If ``True``, monitoring automatically stops when method completes or fails,      Bool  No
                                and starts automatically if the method is found running when the component is
                                loaded.
                                If ``False``, monitoring continues until manually stopped.
                                Note: Monitoring still needs to be activated by setting
                                ``activate_monitoring`` to ``True`` when the transaction method is triggered
                                while the component is already loaded.
                                Default: ``True``.
badge_props                     Dictionary of properties for the ``dmc.Badge`` component.                        dict  No
                                Properties ``children``, ``color``, ``variant``, and ``leftSection`` are
                                controlled by the component and get overridden.
                                Default: ``size``: ``"lg"``, ``radius``: ``"xl"``, and ``fullWidth``: ``True``.
label_props                     Dictionary of properties for the label ``html.Div`` component.                   dict  No
                                Include ``"children"`` key to display a label.
                                Default: Label is hidden unless ``children`` is provided.
interval_props                  Dictionary of properties for the ``dcc.Interval`` component.                     dict  No
                                The ``disabled`` property is controlled by the component.
                                Default interval: ``5000`` ms (5 seconds).
aio_id                          The unique identifier for the component. If not provided, a UUID is generated.   str   No
==============================  ===============================================================================  ====  =========

Component IDs
-------------

The component exposes the following IDs for use in callbacks:

- ``TransactionMethodStatusBadge.ids.status_badge(aio_id)``: The status badge component
- ``TransactionMethodStatusBadge.ids.label(aio_id)``: The label div component
- ``TransactionMethodStatusBadge.ids.activate_monitoring(aio_id)``: Store that controls monitoring
  activation (Bool via ``data`` property)


Limitations
===========

- The component **cannot** be initialized directly in the page layout. It must be added via a
  callback triggered on page load to access the project URL.
- Requires a running GLOW API server to function properly.


Comparison with Transaction Supervisor
======================================

``TransactionMethodStatusBadge`` and ``TransactionSupervisor`` serve similar purposes but with
different use cases:

**TransactionMethodStatusBadge**:

- **Compact**: Small badge, minimal screen space
- **Simple**: Shows only status, no timing information
- **Flexible**: Can be embedded anywhere in the layout
- **Best for**: Multiple methods, space-constrained UIs, quick status checks

**TransactionSupervisor**:

- **Comprehensive**: Full card with status, start time, and elapsed time
- **Detailed**: Provides complete monitoring information
- **Larger**: Requires more screen space
- **Best for**: Single important method, detailed monitoring needs


Full example
============

For a complete working example demonstrating automatic and manual monitoring modes, check out the
`showcase example <https://github.com/ansys/saf/blob/main/packages/dash-super-components/examples/showcase_all/src/ansys/solutions/showcase_dash_super_components/ui/pages/transaction_method_status_badge_page.py>`_.

The example shows:

- Component initialization on page load for three independent long-running transactions
- A default badge where monitoring starts and stops automatically alongside the transaction
- A customized badge with a custom label and a 1-second polling interval, also monitoring
  automatically
- A badge with monitoring decoupled from the transaction trigger, controlled independently
  via a ``Live Updates`` switch

For a minimal self-contained runnable example, see the
:ref:`sphx_glr_examples_dash_super_components_examples_saf_based_example_transaction_method_status_badge.py` page in
the Examples gallery.


Source code
===========

For the full API reference of ``TransactionMethodStatusBadge``, see
:class:`~ansys.solutions.dash_super_components.TransactionMethodStatusBadge`.

Check out the `component source code <https://github.com/ansys/saf/blob/main/packages/dash-super-components/src/ansys/solutions/dash_super_components/transaction_method_status_badge.py>`_
to discover the underlying logic. Contributions are welcomed. You can extend the component
functionalities by raising a pull request in the
`dash-super-components <https://github.com/ansys/saf/tree/main/packages/dash-super-components>`_ package.
