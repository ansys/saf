.. _game_of_life_initialization:

Phase 1 — Initialization
########################

.. topic:: Objective

  In this module, you'll cover the following topics:

  - :material-outlined:`terminal;1.25em;saf-objective-icon` Check that the ``ansys-saf-cli`` toolchain is
    available.
  - :material-outlined:`create_new_folder;1.25em;saf-objective-icon` Create the solution from the
    official SAF template with ``saf new``.
  - :material-outlined:`account_tree;1.25em;saf-objective-icon` Discover the project layout that
    ``ansys-saf-cli`` generates, and the backend/frontend split it enforces.
  - :material-outlined:`inventory_2;1.25em;saf-objective-icon` Declare the dependencies the tutorial
    needs and install them with ``saf install``.
  - :material-outlined:`play_circle;1.25em;saf-objective-icon` Run the empty application with
    ``saf run --debug`` to confirm everything is wired correctly.

  At the end of this phase, you have a working empty SAF application.

Check your toolbox
==================

A single command-line tool drives the whole SAF developer experience: ``ansys-saf-cli``.

SAF CLI is either installed centrally in your base Python interpreter, or in a dedicated
virtual environment. How you check that it is available depends on which of the two you have.

.. practice::

    Open a terminal and confirm that the CLI is available.

    .. tab-set::

        .. tab-item:: Central installation

            The ``saf`` command is available system-wide, so run it directly:

            .. code-block:: bash

                saf --version

        .. tab-item:: Virtual environment

            Activate the virtual environment that holds SAF CLI first:

            .. tab-set::

                .. tab-item:: Windows PowerShell

                    .. code-block:: powershell

                        .cli\Scripts\Activate.ps1
                        saf --version

                .. tab-item:: Linux/macOS

                    .. code-block:: bash

                        source .cli/bin/activate
                        saf --version

            Remember to activate this environment in every new terminal you open during the
            tutorial.

    If the command prints a version, you are ready to continue.

.. seealso::

    If SAF CLI is not installed yet, see :ref:`prerequisites_saf_cli` in the :ref:`prerequisites` section.

Create the solution from the template
=====================================

You never start a SAF solution from a blank folder. The ``saf new`` command instantiates a project template that already contains the structure and boilerplate code you need to get started.

.. practice::

    #. From your preferred working directory, run:

       .. code-block:: bash

           saf new

    #. Answer the prompts as follows. Press :kbd:`Enter` to accept the default for anything not
       listed here.

       .. list-table::
          :header-rows: 1
          :stub-columns: 1
          :widths: 25 25 50

          * - Prompt
            - Value to enter
            - What it drives
          * - Solution name
            - ``game-of-life``
            - The folder name and the Python package name (``game_of_life``).
          * - Solution display name
            - ``Game of Life``
            - The title shown in the application window and the installer.
          * - UI framework
            - ``dash`` *(default)*
            - Which frontend scaffolding is generated.
          * - Solution namespace
            - ``saf.solutions`` *(default)*
            - The import prefix, that is ``saf.solutions.game_of_life``.

    #. Move into the generated folder:

       .. code-block:: bash

           cd game-of-life

.. note::

  Use a lowercase, hyphen-separated name such as ``game-of-life``. SAF converts it to a valid
  Python identifier (``game_of_life``) for the package name, so this form is recommended for the
  tutorial.

What the template generates
===========================

Take a minute to look around. Almost everything you will touch in this tutorial lives under
``src/saf/solutions/game_of_life/``:

