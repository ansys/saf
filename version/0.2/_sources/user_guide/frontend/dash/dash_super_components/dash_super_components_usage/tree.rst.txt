.. _user_guide_frontend_dash_super_components_usage_tree:

Tree
#####

``Tree`` is a Dash All-in-One (AIO) component for creating a navigation sidebar in a Dash
application. Based on the ``NavLink`` component from the ``Dash Mantine Components`` library, it
provides a hierarchical tree structure for page navigation, or displaying and navigating general
tree-like data (for example, filesystem hierarchies).

Key features:

- **Hierarchical navigation**: Supports multi-level tree structures with parent-child relationships.
- **Node customization**: Expandable and collapsible nodes, disabled nodes, icons, and descriptions.
- **Callback integration**: The selected item is accessible via a component ID for implementing
  page routing.
- **Offline support**: Local icon support using the assets folder or base64 images.

.. image:: /_static/dash-media/tree/example_output.png
   :alt: Tree component example output
   :width: 45%


Usage
=====

Configure the Dash application
------------------------------

To display icons, ``Tree`` relies on package assets served by Super Components for Dash. Refer to
the :ref:`ref_register_component_assets` section of the Getting Started guide for instructions on
registering the assets. Specifically, you must call
:func:`~ansys.solutions.dash_super_components.add_super_components_assets` to register the Flask
endpoint that serves the assets.

Basic usage
-----------

Import ``Tree``:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_tree.py
   :language: python
   :start-after: # [imports-start]
   :end-before: # [imports-end]

.. note::

   The ``create_base64_svg_src()`` utility produces offline-compatible icons. For information
   about the available icon options and their advantages, see :ref:`user_guide_frontend_dash_super_components_usage_icons`.

Define a simple two-level tree structure and add the ``Tree`` component to the layout:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_tree.py
   :language: python
   :start-after: # [basic-items-start]
   :end-before: # [basic-items-end]

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_tree.py
   :language: python
   :start-after: # [basic-layout-start]
   :end-before: # [basic-layout-end]

The following output is expected:

.. image:: /_static/dash-media/tree/default_configuration.png
   :alt: Tree component default configuration
   :width: 55%


Accessing the selected item in callbacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To access the currently selected item in a callback, use the ``Tree.ids.selected_item(aio_id)``
component ID as an input. The value of this store is a dictionary containing the key ``"index"``,
which corresponds to the ``id`` of the selected tree item.

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_tree.py
   :language: python
   :start-after: # [basic-callback-start]
   :end-before: # [basic-callback-end]

When item ``Step 1-1`` is selected, the expected output is:

.. code-block:: none

    Selected: step_11


Advanced usage
--------------

The following example shows how to integrate ``Tree`` as a multi-page navigation sidebar.
The tree is defined once in the ``page.py`` module (note that the layout needs to be wrapped in
a ``MantineProvider``). The page content is then driven by a callback that listens to both the URL
and the selected tree item, and updates the page content accordingly:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_tree_multipage.py
   :language: python
   :start-after: # [tree-multipage-start]
   :end-before: # [tree-multipage-end]

The resulting page layout is as follows (with the tree navigation on the left and the
page content on the right):

.. image:: /_static/dash-media/tree/custom_configuration.png
   :alt: Tree component custom configuration
   :width: 50%

Styling
-------

Each tree item accepts an optional ``styles`` dictionary that is forwarded directly to the
underlying ``dmc.NavLink`` component. This allows fine-grained control over the appearance of
individual tree nodes.

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_tree.py
   :language: python
   :start-after: # [styling-items-start]
   :end-before: # [styling-items-end]

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_tree.py
   :language: python
   :start-after: # [styling-layout-start]
   :end-before: # [styling-layout-end]

The following output is expected:

.. image:: /_static/dash-media/tree/styled_tree.png
   :alt: Tree component styled output
   :width: 60%

.. note::
    It is important to note that controlling styles manually can interfere with the automatic
    light/dark mode adaptation mechanisms of the Mantine framework, as well as highlighting of the
    selected item and when hovering over items.

