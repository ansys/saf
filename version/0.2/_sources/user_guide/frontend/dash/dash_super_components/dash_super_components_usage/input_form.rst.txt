.. _user_guide_frontend_dash_super_components_usage_input_form:

Input Form
##########

``InputForm`` is a Dash All-in-One (AIO) component that helps developers quickly design input
forms for capturing user selections. An input form is composed of one or several rows, where each
row corresponds to a parameter. Each row can contain one or multiple input fields (for example,
to capture a set of related values for a single parameter).

Key features:

- **Multiple input types**: Supports ``NumberInput``, ``TextInput``, ``PasswordInput``,
  ``Checkbox``, ``Select``, ``MultiSelect``, ``Slider``, and ``Switch`` fields.
- **Flexible column layout**: Configurable columns (``label``, ``fields``, ``unit``, ``help``,
  ``description``) with adjustable widths.
- **Pattern-matching callbacks**: Uses Dash pattern-matching IDs for easy data retrieval.
- **Help modals**: Optional help column that opens a modal with custom content.
- **Hidden fields**: Fields can be hidden on initialization and toggled dynamically using
  callbacks.

.. image:: /_static/dash-media/input_form/example_output.png
   :alt: Input Form example output
   :width: 80%


Usage
=====

Basic usage
-----------

Import ``InputForm``:

.. code-block:: python

    from ansys.solutions.dash_super_components import InputForm

Add a simple ``InputForm`` with a text input field and a number input field with labels to your page
layout:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_form.py
   :language: python
   :start-after: # [basic-layout-start]
   :end-before: # [basic-layout-end]

The following output is expected:

.. image:: /_static/dash-media/input_form/default_configuration.png
   :alt: Input Form default configuration
   :width: 80%


Advanced usage
--------------

The following example shows a complete form that exercises the constructor parameters
``columns``, ``column_widths``, ``column_names``, ``title``, ``title_props``,
``card_props``, and the row-level ``"id"`` key (which sets the ``row_index`` used in
component IDs). It also demonstrates how a field can be hidden on initialization with
``"hidden": True``:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_form.py
   :language: python
   :start-after: # [advanced-layout-start]
   :end-before: # [advanced-layout-end]

The following output is expected:

.. image:: /_static/dash-media/input_form/advanced_configuration.png
   :alt: Input Form advanced configuration
   :width: 80%



Column layout
-------------

The columns of the form and their order are configured using the ``columns`` parameter. Pass a
list containing any subset of ``"label"``, ``"fields"``, ``"unit"``, ``"help"``, and
``"description"`` in the expected display order. Column widths can be controlled through the
``column_widths`` parameter as a dictionary mapping column names to integer widths. The overall
form width is then distributed proportionally based on the specified widths. For example:

.. code-block:: python

    InputForm(
        items=[...],
        aio_id="my-form",
        columns=["label", "fields", "unit"],
        column_widths={"label": 3, "fields": 4, "unit": 1},
    )

If ``columns`` is not provided, the default is
``["label", "fields", "unit", "description", "help"]``. If ``column_widths`` is not provided,
built-in defaults are used. If a particular column is not included in the ``column_widths``
dictionary, its width also defaults to the built-in value.


Retrieving field values in callbacks
-------------------------------------

Use ``InputForm.ids.field(aio_id, field_type, field_id, row_index)`` to target individual
fields in Dash callbacks. All four arguments are required (or can be pattern-matching wildcards).

The ``row_index`` is either the value of the ``"id"`` key on the row definition, or the
zero-based integer position of the row in the ``items`` list if no ``"id"`` was set.

Retrieve a specific field
~~~~~~~~~~~~~~~~~~~~~~~~~

The following example targets specific fields by their exact ``aio_id``, ``field_type``,
``field_id``, and ``row_index``:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_form.py
   :language: python
   :start-after: # [specific-field-callback-start]
   :end-before: # [specific-field-callback-end]


The resulting output for a sample input might look like this:

.. code-block:: none

    [7 | 10 |3 | True]


Retrieve all fields of a specific type using pattern matching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the ``ALL`` wildcard from ``dash_extensions.enrich`` to collect all fields of a particular
type across the entire form in a single callback:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_form.py
   :language: python
   :start-after: # [number-inputs-callback-start]
   :end-before: # [number-inputs-callback-end]

