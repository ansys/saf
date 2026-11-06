.. _user_guide:

##########
User guide
##########

.. grid:: 4
  :gutter: 4
  :class-container: onboarding-cards

  .. grid-item-card:: :material-outlined:`create_new_folder;1.75em` :ref:`scaffold`
    :class-card: highlight-card
    :link-type: doc
    :link: scaffold
    :shadow: lg

    Create a new solution by instantiating the solution template in your working directory.

  .. grid-item-card:: :material-outlined:`download;1.75em` :ref:`ug-install`
    :class-card: highlight-card
    :link-type: doc
    :link: install
    :shadow: lg

    Install the solution development environment using the ``saf install`` command.

  .. grid-item-card:: :material-outlined:`play_arrow;1.75em` :ref:`ug-run-locally`
    :class-card: highlight-card
    :link-type: doc
    :link: run_locally/index
    :shadow: lg

    Run your solution locally using ``saf run`` or Docker Compose deployment options.

  .. grid-item-card:: :material-outlined:`folder_open;1.75em` :ref:`manage_projects`
    :class-card: highlight-card
    :link-type: doc
    :link: projects
    :shadow: lg

    Perform project management tasks like creating, sharing, upgrading, and deleting solution projects.

  .. grid-item-card:: :material-outlined:`bug_report;1.75em` :ref:`debug`
    :class-card: highlight-card
    :link-type: doc
    :link: debug/index
    :shadow: lg

    Explore techniques for debugging the backend, frontend, and telemetry issues in your solution.

  .. grid-item-card:: :material-outlined:`science;1.75em` :ref:`test`
    :class-card: highlight-card
    :link-type: doc
    :link: test/index
    :shadow: lg

    Test your solution using fixtures for backend API testing, frontend Dash callbacks, and product instances.

  .. grid-item-card:: :material-outlined:`add_circle;1.75em` :ref:`add_step`
    :class-card: highlight-card
    :link-type: doc
    :link: add_step
    :shadow: lg

    Add a new step to an existing solution using the ``saf add-step`` command.

  .. grid-item-card:: :material-outlined:`inventory;1.75em` :ref:`package`
    :class-card: highlight-card
    :link-type: doc
    :link: package/index
    :shadow: lg

    Package your solution as a distributable installer or archive for deployment.

  .. grid-item-card:: :material-outlined:`rocket_launch;1.75em` :ref:`deploy`
    :class-card: highlight-card
    :link-type: doc
    :link: deploy/index
    :shadow: lg

    Deploy solutions on desktop or on-premises infrastructure via Windows services, Docker Compose, or K3s.

  .. grid-item-card:: :material-outlined:`engineering;1.75em` :ref:`backend_development`
    :class-card: highlight-card
    :link-type: doc
    :link: backend/index
    :shadow: lg

    Define your workflow, steps, transaction methods, and manage files and folders.

  .. grid-item-card:: :material-outlined:`web;1.75em` :ref:`frontend_development`
    :class-card: highlight-card
    :link-type: doc
    :link: frontend/index
    :shadow: lg

    Build the user interface using the Dash framework and client-side interaction patterns.

  .. grid-item-card:: :material-outlined:`settings;1.75em` :ref:`environment_variables`
    :class-card: highlight-card
    :link-type: doc
    :link: environment_variables
    :shadow: lg

    Configure the SAF runtime using environment variables for SAF GLOW Engine, SAF, OTEL, and other components.

  .. grid-item-card:: :material-outlined:`dns;1.75em` :ref:`solution_servers`
    :class-card: highlight-card
    :link-type: doc
    :link: solution_servers
    :shadow: lg

    Learn about the servers in your solution stack and the roles they play in local development.

  .. grid-item-card:: :material-outlined:`code;1.75em` :ref:`script_solution`
    :class-card: highlight-card
    :link-type: doc
    :link: script
    :shadow: lg

    Use a Python script to control a SAF-based application and explore available APIs and configurations.

  .. grid-item-card:: :material-outlined:`apps;1.75em` :ref:`supported_software`
    :class-card: highlight-card
    :link-type: doc
    :link: supported_software
    :shadow: lg

    Review Ansys product and third-party tool integrations with version compatibility details.

  .. grid-item-card:: :material-outlined:`view_module;1.75em` :ref:`components_overview`
    :class-card: highlight-card
    :link-type: doc
    :link: components
    :shadow: lg

    Explore the SAF components, their roles, relationships, and installation via the
    ``ansys-saf-sdk`` meta-package.

  .. grid-item-card:: :material-outlined:`tips_and_updates;1.75em` :ref:`best_practices`
    :class-card: highlight-card
    :link-type: doc
    :link: best_practices/index
    :shadow: lg

    Follow recommended patterns and guidelines for building robust, maintainable SAF solutions.

  .. grid-item-card:: :material-outlined:`upgrade;1.75em` :ref:`migration_guide`
    :class-card: highlight-card
    :link-type: doc
    :link: migration/index
    :shadow: lg

    Access migration instructions for upgrading SAF solutions across major versions.

  .. grid-item-card:: :material-outlined:`help_outline;1.75em` :ref:`troubleshooting`
    :class-card: highlight-card
    :link-type: doc
    :link: troubleshooting/index
    :shadow: lg

    Diagnose and resolve installation, dependency, deployment, backend, and network issues.

.. toctree::
   :maxdepth: 2
   :hidden:

   scaffold
   install
   run_locally/index
   projects
   debug/index
   test/index
   add_step
   package/index
   deploy/index
   backend/index
   frontend/index
   environment_variables
   solution_servers
   script
   supported_software
   components
   best_practices/index
   migration/index
   troubleshooting/index
