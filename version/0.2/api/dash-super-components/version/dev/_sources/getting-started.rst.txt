.. _ref_getting_started:

Getting started
###############

Dash Super Components is a collection of pre-assembled, high-level UI components
built on top of the `Dash Mantine Components (DMC) <https://www.dash-mantine-components.com/>`_
library. The components implement common patterns in simulation web app UIs, reducing
frontend development effort by packaging UI logic and layout conventions into smart
building blocks. Some components are specifically designed for use with the
Solution Application Framework (SAF) GLOW API. Other components are general-purpose and can be used
in any Dash application.

For a full list of available components, see the :ref:`ref_user_guide` section.


Installation
============

Install Dash Super Components from `PyPI <https://pypi.org/>`_ using pip:

.. code-block:: bash

   pip install ansys-solutions-dash-super-components

Alternatively, if your project uses `Poetry <https://python-poetry.org/>`_, add
the package to your project dependencies:

.. code-block:: bash

   poetry add ansys-solutions-dash-super-components


Requirements
------------

- Python 3.11 to 3.14. Higher versions may work but are not officially supported.


Configure the Dash application
==============================

All Super Components use the ``callback`` decorator and other utilities from
``dash_extensions.enrich``. This means your application **must** use
``dash_extensions.enrich.DashProxy`` instead of the standard ``dash.Dash``. Using
``dash.Dash`` directly causes the internal callbacks of the components to fail.

Create your app with ``DashProxy``:

.. code-block:: python

   from dash_extensions.enrich import DashProxy

   app = DashProxy(__name__)

Every application that uses Super Components must also be configured with
the following steps.

Set the React version (only for Dash 2.x)
-----------------------------------------

Dash Mantine Components requires React 18.2.0, but the default Dash 2.x renderer
uses React 16. When using Dash 2.x, you must set the React version before creating
the ``DashProxy`` app instance:

.. code-block:: python

   from dash import _dash_renderer

   # Required for Dash 2.x
   _dash_renderer._set_react_version("18.2.0")

Wrap the layout in a ``MantineProvider``
-----------------------------------------

The root layout of your application must be wrapped in a ``dmc.MantineProvider``
to ensure that Dash Mantine Components are styled and themed correctly:

.. code-block:: python

   import dash_mantine_components as dmc

   app.layout = dmc.MantineProvider(children=[...])

For more details, see the official
`DMC getting started guide <https://www.dash-mantine-components.com/getting-started>`_.

.. _ref_notification_container:

Add a ``NotificationContainer``
--------------------------------

Some components, such as ``FolderSelector``, require a
:class:`~dash_mantine_components.NotificationContainer` to display error notifications.
Following the DMC recommendation of a single ``NotificationContainer`` per application,
add one as a child of ``MantineProvider``.

By default, Dash Super Components targets a container with ``id="notification-container"``.
Simply add one to your layout:

.. code-block:: python

   import dash_mantine_components as dmc

   app.layout = dmc.MantineProvider(
       children=[
           dmc.NotificationContainer(
               id="notification-container",
               position="bottom-center",
           ),
           # ... rest of the layout
       ]
   )

For more details, see the
`DMC NotificationContainer documentation <https://www.dash-mantine-components.com/components/notification>`_.

.. note::

   This step is only required when using components that rely on notifications, such as
   ``FolderSelector``. See the documentation of the individual components for details.

Customizing the container ID
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your application uses a different ID for the ``NotificationContainer``, call
:func:`~ansys.solutions.dash_super_components.configure` **before** building the layout
so that all components forward their notifications to the correct container:

.. code-block:: python

   import ansys.solutions.dash_super_components as dsc
   import dash_mantine_components as dmc

   # Tell all super components which container to target
   dsc.configure(notification_container_id="my-app-notifications")

   app.layout = dmc.MantineProvider(
       children=[
           dmc.NotificationContainer(
               id="my-app-notifications",
               position="bottom-center",
           ),
           # ... rest of the layout
       ]
   )

.. important::

   Call :func:`~ansys.solutions.dash_super_components.configure` *before* building
   the application layout, so that the updated ID is used when the components'
   callbacks fire.

.. _ref_color_scheme_toggle:

Add a ``ColorSchemeToggle`` for light/dark mode support
-------------------------------------------------------

To make your application compatible with light and dark mode, add a
:class:`~dash_mantine_components.ColorSchemeToggle` to your layout.
Components that react to light and dark mode, such as ``Tree``, react to the toggle's
state.

.. code-block:: python

   import dash_mantine_components as dmc

   app.layout = dmc.MantineProvider(
       children=[
           dmc.ColorSchemeToggle(id="color-scheme-toggle"),
           # ... rest of the layout
       ]
   )