.. note::

    Styles are applied **per item** and are **not inherited** by children. Each child node
    must define its own ``styles`` dictionary if custom styling is required.

.. _ref_tree_icons:

Icons
=====

Each tree item can display an icon to the left of its label. The primary item-level property is
``icon``, and the constructor exposes ``default_icon`` as a fallback.

If an item defines ``icon``, that value is used. Otherwise, ``default_icon`` is used when
provided. If neither ``icon`` nor ``default_icon`` is provided, no icon is rendered for that
item.

Icon types
----------

Icon values can be local image values (a path relative to the application's ``assets`` folder or
a base64-encoded image string, for example produced by ``create_base64_svg_src()``) or an icon
name from the `Iconify <https://icon-sets.iconify.design/>`_ online icon service (for
example, ``"material-symbols:folder"``).

By default, the icon rendering mode is inferred automatically from the resolved icon value. You can
override this behavior per item via ``icon_type``:

- ``"auto"`` (default): infer whether to render as local image or Iconify icon.
- ``"local"``: render with a local CSS-mask icon. Use for local image values only (assets paths
  or base64 data URI values).
- ``"iconify"``: render with ``DashIconify``. Use for Iconify icon names and internet-connected
  deployments.

The following example demonstrates the three icon rendering modes:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_tree.py
  :language: python
  :start-after: # [icon-type-items-start]
  :end-before: # [icon-type-items-end]

.. note::

    Local icons must be given as strings that are either a path relative to the application's
    ``assets`` folder or a base64-encoded image string. Dash HTML elements are not supported as
    icon values.

.. _ref_tree_dark_mode_strategies:

Dark mode behavior and icon color handling
------------------------------------------

Tree icons use ``currentColor`` by default, so they follow the active state and the current
color scheme automatically. To override icon color per item, set ``icon_color`` in the item
definition.

The following example demonstrates the behavior of the icon color handling strategies for light and
dark mode:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_tree.py
  :language: python
  :start-after: # [icons-dark-mode-options-start]
  :end-before: # [icons-dark-mode-options-end]

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_tree.py
  :language: python
  :start-after: # [layout-dark-mode-options-start]
  :end-before: # [layout-dark-mode-options-end]

The following output is expected:

.. grid:: 2
   :gutter: 4

   .. grid-item::

      .. figure:: /_static/dash-media/tree/dark_mode_options_light.png
        :alt: Tree dark mode options in light mode

        Light mode

   .. grid-item::

      .. figure:: /_static/dash-media/tree/dark_mode_options_dark.png
        :alt: Tree dark mode options in dark mode

        Dark mode


Properties
==========

.. _tree_item_definition_properties:

Tree structure definition
-------------------------

.. list-table::
  :stub-columns: 1
  :header-rows: 1

  * - Key
    - Description
    - Type
    - Required

  * - ``id``
    - The unique identifier of the item.
    - string
    - Yes

  * - ``text``
    - The text displayed in the item.
    - string
    - Yes

  * - ``icon``
    - The icon value displayed in the item. Supports local image values
      (for example, ``/assets/...`` or base64 data URI values) and Iconify icon names.
    - string
    - No

  * - ``icon_color``
    - Optional CSS color for the item icon.

      If omitted, the icon inherits ``currentColor``.
    - string
    - No

  * - ``icon_type``
    - Explicit icon rendering mode: ``"auto"``, ``"local"``, or ``"iconify"``.

      Default: ``"auto"``.
    - string
    - No

  * - ``expanded``
    - Controlled nested items collapse state. Sets the initial open/closed state on load.

      Default: ``False`` (collapsed)
    - boolean
    - No

  * - ``disabled``
    - Turn off item selection.

      Default: ``False`` (enabled)
    - boolean
    - No

  * - ``description``
    - The item description added below the text.

      Default: ``""`` (no description)
    - string
    - No

  * - ``styles``
    - A dictionary of styles applied to the NavLink sub-components (for example, ``"label"``, ``"root"``).

      If styles ``["label"]["color"]`` is not set, it defaults to ``"var(--mantine-color-text)"``.

      Default: ``{"label": {"color": "var(--mantine-color-text)"}}`` (default label color applied)
    - dict
    - No

  * - ``children``
    - The list of children of the item.

      If not provided, the item is considered a leaf node without children.
    - list
    - No