This retrieves all ``NumberInput`` fields from the form with ``aio_id="full-form"`` as a
flat list in row order.

The resulting output for a sample input might look like this:

.. code-block:: none

   Number Inputs: [2, 53]

.. note::

    Using ``ALL`` for ``field_type`` mixes fields that use ``"value"`` (``NumberInput``,
    ``TextInput``, ``Select``, ``MultiSelect``, ``Slider``) and fields that use ``"checked"``
    (``Checkbox``, ``Switch``) in the same callback. If your form contains both types, use separate
    callbacks targeting different field types.

.. note::

    Always import ``ALL``, ``MATCH``, and other pattern-matching wildcards from
    ``dash_extensions.enrich``, not from ``dash``. Because the Super Components require
    ``DashProxy``, the enriched callback pipeline from ``dash_extensions.enrich`` must be used
    throughout your application.


Updating row-level subcomponents from callbacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Row-level subcomponents—``label``, ``unit``, and ``description``—are identified by
``aio_id`` and ``row_index`` and can also be updated from callbacks. Using ``MATCH`` for the
``row_index`` allows you to target different subcomponents (row-level subcomponents and fields)
within the same callback, as shown in the following example.
This example colors the label and unit of a row depending on whether the ``NumberInput`` value
falls close to the edges of the valid range (note that "c" is the property for text color in Dash
Mantine Components):

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_form.py
   :language: python
   :start-after: # [color-callback-start]
   :end-before: # [color-callback-end]

The resulting output for a sample input might look like this:

.. image:: /_static/dash-media/input_form/advanced_configuration_colored.png
   :alt: Input Form advanced configuration with colored labels
   :width: 80%


Using MATCH for cross-form callbacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``MATCH`` allows a single callback to respond to the same field across multiple ``InputForm``
instances. This is useful for composed layouts that embed several independent forms of the same
structure. The following example shows how to turn off certain parameters when a "Use defaults"
checkbox is toggled in either form (for example, front, and rear wheels in a configuration panel):

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_form.py
   :language: python
   :start-after: # [disable-parameters-callback-start]
   :end-before: # [disable-parameters-callback-end]

This callback fires independently for each form instance (for example, for "Front Wheels" and
"Rear Wheels") whenever the checkbox changes in either form.

.. note::

    Using ``ALL`` for ``row_index`` allows to target all rows in the form without having to specify
    the row index explicitly, but it means that the callback receives lists of values for all
    rows, even if only one row contains the targeted field, and that the outputs must also be lists.

    The preceding example assumes that only one row contains the ``use_defaults`` checkbox, so
    the first element of the list in the callback is taken. It also assumes that only one row with a
    ``diameter`` and one row with a ``wheel_material`` field exist, so a single
    boolean value in lists is returned for the outputs.

    To avoid this, you can specify the row index explicitly instead of using ``ALL`` for more
    precise targeting. In this case, it is advisable to set the row index using the ``"id"`` key in
    the row definition to ensure it is unique and easily identifiable.


Value persistence
-----------------

By default, UI-side persistence is **disabled** (``persistence=False``) for all fields.
To enable it globally, set the ``persistence`` parameter on the ``InputForm`` constructor.
You can also configure the storage type via ``persistence_type`` (``"memory"``,
``"session"``, or ``"local"``, default is ``"memory"``).

Individual fields can override the global setting by including a ``"persistence"`` key in
their field definition. This allows, for example, enabling persistence for most fields
while preventing sensitive values (such as passwords or tokens) from being stored in the
browser.

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_form.py
   :language: python
   :start-after: # [control-persistence-start]
   :end-before: # [control-persistence-end]

.. note::

    UI-side persistence only stores values in the browser. To durably persist form
    values on the server (per project and across reloads), use a callback that writes the
    form values to your solution model, for example, when the user clicks a **Save** or **Apply**
    button (shown here for a SAF-based solution, but the same principle applies to any Dash app):

    .. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/super_components_with_saf/src/ansys/solutions/super_components_with_saf/ui/app.py
       :language: python
       :start-after: # [save-input-form-start]
       :end-before: # [save-input-form-end]

    When the layout function initialises each field with a value from the backend
    (for example, ``"value": step.project_name``), the first page load always reflects
    the last saved state. Subsequent navigations within the same browser tab then show the
    user's in-progress edits thanks to UI-side persistence, until the next save or
    reload.


