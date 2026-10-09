.. _user_guide_frontend_dash_super_components_usage_folder_selector:

Folder Selector
###############

``FolderSelector`` is a Dash All-in-One (AIO) component for browsing and selecting a directory. It
can operate in two modes: a native OS dialog (tkinter mode) and a browser-based modal with a tree
view of the file system (bootstrap mode).

Key features:

- **Dual operating modes**: Supports tkinter (native OS dialog) and bootstrap (browser modal, requires beta opt-in) modes.
- **Automatic mode selection**: Automatically selects the best mode based on environment and
  ``tkinter`` availability.
- **Flexible configuration**: Customizable browse and clear buttons, default path, and maximum path
  length.
- **Readable long-path display**: Built-in selected-path display supports line clamping with
  ellipsis and full-path tooltip on hover.
- **Environment variable support**: Mode and root path can be configured via environment variables
  for remote or containerized deployments.

.. note::
    tkinter is Python's standard library for creating graphical user interfaces (GUIs). It is
    included in the standard Python library and thus is available by default in most Python
    installations, but may not be available in some minimal or custom Python installations.


.. image:: /_static/dash-media/folder_selector/folder_selector_component.png
  :alt: Folder Selector component
  :width: 80%



Usage
=====

.. warning::

    The ``FolderSelector`` component must be wrapped inside a ``MantineProvider`` with a
    ``dmc.NotificationContainer`` present in the application layout for error notifications
    to work properly. If the notification container is missing or not properly configured, errors
    fail silently without feedback to the user.
    See the :ref:`ref_notification_container` section of the Getting
    Started page for instructions, including how to customize the container id via
    :func:`~ansys.solutions.dash_super_components.configure`.

Basic usage
-----------

Import ``FolderSelector``:

.. code-block:: python

    from ansys.solutions.dash_super_components import FolderSelector


Add ``FolderSelector`` to the page layout:

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_folder_selector.py
   :language: python
   :start-after: # [basic-layout-start]
   :end-before: # [basic-layout-end]

The following output is expected:


.. image:: /_static/dash-media/folder_selector/default_configuration.png
   :alt: Default configuration of the Folder Selector component
   :width: 80%


Advanced usage
--------------

The following example shows how to use the component in bootstrap mode and customize its button
properties and options.

Bootstrap mode is a beta feature and is disabled by default. To enable it, call
:func:`~ansys.solutions.dash_super_components.configure` during app startup (for the
package-level beta feature setup, see :ref:`ref_enable_beta_features`):

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_folder_selector.py
   :language: python
   :start-after: # [configure-start]
   :end-before: # [configure-end]

To make the ``FolderSelector`` use bootstrap mode, import ``FolderSelectorMode`` in addition to
``FolderSelector`` and set the ``mode`` parameter to ``FolderSelectorMode.BOOTSTRAP`` when
instantiating the component. In addition, pass custom settings in the ``options``
dictionary, and customize the appearance of the browse and clear buttons with the
``browse_button_props`` and ``clear_button_props`` dictionaries:

.. code-block:: python

    from ansys.solutions.dash_super_components import FolderSelector
    from ansys.solutions.dash_super_components.folder_selector import FolderSelectorMode

.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_folder_selector.py
   :language: python
   :start-after: # [advanced-layout-start]
   :end-before: # [advanced-layout-end]

The following output is expected:

.. image:: /_static/dash-media/folder_selector/custom_configuration.png
   :alt: Custom configuration of the Folder Selector component
   :width: 80%


.. warning::

    In bootstrap mode, you must provide a root path for the folder tree by setting either
    ``options["browse_from"]`` or the ``FOLDER_SELECTOR_BROWSE_FROM`` environment variable.


Accessing the selected folder
-----------------------------

The selected folder path can be accessed in a callback function using the
``FolderSelector.ids.selected_folder(aio_id)`` store ID. The value is a string representing
the selected folder path, or ``None`` if no folder is selected.


.. literalinclude:: ../../../../../../../packages/dash-super-components/examples/user_guide/example_folder_selector.py
   :language: python
   :start-after: # [callback-start]
   :end-before: # [callback-end]

.. warning::

    The selected folder value is client-side browser state and should be treated
    as not trusted input (that is, it should be validated before use).

