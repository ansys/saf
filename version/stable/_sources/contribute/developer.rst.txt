.. _contribute_dev:

Contribute as a developer
#########################

Developers can contribute by adding features, fixing bugs, improving tests and documentation, reviewing code, and joining technical discussions to ensure project quality.

.. _choose_your_workflow:

Choose your workflow
====================

How you get the code and submit changes depends on your permissions on the
``ansys/saf`` repository.

By default, all members of the
`Ansys GitHub organization <https://github.com/ansys>`__ (``ansys``) have
write access to ``ansys/saf``.

.. important::

    - **Clone the repository** if you are a member of the
      `Ansys GitHub organization <https://github.com/ansys>`__. You clone
      ``ansys/saf`` directly, push branches to it, and open a pull-request
      from those branches.
    - **Fork the repository** if you are **not** a member of the
      `Ansys GitHub organization <https://github.com/ansys>`__. You cannot
      push branches to ``ansys/saf``, so you develop on your own fork and open
      a pull-request from it.

    If a ``git push`` to ``ansys/saf`` is rejected with a permission error,
    your access has been restricted: switch to the fork workflow.

.. list-table::
    :header-rows: 1
    :widths: 30 35 35

    * -
      - `Ansys GitHub organization <https://github.com/ansys>`__ member
      - Not a member
    * - Get the code
      - :ref:`Clone <clone_the_repository>` ``ansys/saf``
      - :ref:`Fork <fork_the_repository>` ``ansys/saf``, then clone your fork
    * - Push branches to
      - ``ansys/saf`` (``origin``)
      - Your fork (``origin``)
    * - Pull-request source
      - Branch in ``ansys/saf``
      - Branch in your fork
    * - CI/CD pipelines
      - Run for ``SAF developers team`` members. Otherwise, a team member must
        authorize the run for every new commit.
      - Must be authorized by a ``SAF developers team`` member for every new
        commit

Both workflows share the same prerequisites.

Prerequisites
-------------

- Install `git`_ on your machine.
- Set up SSH access by following the instructions to `configure SSH`_ with
  your GitHub account. This allows you to access the
  repository without tokens or passwords.
- On Windows, enable long paths. Some paths in the repository exceed the
  default Windows path length limit.

  .. code-block:: text

      git config --global core.longpaths true

.. _clone_the_repository:

Clone the repository (Ansys GitHub organization members)
========================================================

Use this workflow if you are a member of the
`Ansys GitHub organization <https://github.com/ansys>`__, which grants you
write access to ``ansys/saf`` by default. You work
directly on ``ansys/saf`` without creating a fork.

#. Clone the repository using SSH:

   .. code-block:: bash

       git clone git@github.com:ansys/saf.git
       cd saf

#. Create a branch from an up-to-date ``main``:

   .. code-block:: bash

       git fetch origin
       git checkout -b <my-branch> origin/main

#. Make your changes and commit them. Follow the `Conventional Commits`_
   specification for commit messages.

#. Push the branch to ``ansys/saf``:

   .. code-block:: bash

       git push --set-upstream origin <my-branch>

#. :ref:`Open a pull-request <open_a_pull_request_as_a_member>` from your
   branch against ``main``.

.. _fork_the_repository:

Fork the repository (non-members of the Ansys GitHub organization)
==================================================================

Use this workflow if you are **not** a member of the
`Ansys GitHub organization <https://github.com/ansys>`__, and therefore do not
have write access to ``ansys/saf``.
A fork is your own copy of the project, where you can make changes without
affecting the main project. When your changes are ready, you submit a
pull-request from your fork to ``ansys/saf`` to have them reviewed and merged.

#. Fork the repository to your own GitHub account:

   .. button-link:: https://github.com/ansys/saf/fork
       :color: primary
       :align: center

       :fa:`code-fork` Fork this project

#. Clone your fork, replacing ``<your-user-name>`` with your GitHub user name:

   .. code-block:: bash

       git clone git@github.com:<your-user-name>/saf.git
       cd saf

