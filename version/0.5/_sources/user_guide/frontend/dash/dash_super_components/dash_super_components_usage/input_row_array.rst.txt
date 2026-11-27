.. _user_guide_frontend_dash_super_components_usage_input_row_array:

Input Row Array
###############


``InputRowArray`` is a Dash All-in-One (AIO) component that creates a set of input fields arranged
in a row. Optionally, a "multiple rows mode" can be enabled, which allows users to capture multiple
sets of input values within a single form. When multiple rows are enabled, buttons are displayed for
adding and deleting rows.

Key features:

- **Multiple input types**: Supports ``TextInput``, ``NumberInput``, and ``Select`` fields
- **Dynamic row management**: Optional add and delete buttons to manage multiple rows at runtime
- **Pattern-matching callbacks**: Uses Dash pattern-matching IDs for easy data retrieval
- **Flexible configuration**: Each field is independently configurable via a properties dictionary

.. image:: /_static/dash-media/input_row_array/input_row_array_with_buttons.png
   :alt: Input Row Array with add and delete buttons
   :width: 85%


Usage
=====

Basic usage
-----------

Import ``InputRowArray``:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_row_array.py
   :language: python
   :start-after: # [imports-start]
   :end-before: # [imports-end]

Define the items and add ``InputRowArray`` to the page layout:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_row_array.py
   :language: python
   :start-after: # [basic-layout-start]
   :end-before: # [basic-layout-end]

The following output is expected:

.. image:: /_static/dash-media/input_row_array/default_configuration.png
   :alt: Input Row Array default configuration
   :width: 70%


Advanced usage
--------------

Enable multiple rows so that users can add rows at runtime. When only one row is
left, the delete button is disabled. You can also use the ``full_width`` parameter
to control whether the row stretches to the width of its parent container or keeps its base width:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_row_array.py
   :language: python
   :start-after: # [advanced-layout-start]
   :end-before: # [advanced-layout-end]

The following output is expected:


.. image:: /_static/dash-media/input_row_array/custom_configuration.png
   :alt: Input Row Array custom configuration
   :width: 50%


Retrieve input values
---------------------

Use the ``ids.input(aio_id, item_id, row_index)`` ID to retrieve input values in a callback. See the
:ref:`input_row_array_component_ids` section for more details on the component IDs.

With the ``ALL`` pattern-matching wildcard, you can retrieve values from all rows or all fields
simultaneously. For example, to retrieve values from all fields in all rows when a button is
clicked, use the following callback:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_row_array.py
   :language: python
   :start-after: # [all-values-callback-start]
   :end-before: # [all-values-callback-end]

The resulting output for a sample input might look like this:

.. code-block:: none

    ['Row 1 value', 42, 'Row 2 value', 99, 'Row 3 value', 100]

To retrieve values from a specific row, use the ``row_index`` key in the ID:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_row_array.py
   :language: python
   :start-after: # [first-row-values-callback-start]
   :end-before: # [first-row-values-callback-end]

The resulting output for a sample input might look like this:

.. code-block:: none

    ['Row 1 value', 42]

To retrieve values from a specific field across all rows, use the ``item_id`` key in the ID:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_row_array.py
   :language: python
   :start-after: # [collect-input-1-values-callback-start]
   :end-before: # [collect-input-1-values-callback-end]

The resulting output for a sample input might look like this:

.. code-block:: none

    ['Row 1 value', 'Row 2 value', 'Row 3 value']

How it works
------------

1. **Initialization**: The component is initialized with an ``items`` list that
   describes each field in a row, including its type and properties.
2. **Row rendering**: The first row is rendered immediately. When ``enable_multiple_rows`` is
   ``True``, add and delete buttons are displayed at the top of the component.
3. **Adding rows**: Clicking the add button appends a new row using the same
   ``items`` list. Each field in the new row receives a unique ``row_index`` based on
   the row number.
