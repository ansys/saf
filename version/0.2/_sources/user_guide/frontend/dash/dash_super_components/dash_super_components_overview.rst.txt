.. _user_guide_frontend_dash_super_components_overview:

Overview
#########


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
  integrate with the Solutions Application Framework (SAF) GLOW API to visualize the
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