Properties
==========

Constructor parameters
----------------------

.. vale Google.Spacing = NO

===================  ====================================================================================  ==================  ========
Parameter            Description                                                                           Type                Required
===================  ====================================================================================  ==================  ========
mode                 The technology to be used to create the folder selector pop-up.                       FolderSelectorMode  No
                     Can be ``FolderSelectorMode.TKINTER`` or ``FolderSelectorMode.BOOTSTRAP``.
                     If not specified, automatically selects based on ``tkinter`` availability
                     and ``FOLDER_SELECTOR_REMOTE_DEPLOYMENT`` environment variable when
                     bootstrap beta is enabled via
                     ``configure(enable_beta_features=True)``.
aio_id               The unique identifier for the component. If not provided, a UUID is generated.        str                 No
browse_button_props  Properties for the browse button. See `dmc.Button properties                          dict                No
                     <https://www.dash-mantine-components.com/components/button>`_.
                     Default includes a folder icon and "Browse" text.
clear_button_props   Properties for the clear button. See `dmc.ActionIcon properties                       dict                No
                     <https://www.dash-mantine-components.com/components/actionicon>`_.
                     Default includes a delete icon.
style                Style properties for the component container.                                         dict                No
options              Dictionary containing additional configuration options (see below).                   dict                No
value                The preselected folder path. Populates the selected folder store upon instantiation.  str                 No
===================  ====================================================================================  ==================  ========

.. vale Google.Spacing = YES

Options dictionary
------------------

The ``options`` parameter accepts a dictionary with the following keys:

=====================  =================================================================  ======  ========
Key                    Description                                                        Type    Required
=====================  =================================================================  ======  ========
default_path           The path to be used as a default value for the selected folder     str     No
                       when no folder has been selected yet or the selection has been
                       cleared.
browse_from            The path to be used as a root for folder selection. Only works     str     No
                       with bootstrap mode. In bootstrap mode, this value must be
                       provided either in ``options`` or with an environment variable
                       ``FOLDER_SELECTOR_BROWSE_FROM``.
topmost                If set to ``True``, the dialog window is shown in the foreground   bool    No
                       (tkinter mode only).
                       Default: ``True``.
max_path_length        The maximum length of the path that can be selected.               int     No
                       Default: System-dependent maximum path length.
max_tree_depth         The maximum folder depth included in bootstrap tree generation.     int     No
                       Default: ``10``.
max_children_per_node  The maximum child folders included for each tree node         int     No
                       in bootstrap mode. Additional folders are omitted from the tree.
                       Default: ``100``.
display_field          Dictionary with ``enabled`` (bool) and optional                    dict    No
                       ``max_display_lines`` (int) keys. If ``enabled`` is ``True``,
                       the selected folder path is displayed below the buttons.
                       The display is truncated with ellipsis after a maximum number of
                       lines specified by ``max_display_lines`` and the full path is
                       available via tooltip on hover.
                       Default: ``{"enabled": True, "max_display_lines": 2}``.
=====================  =================================================================  ======  ========


Component IDs
-------------

The component exposes the following IDs for use in callbacks:

- ``FolderSelector.ids.selected_folder(aio_id)``: Store containing the selected folder path (str or
  None)
- ``FolderSelector.ids.browse_button(aio_id)``: The browse button component
- ``FolderSelector.ids.clear_button(aio_id)``: The clear button component


Operating modes
===============

Tkinter mode
------------

- Uses native OS dialog window for folder selection
- Provides familiar OS-native user experience
- Requires ``tkinter`` package to be available
- Selected via ``mode=FolderSelectorMode.TKINTER``
- Respects the ``topmost`` option to control window layering

.. image:: /_static/dash-media/folder_selector/tkinter_mode_dialog.png
   :alt: Tkinter mode dialog of the Folder Selector component
   :width: 85%

.. _ref_folder_selector_bootstrap:

Bootstrap mode
--------------

Bootstrap mode is a beta capability for browser-based folder selection in controlled environments
when ``tkinter`` is not available. It should not be used in production environments.

- Is a beta feature and can only be used when enabled through
  :func:`~ansys.solutions.dash_super_components.configure` with
  ``enable_beta_features=True``
  (see :ref:`ref_enable_beta_features`).