4. **Deleting rows**: Clicking the delete button removes the last row. If only one row
   remains, it is cleared but the row container is kept.
5. **Retrieving values**: Use ``InputRowArray.ids.input(aio_id, item_id, row_index)`` in a ``State``
   or ``Input`` to retrieve input values. The ID's ``item_id`` key corresponds to the
   field's ``id`` from the ``items`` list, and the ``row_index`` key indicates the row.


Properties
==========

Items definition
----------------

.. _input_row_array_item_definition_properties:

.. vale Google.Quotes = NO
.. vale Google.Spacing = NO

==========  ============================================================  ======  ========
Key         Description                                                   Type    Required
==========  ============================================================  ======  ========
id          A unique identifier of the field across all rows.             string  Yes
type        The input type: "TextInput", "NumberInput", or "Select".      string  Yes
properties  The properties of the field.                                  dict    Yes
==========  ============================================================  ======  ========

.. vale Google.Quotes = YES
.. vale Google.Spacing = YES

Constructor parameters
----------------------

.. vale Google.Spacing = NO

====================  ======================================================  =======  ========
Name                  Description                                             Type     Required
====================  ======================================================  =======  ========
items                 A list of field definitions. See `Items definition`_.   list     Yes
enable_multiple_rows  When ``True``, add and delete row buttons appear.       bool     No
                      Default: ``False``.
full_width            When ``True``, the row container expands to the         bool     No
                      available parent width so the input fields can spread
                      across the row. Default: ``False``.
aio_id                A unique identifier for the component. If not           string   No
                      provided, a UUID is generated.
====================  ======================================================  =======  ========

.. vale Google.Spacing = YES

.. _input_row_array_component_ids:

Component IDs
-------------

The component exposes the following IDs for use in callbacks:

- ``InputRowArray.ids.rows(aio_id)``: The container holding all rendered rows.
  Use its ``children`` property in a ``State`` to retrieve row data.
- ``InputRowArray.ids.add_button(aio_id)``: The button that adds a new row.
  Only present when ``enable_multiple_rows=True``.
- ``InputRowArray.ids.delete_button(aio_id)``: The button that removes the last row.
  Only present when ``enable_multiple_rows=True``.
- ``InputRowArray.ids.input(aio_id, item_id, row_index)``: An individual input field, where
  ``item_id`` is the item id (``item["id"]``) and ``row_index`` is the zero-based row number. For
  single-row mode, the row index can be omitted and defaults to ``0``:
  ``InputRowArray.ids.input(aio_id, item_id)``.


Full example
============

Check out this `example <https://github.com/ansys/saf/blob/main/packages/dash-super-components/examples/showcase_all/src/ansys/solutions/showcase_dash_super_components/ui/pages/input_row_array_page.py>`_
to learn how to use ``InputRowArray``.

The example demonstrates:

- A minimal single-row array with ``TextInput``, ``NumberInput``, and ``Select`` inputs
  configured with only the required properties
- A single-row array with detailed item configuration: description hints, unit suffixes,
  decimal scale, step size, and a searchable and clearable select
- A dynamic multi-row array with row addition and deletion, and callbacks reading all values
  for a specific input across all rows and all inputs from a specific row using
  ``InputRowArray.ids.input()`` with ``ALL`` pattern-matching wildcards


For a minimal self-contained runnable example, see the
:ref:`sphx_glr_examples_dash_super_components_examples_general_example_input_row_array.py` page in the Examples gallery.


Source code
===========

For the full API reference of ``InputRowArray``, see
:class:`~ansys.solutions.dash_super_components.InputRowArray`.

Check out the `component source code <https://github.com/ansys/saf/blob/main/packages/dash-super-components/src/ansys/solutions/dash_super_components/input_row_array.py>`_
to discover the underlying logic. Contributions are welcomed. You can extend the component
functionalities by raising a pull request in the
`dash-super-components <https://github.com/ansys/saf/tree/main/packages/dash-super-components>`_ package.