Toggling hidden fields using callbacks
---------------------------------------

Fields can be hidden on initialization by setting ``"hidden": True`` in the field definition.
Hidden fields are wrapped in an ``html.Div`` with ``style={"display": "none"}``, so they are
invisible in the UI but still present in the component tree.

To toggle field visibility dynamically, use ``InputForm.ids.field_div()``—which targets the
wrapping ``html.Div``—as the callback ``Output``:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_input_form.py
   :language: python
   :start-after: # [toggle-visibility-callback-start]
   :end-before: # [toggle-visibility-callback-end]

The resulting output with the checkbox checked might look like this:

.. image:: /_static/dash-media/input_form/advanced_configuration_slider_enabled.png
   :alt: Input Form advanced configuration with slider enabled
   :width: 80%


Properties
==========

Item keys
---------

==============  =============================================  ===================  =========
Key             Description                                    Type                 Required
==============  =============================================  ===================  =========
label           A string that describes the input.             string               No
fields          A list of dictionaries, each defining          list                 Yes
                an input field.
help            A list of or a singular Dash component,        any                  No
                string, or number to indicate to the user
                how to use or where to get the information
                for the input. Displayed in a modal when
                the help icon is clicked.
unit            A LaTeX string that describes the unit of      string               No
                the input. Rendered with MathJax.
description     A sentence that describes the input.           string               No
id              A unique identifier for the row. Used as       string               No
                the ``row_index`` in all component IDs for
                this row. If not set, the zero-based
                position of the row is used instead.
==============  =============================================  ===================  =========


Field keys
----------

==============  ===============================================  ===================  =========
Key             Description                                      Type                 Required
==============  ===============================================  ===================  =========
type            The input field type: ``"NumberInput"``,         string               Yes
                ``"TextInput"``, ``"PasswordInput"``,
                ``"Checkbox"``, ``"Select"``,
                ``"MultiSelect"``, ``"Slider"``,
                or ``"Switch"``.
id              A unique identifier for the field. Used as       string               Yes
                the ``field_id`` in all component IDs for
                this field.
hidden          If ``True``, the field is not displayed          boolean              No
                (that is, ``display: none``). The field can
                be shown dynamically using callbacks via
                ``InputForm.ids.field_div()``.
                Default: ``False``.
persistence     Controls whether the field value is persisted    boolean               No
                in the browser. When ``True``, the value
                survives page navigation within the same tab.
                When ``False``, the value resets to the
                initial ``value`` on every render.
                Default: the global ``persistence`` setting
                of the ``InputForm`` (``False`` if not set).
==============  ===============================================  ===================  =========

In addition, each field dictionary accepts any property supported by the corresponding
Dash Mantine component: ``NumberInput``, ``TextInput``, ``PasswordInput``, ``Checkbox``,
``Select``, ``MultiSelect``, ``Slider``, or ``Switch``.


Constructor parameters
----------------------

================  ======================================================================  ========  =========
Name              Description                                                             Type      Required
================  ======================================================================  ========  =========
items             A list of dictionaries, each defining a row of the input form.          list      Yes
title             The title displayed at the top of the form card.                        string    No
with_card         If ``True``, wraps the form in a ``dmc.Card``.                          boolean   No
                  Default: ``True``.
card_props        Properties for the ``dmc.Card`` wrapping the form.                      dict      No
                  Default:
                  ``{"withBorder": True, "shadow": "sm", "radius": "md"}``.
title_props       Properties for the title ``dmc.Text`` component.                        dict      No
                  Default:
                  ``{"style": {"fontSize": "18px", "fontWeight": "bold"}}``.
columns           List of column types to display, in order. Accepted values:             list      No
                  ``"label"``, ``"fields"``, ``"unit"``, ``"help"``,
                  ``"description"``.
                  Default: ``["label", "fields", "unit", "description", "help"]``.
column_widths     Dictionary mapping column names to integer widths (Mantine              dict      No
                  grid ``span`` units). Unspecified columns use built-in defaults.
                  Default:
                  ``{"label": 2, "fields": 5, "unit": 1, "description": 3, "help": 1}``.
