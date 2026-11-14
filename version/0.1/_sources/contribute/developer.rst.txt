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

The ``saf`` repository groups all SAF packages in a single repository. Every
package located under the ``packages`` directory is independent: it has its own
``pyproject.toml``, its own ``poetry.lock``, its own ``.pre-commit-config.yaml``,
and its own release lifecycle.

.. code-block:: text

    saf/
    |-- architecture/    Design documents of the repository
    |-- doc/             Centralized documentation
    |-- packages/        All SAF packages
    |   |-- bdm-python-api/
    |   |-- bdm-python-shared-volume/
    |   |-- dash-super-components/
    |   |-- glow-engine/
    |   |-- saf-cli/
    |   |-- saf-desktop-installer/
    |   |-- saf-desktop-orchestrator/
    |   |-- saf-iam-oidc/
    |   |-- saf-product-configuration/
    |   |-- saf-product-manager/
    |   |-- saf-templates/
    |   |-- saf-testing/
    |-- pyproject.toml   Root project, documentation dependencies only

Two different tools are used, depending on where you work:

.. list-table::
    :header-rows: 1
    :widths: 34 33 33

    * - Task
      - Working directory
      - Tool
    * - Centralized documentation and repository code style checks
      - Repository root
      - ``uv``
    * - Package development, tests, and package code style checks
      - ``packages/<package-name>``
      - Poetry


.. _install_for_developers:

Set up a development environment
==================================

Installing a SAF package in development mode allows you to perform changes to
the code and see the changes reflected in your environment without having to
reinstall the package every time you make a change.

All SAF packages require Python 3.11 or a later version, up to but excluding
Python 4.


Install Poetry
--------------

SAF packages are managed with Poetry 2.3.2.

.. important::

    Install Poetry outside of the virtual environment of the package you work
    on. When Poetry shares an environment with the project dependencies, it
    resolves and upgrades its own dependencies together with the project ones,
    which leads to broken environments. Use a tool that installs Poetry in its
    own isolated environment instead.

.. tab-set::

    .. tab-item:: pipx

        .. code-block:: text

            python -m pip install --user pipx
            python -m pipx ensurepath
            pipx install poetry==2.3.2

    .. tab-item:: uv

        .. code-block:: text

            python -m pip install --user uv
            uv tool install poetry==2.3.2

    .. tab-item:: Official installer

        .. tab-set::

            .. tab-item:: Windows

                .. code-block:: text

                    (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py - --version 2.3.2

            .. tab-item:: macOS/Linux/UNIX

                .. code-block:: text

                    curl -sSL https://install.python-poetry.org | python3 - --version 2.3.2

Verify the installation by running:

.. code-block:: text

    poetry --version

Then, configure Poetry to create the virtual environment inside the package
directory. This keeps the environment next to the sources and makes it easier
for editors to detect it:

.. code-block:: text

    poetry config virtualenvs.in-project true


Install a package in development mode
----------------------------------------

Start by navigating to the package you want to work on. For example, to work on
the SAF CLI, run:

.. code-block:: text

    cd packages/saf-cli

Then, install the package in development mode, together with the dependencies
required to run the tests and to build the documentation:

.. code-block:: text

    poetry install --with tests,doc

Poetry creates the ``.venv`` directory inside the package directory, installs
the package in editable mode, and installs its dependencies.

.. note::

    Some packages declare optional extras. To install them all, append
    ``--all-extras`` to the previous command. This is what the CI/CD pipelines
    do.

Finally, activate the environment by running:

.. tab-set::

    .. tab-item:: Windows

        .. tab-set::

            .. tab-item:: CMD

                .. code-block:: text

                    .venv\Scripts\activate.bat

            .. tab-item:: PowerShell

                .. code-block:: text

                    .venv\Scripts\Activate.ps1

    .. tab-item:: macOS/Linux/UNIX

        .. code-block:: text

            source .venv/bin/activate

Activating the environment is optional. If you prefer not to activate it,
prefix every command with ``poetry run``.

.. _run_tests:

Run the tests
=============

Tests are declared in the ``tests`` directory of each package and are run with
pytest. From the directory of the package you work on, run:

.. code-block:: text

    poetry run pytest

To compute the coverage ratio and generate a report, run:

.. code-block:: text

    poetry run pytest --cov=ansys --cov-report=term

.. note::

    Some packages, such as ``glow-engine``, declare test sessions that require
    additional services or specific markers. The test sessions run by the
    CI/CD pipelines are declared in the
    ``.github/workflows/tests_groups_definitions`` directory. Use them as a
    reference to reproduce a given test session locally.

.. _run_code_style_checks:

Run the code style checks
=========================

Code style is enforced with ``pre-commit``. There are two levels of
configuration: the root one, which applies to the whole repository, and one per
package.

To run the root checks, from the repository root, run:

.. code-block:: text

    uv venv .venv --python 3.12
    uv pip install pre-commit==4.6.0
    uv run pre-commit run --all-files

Not every package declares ``pre-commit``. When it does, the dependency group
that contains it depends on the package:

.. list-table::
    :header-rows: 1
    :widths: 20 80

    * - Group
      - Packages
    * - ``style``
      - ``dash-super-components``, ``glow-engine``, ``saf-testing``
    * - ``dev``
      - ``saf-cli``, ``saf-desktop-orchestrator``,
        ``saf-product-configuration``, ``saf-product-manager``
    * - None
      - ``bdm-python-api``, ``bdm-python-shared-volume``,
        ``saf-desktop-installer``, ``saf-iam-oidc``, ``saf-templates``

To run the checks of a package that declares ``pre-commit``, from the directory
of that package, run:

.. code-block:: text

    poetry install --with tests,doc,style
    poetry run pre-commit run --all-files

Replace ``style`` with ``dev`` for the packages that declare ``pre-commit`` in
the ``dev`` group.

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