.. _ref_register_component_assets:

Register component assets and add external scripts
--------------------------------------------------

Some components rely on package assets served by Dash Super Components.
For example, ``Tree`` uses these assets for component styling and icon rendering, and
``LogsSupervisor`` uses a custom JavaScript cell renderer for
displaying log level badges in the AG Grid table.

To support these components, register the Flask endpoint that serves the assets:

.. code-block:: python

   from dash_extensions.enrich import DashProxy
   from ansys.solutions.dash_super_components import add_super_components_assets

   app = DashProxy(__name__)

   # Register the Flask endpoint to serve super-components assets
   add_super_components_assets(app)

If you use ``LogsSupervisor``, you must also add the AG Grid renderer script in
``external_scripts``:

.. code-block:: python

   from dash_extensions.enrich import DashProxy

   app = DashProxy(
       __name__,
       external_scripts=["/super-components/dashAgGridComponentFunctions.js"],
   )

.. note::

   Registering the assets endpoint is required only for components that rely on
   these assets, such as ``Tree`` and ``LogsSupervisor``. See each component
   page for details. If not mentioned, registration is not required.

.. warning::

   If ``add_super_components_assets()`` is not called or ``external_scripts`` is not set correctly,
   components that depend on package assets or custom scripts might not render correctly. The
   components remain functional, but the appearance may be broken (for example icons not displaying)
   or missing features.


.. _ref_path_prefix:

Adding external scripts with a URL path prefix
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When your app uses a URL prefix (for example, in a containerized deployment where the app is
served under ``/myapp/``), the ``external_scripts`` path must include that prefix.

Build the ``external_scripts`` path from the same prefix used in ``requests_pathname_prefix``:

.. code-block:: python

   from dash_extensions.enrich import DashProxy
   from ansys.solutions.dash_super_components import add_super_components_assets

   url_prefix = "myapp"

   # Compute the external script path with the same prefix
   external_script = f"/{url_prefix}/super-components/dashAgGridComponentFunctions.js"

   app = DashProxy(
      __name__,
      requests_pathname_prefix=f"/{url_prefix}/",
      routes_pathname_prefix=f"/{url_prefix}/",
      external_scripts=[external_script],  # only needed for LogsSupervisor
   )
   add_super_components_assets(app)

.. note::

   Instead of setting both ``requests_pathname_prefix`` and ``routes_pathname_prefix`` in the app, you
   can also set the ``url_base_pathname`` parameter in the DashProxy constructor. This is equivalent
   to setting both prefixes to the same value.


.. note::

   This configuration is only needed when using a URL prefix. In a direct deployment which does not
   set a URL prefix, you can use the default ``external_scripts`` path
   ``"/super-components/dashAgGridComponentFunctions.js"``.

.. _ref_enable_beta_features:

Enable beta features
====================

Dash Super Components keeps beta features disabled by default.
To opt in, call :func:`~ansys.solutions.dash_super_components.configure` with
``enable_beta_features=True``.

If your application requires beta features, enable beta features before you build the application
layout:

.. code-block:: python

   import ansys.solutions.dash_super_components as dsc

   dsc.configure(enable_beta_features=True)

.. important::

   Call :func:`~ansys.solutions.dash_super_components.configure` before creating
   component instances so that all callbacks and runtime behavior use the updated
   configuration.

.. note::

   Currently, beta features are used by ``FolderSelector`` bootstrap mode. For bootstrap mode details, see  :ref:`ref_folder_selector_bootstrap`.


Minimal example
===============

The following minimal example shows how to add the :ref:`ref_dual_input_range_slider`
component to a Dash application:

.. code-block:: python

   import dash_mantine_components as dmc
   from dash import _dash_renderer
   from dash_extensions.enrich import DashProxy, html
   from ansys.solutions.dash_super_components import DualInputRangeSlider

   # Required for Dash 2.x
   _dash_renderer._set_react_version("18.2.0")

   app = DashProxy(__name__)

   app.layout = dmc.MantineProvider(
       children=[
           html.Div(
               [
                   DualInputRangeSlider(
                       aio_id="example-slider",
                       min=0,
                       max=100,
                       value=[20, 80],
                   )
               ],
               style={"padding": "40px"},
           )
       ]
   )

   if __name__ == "__main__":
       app.run(debug=True)

Run the example with the following command and open ``http://127.0.0.1:8050``
in your browser:

.. code-block:: bash

   python app.py

For small, runnable examples of the individual components, explore the
:ref:`ref_example_gallery`, and for a full application that showcases all components,
see the
`showcase application <https://github.com/ansys/saf/tree/main/packages/dash-super-components/examples/showcase_all>`_
in the repository.
