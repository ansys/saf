.. _ref_main_index:

Dash Super Components
#########################

Building simulation web app UIs with `Plotly Dash <https://dash.plotly.com/>`_ usually requires
wiring together many low-level primitives (buttons, input fields, dropdowns, tables, etc.) to
assemble richer UI elements from scratch. Dash Super Components provides a curated set of
production-ready, high-level components that encapsulate these recurring patterns into reusable
building blocks, so you can focus on application logic instead of UI plumbing.

.. note::

  Dash is a trademark of Plotly Technologies Inc. This project is not affiliated with, endorsed by,
  or sponsored by Plotly Technologies Inc.

How it works
============

Dash Super Components are built on top of
`Dash Mantine Components (DMC) <https://www.dash-mantine-components.com/>`_ and follow the Dash
`All-in-One (AIO) <https://dash.plotly.com/all-in-one-components>`_ pattern. Each component is
self-contained: layout, styling, and callback logic are bundled together and exposed through a
clean, declarative Python API. You configure a component with properties and receive its state in
callbacks without managing internal IDs or writing boilerplate callbacks.

When to use Dash Super Components
=====================================

- **Any Dash project**: general-purpose components such as ``Authenticator``,
  ``DualInputRangeSlider``, ``FolderSelector``, ``InputForm``, ``InputRowArray``,
  ``LogsSupervisor``, and ``Tree`` work in any Dash application.
- **SAF-based projects**: ``TransactionSupervisor`` and ``TransactionMethodStatusBadge``
  integrate with the Solution Application Framework (SAF) GLOW API to visualize the
  status and timing of long-running transaction methods.

Key features
============

- **Reduced boilerplate**: get polished, interactive UI patterns up and running with just a few
  lines of Python.
- **Self-contained components**: each component encapsulates its own layout, styling, and
  callback logic using the Dash AIO pattern. No internal IDs to manage.
- **Consistent design language**: all components share the same Mantine-based design system for
  a coherent look and feel across your application.
- **Declarative API**: configure components through Python properties and dictionaries.
- **Real-time capabilities**: built-in polling and auto-refresh for log monitoring and
  transaction status tracking.
- **Environment-aware behavior**: components adapt to the deployment context, for example
  ``FolderSelector`` switches between a native OS dialog and a browser-based modal depending
  on whether the app runs locally or in a remote environment.

.. grid:: 3

    .. grid-item-card:: :octicon:`rocket` Getting started
        :padding: 2 2 2 2
        :link: ref_getting_started
        :link-type: ref

        Install the library and set up your first Dash application.

    .. grid-item-card:: :octicon:`book` User guide
        :padding: 2 2 2 2
        :link: ref_user_guide
        :link-type: ref

        Explore each component with usage examples and configuration options.

    .. grid-item-card:: :octicon:`code-square` API reference
        :padding: 2 2 2 2
        :link: ref_api_index
        :link-type: ref

        Browse the full API reference for all classes and functions.

    .. grid-item-card:: :octicon:`play` Examples
        :padding: 2 2 2 2
        :link: examples/index
        :link-type: doc

        Browse the gallery of runnable examples.

    .. grid-item-card:: :octicon:`git-pull-request` Contribute
        :padding: 2 2 2 2
        :link: ref_contribute
        :link-type: ref

        Learn how to contribute to the library.

    .. grid-item-card:: :octicon:`tag` Release notes
        :padding: 2 2 2 2
        :link: ref_release_notes
        :link-type: ref

        View the changelog and release history.

.. toctree::
   :maxdepth: 2
   :hidden:

   getting-started
   user-guide/index
   api/index
   examples/index
   contribute
   changelog
