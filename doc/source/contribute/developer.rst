.. _contribute_dev:

Contribute as a developer
#########################

Developers can contribute by adding features, fixing bugs, improving tests and documentation, reviewing code, and joining technical discussions to ensure project quality.

.. _fork_the_repository:

Fork the repository
===================

Forking the repository is the first step to contributing to the project. This
allows you to have your own copy of the project so you can make changes without
affecting the main project. Once you have made your changes, you can submit a
pull-request to the main project to have your changes reviewed and merged.

.. button-link:: https://github.com/ansys/saf/fork
    :color: primary
    :align: center

    :fa:`code-fork` Fork this project

.. note::

    If you are an Ansys employee, you can skip this step.

.. _clone_the_repository:

Clone the repository
====================

Make sure you `configure SSH`_ with your GitHub
account. This allows you to clone the repository without having to use tokens
or passwords. Also, make sure you have `git`_ installed in your machine.

Some paths in the repository exceed the default Windows path length limit.
Before cloning on Windows, enable long paths:

.. code-block:: text

    git config --global core.longpaths true

To clone the repository using SSH, run:

.. code-block:: bash

    git clone git@github.com:ansys/saf.git

.. note::

    If you are not an Ansys employee, you need to :ref:`fork the repository <fork_the_repository>` and
    replace ``ansys`` with your GitHub user name in the ``git clone``
    command.

.. _repository_layout:

Understand the repository layout
================================

The ``saf`` repository groups SAF packages in a single repository. The Python
packages registered in ``.moon/workspace.yml`` are managed as a uv workspace
rooted at the repository root. Each package keeps its own ``pyproject.toml``
and release lifecycle; dependency resolution is recorded in the root
``uv.lock``. Moon provides the common tasks for these packages. Run Moon
commands from the repository root, and use ``moon projects`` to list the
registered projects.

.. code-block:: text

    saf/
    |__ doc/             Centralized documentation
    |__ .moon/           Moon workspace and shared task definitions
    |__ packages/        All SAF packages
    |   |__ bdm-python-api/
    |   |__ bdm-python-shared-volume/
    |   |__ dash-super-components/
    |   |__ glow-engine/
    |   |__ saf-cli/
    |   |__ saf-desktop-installer/
    |   |__ saf-desktop-orchestrator/
    |   |__ saf-iam-oidc/
    |   |__ saf-product-configuration/
    |   |__ saf-product-manager/
    |   |__ saf-sdk/
    |   |__ saf-templates/
    |   |__ saf-testing/
    |__ pyproject.toml   Root uv workspace and documentation dependencies
    |__ uv.lock          Resolved dependencies for the workspace

You can leverage the Moon tasks defined in the root ``.moon`` directory to manage and interact with the SAF packages efficiently.

.. list-table::  Tools used for repository-level and package-level tasks
    :header-rows: 1
    :stub-columns: 1
    :widths: 50 30 20

    * - Work
        - Command
    * - Synchronize workspace dependencies
        - ``moon run root:uv-sync``
    * - Run root checks
        - ``moon run root:pre-commit``
    * - Run a package task (for example, tests)
        - ``moon run saf-testing:test``


.. _install_for_developers:

Set up a development environment
==================================

Installing a SAF package in development mode allows you to perform changes to
the code and see the changes reflected in your environment without having to
reinstall the package every time you make a change.

All SAF packages require Python 3.11 or a later version, up to but excluding

    moon run saf-testing:test

The task runs pytest with coverage enabled and writes terminal, XML, and HTML
coverage reports.

.. code-block:: text

    moon run saf-testing:test


    moon run saf-testing:pre-commit

Other package tasks include ``test``, ``build``, ``build-doc``, ``ruff``,
``pyright``, and ``bandit``. Replace ``saf-testing`` with the project name
shown by ``moon projects``.

.. _build_the_documentation_dev:

Build the documentation
=======================

For instructions on how to build the documentation, see
:ref:`build_the_documentation`.

.. _open_a_pull_request:

Open a pull-request
===================

Once your changes are ready, open a pull-request against the ``main`` branch.
The following rules are verified automatically:

- The title of the pull-request must follow the `Conventional Commits`_
  specification. For example, ``feat: add the solution export command``.
- The description of the pull-request must link at least one issue.

Labels are applied automatically, based on the title of the pull-request and on
the files you changed. The labels of the packages you changed determine which
style, build, and test jobs run.

.. _run_pipelines:

Run CI/CD pipelines
===================

SAF has a set of CI/CD pipelines that are executed automatically when certain
events are detected in the repository. Some of these events include opening a
pull-request, labelling a pull-request, and tagging a commit.

.. important::

    The CI/CD pipelines are protected. Only team members of the ``SAF
    developers team`` can run the pipelines. For non team members, an ``SAF
    developers team`` member must authorize the CI/CD run for every new commit
    or change. This prevents unauthorized or malicious code from being executed
    in the runners.