#. Add the ``ansys/saf`` repository as the ``upstream`` remote, so that you can
   keep your fork up to date:

   .. code-block:: bash

       git remote add upstream git@github.com:ansys/saf.git

#. Create a branch from an up-to-date ``upstream/main``:

   .. code-block:: bash

       git fetch upstream
       git checkout -b <my-branch> upstream/main

#. Make your changes and commit them. Follow the `Conventional Commits`_
   specification for commit messages.

#. Push the branch to your fork:

   .. code-block:: bash

       git push --set-upstream origin <my-branch>

#. :ref:`Open a pull-request from your fork <open_a_pull_request_from_a_fork>`
   against the ``main`` branch of ``ansys/saf``.

.. tip::

    To keep your fork up to date, fetch ``upstream`` regularly and rebase or
    merge ``upstream/main`` into your branch.

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
    |   |__ saf-projects-dashboard/
    |   |__ saf-sdk/
    |   |__ saf-templates/
    |   |__ saf-testing/
    |__ pyproject.toml   Root uv workspace and documentation dependencies
    |__ uv.lock          Resolved dependencies for the workspace

You can leverage the Moon tasks defined in the root ``.moon`` directory to manage and interact with the SAF packages efficiently.

.. list-table:: Moon tasks for repository-level and package-level work
    :header-rows: 1
    :widths: 50 50

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
Python 4.

Set up the workspace
--------------------

Install the Moon CLI. Moon uses the root ``uv.lock`` and creates the shared ``.venv`` at the
repository root. Package tasks select the relevant workspace member and install
its extras as needed. Set ``UV_PYTHON`` and ``MOON_PYTHON_VERSION`` to the same
Python version before running package tasks.

.. _run_tests:

Run the tests
=============

Tests are declared in each package's ``tests`` directory. From the repository
root, run the package's Moon task. For example:

.. code-block:: text

  moon run saf-testing:test

The task runs pytest with coverage enabled and writes terminal, XML, and HTML
coverage reports.

.. note::

  Some packages, such as ``glow-engine``, declare test sessions that require
  additional services or specific markers. The test sessions run by the
  CI/CD pipelines are declared in the
  ``.github/workflows/tests_groups_definitions`` directory. Use them as a
  reference to reproduce a given test session locally.

.. _run_code_style_checks:

Run the code style checks
=========================

Code style is enforced with ``pre-commit``. Run root checks from the repository
root:

.. code-block:: text

  moon run root:pre-commit

To run a package's checks, use its ``pre-commit`` task. This task also runs the
package's Ruff, Pyright, and Bandit checks. For example:

.. code-block:: text

  moon run saf-testing:pre-commit

Other package tasks include ``test``, ``build``, ``build-doc``, ``ruff``,
``pyright``, and ``bandit``. Use ``moon projects`` to find registered project
names.

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

.. _open_a_pull_request_as_a_member:

Open a pull-request as an organization member
---------------------------------------------

#. In GitHub, open a pull-request with:

   - **base repository**: ``ansys/saf``, **base** branch: ``main``.
   - **head repository**: ``ansys/saf``, **compare** branch: ``<my-branch>``.

   Make sure the title and description follow the rules listed above.

.. _open_a_pull_request_from_a_fork:

Open a pull-request from a fork
-------------------------------

.. important::

    If you are not a member of the
    `Ansys GitHub organization <https://github.com/ansys>`__, you must open your
    pull-request **from your fork** against the ``main`` branch of
    ``ansys/saf``. Pull-requests from branches pushed directly to ``ansys/saf``
    are only possible for members of the organization.

#. In GitHub, open a pull-request with:

   - **base repository**: ``ansys/saf``, **base** branch: ``main``.
   - **head repository**: your fork, **compare** branch: ``<my-branch>``.

   Make sure the title and description follow the rules listed above.

.. note::

    The :ref:`CI/CD pipelines <run_pipelines>` do not run automatically on
    pull-requests from forks. A member of the ``SAF developers team`` must
    authorize the run for every new commit.

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