column_names      List of strings to use as column header labels, in the same             list      No
                  order as ``columns``. If provided, a header row is added.
aio_id            A unique identifier for the component instance.                         string    No
                  If not provided, a UUID is generated.
persistence       Whether to enable UI-side persistence for all form fields.              boolean   No
                  When ``True``, user-entered values survive page navigation
                  within the same browser tab. Individual fields can override
                  this global setting via ``"persistence"`` in the field dict.
                  Default: ``False``.
persistence_type  The Dash persistence storage type. Accepted values:                     string    No
                  ``"memory"`` (cleared on page reload), ``"session"``
                  (cleared when the browser tab is closed), ``"local"``
                  (persists across reloads and browser restarts). Only
                  relevant when ``persistence`` is ``True``.
                  Default: ``"memory"``.
================  ======================================================================  ========  =========


Component IDs
-------------

The component exposes the following IDs for use in callbacks:

Row-level subcomponents
~~~~~~~~~~~~~~~~~~~~~~~

- ``InputForm.ids.label(aio_id, row_index)``: The ``dmc.Text`` label component of a row.
- ``InputForm.ids.unit(aio_id, row_index)``: The ``dmc.Text`` unit component of a row.
- ``InputForm.ids.description(aio_id, row_index)``: The ``dmc.Text`` description component of
  a row.
- ``InputForm.ids.help(aio_id, row_index)``: The ``dmc.ActionIcon`` help button of a row.
- ``InputForm.ids.modal(aio_id, row_index)``: The ``dmc.Modal`` help modal of a row.

These IDs are indexed by ``aio_id`` and ``row_index``. The ``row_index`` is the value of the
``"id"`` key in the row definition (``item["id"]``), or the zero-based integer position of the row
if no ``"id"`` key is set.

Field-level subcomponents
~~~~~~~~~~~~~~~~~~~~~~~~~

- ``InputForm.ids.field(aio_id, field_type, field_id, row_index)``: The input field component
  itself (for example, a ``dmc.NumberInput``).
- ``InputForm.ids.field_div(aio_id, field_type, field_id, row_index)``: The ``html.Div``
  wrapping the input field. Use this ID to toggle field visibility dynamically.

These IDs are indexed by ``aio_id``, ``field_type`` (``field["type"]``), ``field_id``
(``field["id"]``), and ``row_index``.


.. _ref_input_form_full_example:

Full example
============

Check out this `example <https://github.com/ansys/saf/blob/main/packages/dash-super-components/examples/showcase_all/src/ansys/solutions/showcase_dash_super_components/ui/pages/input_form_page.py>`_
to learn how to use ``InputForm``.

The example demonstrates:

- A minimal form using the default column layout with labels embedded in the field
  definitions
- A form with all supported field types (``TextInput``, ``Select``, ``MultiSelect``,
  ``NumberInput``, ``Checkbox``, ``Switch``, ``Slider``, ``PasswordInput``) in a
  four-column configuration with named row IDs
- Retrieving field values using specific ``ids.field()`` IDs, reading a single named field,
  and collecting all fields of a given type with ``ALL`` wildcards
- A form using all five columns (``label``, ``fields``, ``unit``, ``description``, ``help``)
  with images in the help column and custom title and card appearance
- Toggling the visibility of individual fields within a row using a checkbox
- Two ``InputForm`` instances without a card wrapper composed inside a shared card, with
  ``MATCH`` callbacks that turn off fields and update label and unit colors based on the
  entered value

For a minimal self-contained runnable example, see the
:ref:`sphx_glr_examples_dash_super_components_examples_general_example_input_form.py` page in the Examples gallery.


Source code
===========

For the full API reference of ``InputForm``, see
:class:`~ansys.solutions.dash_super_components.InputForm`.

Check out the `component source code <https://github.com/ansys/saf/blob/main/packages/dash-super-components/src/ansys/solutions/dash_super_components/input_form.py>`_
to discover the underlying logic. Contributions are welcomed. You can extend the component
functionalities by raising a pull request in the
`dash-super-components <https://github.com/ansys/saf/tree/main/packages/dash-super-components>`_ package.