Constructor parameters
----------------------


.. list-table::
  :stub-columns: 1
  :header-rows: 1

  * - Key
    - Description
    - Type
    - Required

  * - ``items``
    -  A list of dictionaries representing the tree structure.
    - list
    - Yes

  * - ``selected_item``
    -  The unique id of the initially selected tree item.

       Default: ``None`` (no item selected)
    - string
    - No

  * - ``default_icon``
    -  The default icon value displayed for tree items when ``icon`` is not provided.
       Supports local image values and Iconify icon names.

       Default: ``None`` (no item selected)
    - string
    - No

  * - ``aio_id``
    - The unique identifier for the component.

      If not provided, a UUID is generated.
    - string
    - No


Component IDs
-------------

The component exposes the following IDs for use in callbacks:

- ``Tree.ids.selected_item(aio_id)``: Store containing the currently selected item data
  (dict with ``"index"`` key matching the selected item's ``id``). Can also be used as an output of
  a callback to programmatically set the selected item.
- ``Tree.ids.navlink_item(aio_id, index)``: Individual navigation link items (use ``ALL``
  wildcard for the ``index`` to match all items)

.. warning::

  ``Tree.ids.navlink_item(aio_id, index)`` is supported for controlling component properties such as
  ``disabled``, but it must not be used with ``n_clicks`` to detect click events.

  To detect selection changes, always use ``Tree.ids.selected_item(aio_id)``.


Limitations
===========

- Iconify-based icons require internet access. For offline deployments, use local image values
  (assets paths or base64 data URI values).
- Tree icons require
  :func:`~ansys.solutions.dash_super_components.add_super_components_assets` to be called in order
  for the icons to be displayed. See :ref:`ref_register_component_assets`.


Full example
============

.. updated for metapackage

Check out this `example <https://github.com/ansys/saf/blob/main/packages/dash-super-components/examples/showcase_all/src/ansys/solutions/showcase_dash_super_components/ui/pages/tree_page.py>`_
to learn how to use ``Tree`` as a standalone component.

The example demonstrates:

- A minimal tree using only the required item properties (``id`` and ``text``)
- A full-featured tree using online Iconify icons (internet required), descriptions,
  mixed expanded and collapsed state, a disabled item, a preselected item, and a button
  callback that jumps the selection to a certain tree item. The selected item is persisted on the
  backend and restored on page reload.
- A styled tree using offline-compatible ``create_base64_svg_src()`` icons with
  item-level ``styles`` and ``icon_color`` for coloring node labels and icons
- A tree demonstrating explicit ``icon_type`` overrides (``"local"`` and ``"iconify"``)
  and an item rendered without any icon
- A workflow tree where nodes can be disabled and re-enabled via callbacks, with three
  scenarios: disabling a single node, a downstream range of nodes, and the entire tree
- A callback per tree displaying the currently selected item

For a complete example of ``Tree`` used as a navigation sidebar for a multi-page application,
see the `showcase application page.py <https://github.com/ansys/saf/blob/main/packages/dash-super-components/examples/showcase_all/src/ansys/solutions/showcase_dash_super_components/ui/pages/page.py>`_.

This file shows how ``Tree`` drives page routing across all component pages of the showcase
application.

For a minimal self-contained runnable example, see the
:ref:`sphx_glr_examples_dash_super_components_examples_general_example_tree.py` page in the Examples gallery.


Source code
===========

For the full API reference of ``Tree``, see
:class:`~ansys.solutions.dash_super_components.Tree`.

Check out the `component source code <https://github.com/ansys/saf/blob/main/packages/dash-super-components/src/ansys/solutions/dash_super_components/tree.py>`_
to discover the underlying logic. Contributions are welcomed. You can extend the component
functionalities by raising a pull request in the
`dash-super-components <https://github.com/ansys/saf/tree/main/packages/dash-super-components>`_ package.