.. code-block:: text

    game-of-life/
    ├── pyproject.toml                 # Dependencies and packaging metadata
    ├── poetry.lock                    # Exact resolved versions of every dependency
    ├── tests/                         # Pytest suite scaffolding
    └── src/saf/solutions/game_of_life/
        ├── solution/
        │   ├── definition.py          # The solution definition — the workflow contract
        │   ├── first_step.py          # Sample step (backend)
        │   ├── second_step.py         # Sample step (backend)
        │   └── scripts/               # Source code shipped to job submission execution nodes
        └── ui/
            ├── app.py                 # Dash app instance (auto-generated, leave it alone)
            ├── assets/                # CSS, icons, images
            └── pages/
                ├── about_page.py      # Landing page
                ├── first_page.py      # Sample step (frontend)
                ├── second_page.py     # Sample step (frontend)
                └── page.py            # Page router

Three ideas are baked into this layout, and they hold for every SAF solution:

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 15 85

   * - Folder
     - Role
   * - ``solution/``
     - The **backend**. It owns the workflow definition and the step models — the state of the
       application and the methods that compute it.
   * - ``ui/``
     - The **frontend**. One page per step, plus a router and shared assets. It never computes
       anything; it only reads and writes backend state.
   * - ``tests/``
     - The test suite. SAF solutions are ordinary Python packages, so ``pytest`` works exactly
       as you expect.

.. tip::

    The ``solution/`` and ``ui/`` split is not cosmetic. The backend can run in a completely
    different process, or on a different machine, from the frontend. Keeping them apart from
    day one is what makes a SAF solution deployable on a laptop, in Docker, or on an on-prem
    cluster without changing a line of code.

The two files at the root of the folder drive the packaging and the environment. A SAF solution
is a `Poetry <https://python-poetry.org/docs/>`_ project, so they follow the standard Poetry
contract.

Poetry is a **dependency manager**: the tool that decides which third-party packages end up in
your environment, and in which version. Given the list of packages your project needs, it
resolves the whole graph, including the dependencies of your dependencies, into a single set
of versions that are mutually compatible, installs them into a dedicated virtual environment,
and records the result so the exact same set can be reproduced later. It also handles the
packaging side: building the wheel that is shipped in the final installer. The ``saf install``,
``saf execute`` and ``saf build`` commands all delegate to Poetry under the hood.

That contract is split across two files:

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 20 80

   * - File
     - Role
   * - ``pyproject.toml``
     - The **manifest**, and the file you edit. It declares the solution metadata (name, version,
       display name), the packaging configuration, and the dependencies with *version
       constraints* such as ``numpy = "^2.0"``. It says what the solution needs, not which exact
       build it gets.
   * - ``poetry.lock``
     - The **resolution**, and a generated file you never edit by hand. It pins the exact version
       and hash of every direct and transitive dependency that satisfies the constraints in
       ``pyproject.toml``. It guarantees that your machine, your colleague's machine, the CI
       pipeline, and the final installer all get a byte-identical environment.

The two files must stay consistent. The ``saf install`` command installs from ``poetry.lock``, and Poetry refuses to do so if the lock file no longer matches the manifest. This is why every dependency change goes through ``poetry lock``, as shown in
:ref:`Declare the dependencies <game_of_life_declare_dependencies>`.

.. important::

    Commit both files to version control. ``pyproject.toml`` alone is not enough to reproduce an
    environment; without ``poetry.lock``, a fresh install can silently pick up a newer patch
    release of a transitive dependency and break the solution.

.. seealso::

    - The official `Poetry documentation <https://python-poetry.org/docs/>`_.
    - `Dependency specification <https://python-poetry.org/docs/dependency-specification/>`_ for
      the syntax of version constraints such as ``^2.0``.
    - :ref:`user_guide_install_manage_dependencies` in the user guide for the SAF-specific
      dependency workflow.

Install the solution
====================

A SAF solution runs inside its own virtual environment. ``saf install`` creates it and resolves
every dependency declared in ``pyproject.toml``.

.. practice::

    From the root of the ``game-of-life`` folder, run:

    .. code-block:: bash

        saf install -f

    The ``-f`` flag forces a fresh environment. Use it whenever the dependency resolution needs
    to start from scratch; plain ``saf install`` is enough the rest of the time.