- Uses browser-based modal with tree view of file system
- Works in environments where ``tkinter`` is not available (for example, remote deployments)
- Requires ``browse_from`` to be defined through ``options`` or
  ``FOLDER_SELECTOR_BROWSE_FROM`` environment variable
- Hidden folders and symlink folders are excluded from the tree
- Supports tree-size controls through ``max_tree_depth`` and ``max_children_per_node``
- Selected via ``mode=FolderSelectorMode.BOOTSTRAP``
- Automatically activated (when mode is omitted) if bootstrap beta is enabled and
  ``FOLDER_SELECTOR_REMOTE_DEPLOYMENT`` environment variable is set to ``true``, ``1``, or ``yes``

.. image:: /_static/dash-media/folder_selector/bootstrap_mode_modal.png
   :alt: Bootstrap mode modal of the Folder Selector component
   :width: 80%


**Operational guidance**

- Set ``browse_from`` to the narrowest practical root
- Avoid broad roots such as monorepo roots or system-level roots
- Keep ``max_tree_depth`` and ``max_children_per_node`` conservative for responsiveness
- Prefer tkinter mode for production workflows when native GUI access is available


Environment variables
=====================

==================================  ================================================================
Variable                            Description
==================================  ================================================================
FOLDER_SELECTOR_REMOTE_DEPLOYMENT   If set to ``true``, ``1``, or ``yes``, forces bootstrap mode
                                    when bootstrap beta is enabled via
                                    ``configure(enable_beta_features=True)``.
                                    Useful for remote or containerized deployments.
FOLDER_SELECTOR_BROWSE_FROM         Specifies the root path for folder browsing in bootstrap mode.
                                    Can be overridden by the ``browse_from`` option.
==================================  ================================================================


Limitations
===========

- Bootstrap mode is intended for controlled environments with a narrowly scoped
  ``browse_from`` root and trusted usage patterns.
- The tree can omit folders when ``max_tree_depth`` or ``max_children_per_node`` limits are reached.
  In that case, the affected nodes include a description message indicating truncation.
- Hidden folders (names beginning with ``.``) and symlink folders are intentionally excluded from
  the bootstrap tree.
- If ``tkinter`` is unavailable and bootstrap beta is not enabled, folder browsing is blocked and
  the component shows a notification explaining how to enable bootstrap mode.
  See :ref:`ref_enable_beta_features`.


Full example
============

For a complete working example, check out the `showcase example
<https://github.com/ansys/saf/blob/main/packages/dash-super-components/examples/showcase_all/src/ansys/solutions/showcase_dash_super_components/ui/pages/folder_selector_page.py>`_.

The example demonstrates:

- A basic folder selector using default settings, with the selected path displayed via a
  callback
- Switching between bootstrap and tkinter modes, toggling the built-in path display field,
  toggling a default path, and setting ``max_display_lines`` via the ``options`` dictionary
- Custom styling of the component container, browse button, and clear button
- Two folder selectors demonstrating persistence strategies: no persistence (resets on
  recreation) and backend persistence (restored from the server per project)

For a minimal self-contained runnable example, see the
:ref:`sphx_glr_examples_dash_super_components_examples_general_example_folder_selector.py` page in the Examples gallery.

file:///D:/AnsysDev/Solutions-Manager-Doc-Migration/saf/doc/build/html/examples/dash_super_components_examples/general/example_folder_selector.html

Notes
=====

- Consider preserving the selected folder value by passing it to the ``value`` parameter, so it gets
  preserved when recreating the component with different settings etc.
- The ``browse_from`` option is only effective in bootstrap mode and has no effect in tkinter mode
- Path validation is automatically performed based on the ``max_path_length`` setting


Source code
===========

For the full API reference of ``FolderSelector``, see
:class:`~ansys.solutions.dash_super_components.FolderSelector`.

Check out the `component source code <https://github.com/ansys/saf/blob/main/packages/dash-super-components/src/ansys/solutions/dash_super_components/folder_selector.py>`_
to discover the underlying logic. Contributions are welcomed. You can extend the component
functionalities by raising a pull request in the
`dash-super-components <https://github.com/ansys/saf/tree/main/packages/dash-super-components>`_ package.
