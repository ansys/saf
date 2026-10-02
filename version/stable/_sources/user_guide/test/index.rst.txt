.. _test:

Test
####

This page provides guidance for solution developers on how to use the testing fixtures provided by the
``ansys.saf.glow.testing`` pytest plugin for SAF GLOW Engine-based solutions. Pytest discovers the plugin automatically; no
fixture imports or ``pytest_plugins`` configuration are required.

The primary fixtures are:

- ``client_project``: Enables backend testing, giving you access to a GLOW client to interact with your solution's API. With this fixture, you can test transaction methods, operate with your step fields and validate project-level operations. The client is initiated with a random project for every single test.
- ``init_dashclient``: Enables frontend testing of your Dash callbacks and UI logic. You can then import your callbacks and execute them, also using the ``project_name`` fixture.
- ``mock_product_instance``: Extend backend testing to support transactions that use product instances, either in a shared or unshared way, without having to actually run the product.

In all cases, you don't need to externally launch your solution. The fixtures automatically launch and interact with your
Solution API in a process-based way using FastAPI's TestClient. All data is stored in temporary directories.
Furthermore, none of them require changes in your solution implementation or configuration.

These fixtures help you write robust tests for both backend logic and frontend user interfaces, ensuring your solution
works correctly in real-world scenarios while keeping tests isolated.

.. grid:: 3
   :gutter: 4
   :class-container: onboarding-cards

   .. grid-item-card:: :material-outlined:`play_arrow;1.75em` Quick start guide
      :class-card: highlight-card
      :link-type: doc
      :link: quick_start
      :shadow: lg

      Get started with installation and your first test.

   .. grid-item-card:: :material-outlined:`code;1.75em` Solution API
      :class-card: highlight-card
      :link-type: doc
      :link: solution_api
      :shadow: lg

      Test backend logic using the ``client_project`` fixture.

   .. grid-item-card:: :material-outlined:`web;1.75em` Solution UI
      :class-card: highlight-card
      :link-type: doc
      :link: solution_ui
      :shadow: lg

      Test Dash callbacks and UI logic using ``init_dashclient``.

   .. grid-item-card:: :material-outlined:`engineering;1.75em` Product Instances
      :class-card: highlight-card
      :link-type: doc
      :link: product_instances
      :shadow: lg

      Test transactions with mocked Ansys product instances.

   .. grid-item-card:: :material-outlined:`build;1.75em` Other fixtures
      :class-card: highlight-card
      :link-type: doc
      :link: other_fixtures
      :shadow: lg

      Configure solution environments and use additional utilities.

   .. grid-item-card:: :material-outlined:`science;1.75em` Advanced techniques
      :class-card: highlight-card
      :link-type: doc
      :link: advanced_techniques
      :shadow: lg

      Advanced patterns for reusing setup code and complex scenarios.

   .. grid-item-card:: :material-outlined:`language;1.75em` End-to-end testing
      :class-card: highlight-card
      :link-type: doc
      :link: e2e_testing
      :shadow: lg

      Test the complete install, package, launch, API, and browser lifecycle.

.. toctree::
   :maxdepth: 2
   :hidden:

   quick_start
   solution_api
   solution_ui
   product_instances
   other_fixtures
   advanced_techniques
   e2e_testing