.. note::

    Never activate that environment by hand. The ``saf run`` and ``saf execute`` commands do it for you, which is why every command in this tutorial is prefixed with ``saf``.

.. _game_of_life_declare_dependencies:

Declare the dependencies
========================

The template ships with the SAF runtime only. The Game of Life engine you will add in
:ref:`phase 2 <game_of_life_business_logic>` relies on ``numpy``, so declare it now.

Adding a dependency is always a three-step move: edit ``pyproject.toml``, refresh
``poetry.lock``, and reinstall. Skipping the lock refresh makes ``saf install`` fail with an
outdated lock file error, because Poetry refuses to install from a lock file that no longer
matches the manifest.

.. practice::

    #. Open ``pyproject.toml`` at the root of the ``game-of-life`` folder and add ``numpy`` to
       the dependencies:

       .. code-block:: toml

           [tool.poetry.dependencies]
           # ... existing entries ...
           numpy = "^2.0"

    #. Refresh the lock file so it matches the manifest again. Run ``poetry lock`` inside the
       solution environment, either through SAF CLI or by activating the environment yourself:

       .. tab-set::

           .. tab-item:: With SAF CLI

               .. code-block:: bash

                   saf execute "poetry lock"

           .. tab-item:: With the activated environment

               .. tab-set::

                   .. tab-item:: Windows PowerShell

                       .. code-block:: powershell

                           .venv\Scripts\Activate.ps1
                           poetry lock

                   .. tab-item:: Linux/macOS

                       .. code-block:: bash

                           source .venv/bin/activate
                           poetry lock

    #. Install the new dependency:

       .. code-block:: bash

           saf install

.. tip::

    The ``saf execute`` command runs any command inside the solution virtual environment without you having to activate it. Use it for Poetry, ``pytest``, ``sphinx-build``, or any other tool that must see the solution dependencies.

Run the empty application
=========================

Before writing any code, confirm the scaffolding works end to end.

.. practice::

    Start the solution:

    .. code-block:: bash

        saf run --debug

    A desktop window opens with the solution display name in the title bar. Create a new
    project, then click through **First step** and **Second step** in the navigation tree on
    the left. They are the sample steps the template generated. Each one adds two numbers and
    shows the result.

    Close the window (or press :kbd:`Ctrl+C` in the terminal) when you are done.

If you saw the two sample steps, your toolchain is healthy and you are ready to start building.

.. important::

    **Always develop with** ``--debug``. It enables the Dash dev tools, which surface frontend
    and callback errors directly in the UI instead of letting them fail silently. Without it a
    broken callback simply does nothing and you are left guessing. Every ``saf run`` in this
    tutorial therefore uses ``--debug``; drop the flag only when you serve the solution for
    real users.

.. tip::

    The ``saf run`` command has a few other variants worth knowing:

    - ``saf run --browser`` opens the app in your default web browser instead of a desktop
      window.
    - ``saf run --no-ui`` starts the backend only and exposes the auto-generated REST API.
      Handy to test transactions without a frontend.

    The flags combine, so ``saf run --debug --browser`` is a common development setup.

Key takeaways
=============

.. important::

    - The ``saf new`` command instantiates a solution from the official template. Never start from an empty
      folder.
    - A solution is split into ``solution/`` (backend: definition and step models) and ``ui/``
      (frontend: one page per step). The split is what makes the solution deployable anywhere.
    - Dependencies are declared in ``pyproject.toml`` and installed into a dedicated virtual
      environment with ``saf install``. After editing ``pyproject.toml``, always refresh
      ``poetry.lock`` with ``saf execute "poetry lock"`` before reinstalling, otherwise
      ``saf install`` fails on an outdated lock file.
    - The ``saf run --debug`` command starts the application with the Dash dev tools enabled — the default
      way to run a solution while developing. ``--browser`` and ``--no-ui`` change how it is
      served.
    - Run the freshly scaffolded app **before** writing code. It takes thirty seconds and rules
      out an entire class of environment problems.
