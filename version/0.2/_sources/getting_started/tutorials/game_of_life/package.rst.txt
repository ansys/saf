.. _game_of_life_package:

Phase 5 — Package
#################

.. topic:: Objective

  In this module, you'll cover the following topics:

  - :material-outlined:`inventory_2;1.25em;saf-objective-icon` Understand why a solution that runs
    from source is not yet something you can hand over to an end user.
  - :material-outlined:`build;1.25em;saf-objective-icon` Turn the solution into a **standalone
    desktop installer** with ``saf build``, on Windows or on Linux.
  - :material-outlined:`cloud_off;1.25em;saf-objective-icon` Choose between an **online** and an
    **offline** installer depending on how your users' machines are connected.
  - :material-outlined:`terminal;1.25em;saf-objective-icon` Tell a **development** build apart from
    a **release** build, and know which one to ship.
  - :material-outlined:`fact_check;1.25em;saf-objective-icon` Smoke-test the generated installer on
    a clean machine before distributing it.

  At the end of this phase, the ``game-of-life`` solution is a single executable that a
  colleague can run to install and start the app.

Why package the solution?
=========================

Up to this point you have been running the solution from source with ``saf run --debug``. That
is perfect for development, but it assumes the target machine has:

- a compatible Python interpreter,
- the SAF CLI installed,
- network access to every dependency,
- and a copy of your source tree.

Real end users have none of that.

.. key-concept:: ``saf build``

    The ``saf build`` command is a one-shot command that packages a solution into a single
    executable installer. The installer includes code, Python interpreter and
    every dependency. The end user runs the installer, clicks through a
    Next / Next / Finish wizard, and lands on a working desktop app.

    It is the hand-off point between *your* development environment and *their* machine:
    everything the solution needs at runtime has to be inside that artifact.

.. important::

    The ``saf build`` command is **platform-specific**: it produces an installer for the operating system
    of the machine it runs on, and there is no cross-compilation.

    - When run on Windows, it produces a Windows ``.exe`` installer.
    - When run on Linux, it produces a Linux executable.

    To ship the solution on both platforms, run the build twice — once on a Windows machine,
    once on a Linux machine. The following commands are identical in either case.

Prerequisites
=============

The build command needs an installed solution to package.

.. practice::

    If you skipped ``saf install`` earlier, run it now from the root of the ``game-of-life``
    folder:

    .. code-block:: bash

        saf install -f

    The ``-f`` flag forces a clean re-install of the virtual environment — recommended before a
    release build to make sure the dependency graph is fresh.

Build the installer
===================

Before building, choose the installer's network model and build mode: **online vs offline installer** and
**development vs release build**.

Online vs offline installer
---------------------------

.. key-concept:: Online vs offline installer

    - **Online installer (default)**: small executable that downloads dependencies from the
      internet at install time. Perfect for internal distribution to machines that have
      network access.
    - **Offline installer** (``--offline-package``): larger executable that embeds every wheel
      it needs and installs without any network call. Choose this when your users sit behind
      an air-gapped firewall or you need a truly self-contained artifact.

    The choice is about the *target* machine, not yours: an offline installer costs you size
    and build time, and buys your users independence from the network.

Development vs release build
----------------------------

.. best-practice:: Development vs release build

    - **Development build** (``--display-console-window``): keeps a console window open next
      to the app so you can see logs and tracebacks. Use it while you are still ironing out
      bugs.
    - **Release build** (default, no flag): hides the console window. Use it for anything you
      send to end users.

    The console window is the packaged equivalent of the ``--debug`` flag you used with
    ``saf run``: without it, a failing installed solution gives you nothing to work with.

.. practice::

    From the root of the ``game-of-life`` folder, build a **development installer** first — the
    console window makes any post-install issue trivial to diagnose:

    .. code-block:: bash

        saf build --display-console-window

    The build takes a few minutes. When it succeeds, ``saf-cli`` prints the absolute path to the
    generated installer. It sits under the ``dist/`` directory of your solution, and its
    extension depends on the platform you built on: ``.exe`` on Windows, a plain executable on
    Linux.

    Then, once you are happy with the result, build the **release installer** you will ship:

    .. code-block:: bash

        saf build

    Or, for a fully self-contained artifact:

    .. code-block:: bash

        saf build --offline-package

Test the installer
==================

.. best-practice:: Test on a clean machine

    Your development workstation has Python, the SAF CLI and a pile of globally installed
    packages. An installer tested only there proves nothing: it may be silently relying on
    something that exists on your machine and nowhere else. Testing on a clean machine, for example a
    virtual machine or a second workstation, is the only reliable way to catch that class of
    bug.

Never ship an installer you have not smoke-tested yourself.

.. practice::

    #. Locate the generated installer printed at the end of the ``saf build`` command.

    #. Copy it to a **clean** location — ideally a virtual machine or a second workstation that
       does not have your development environment. This is the only way to catch missing
       dependencies that happen to be pre-installed on your dev machine.

    #. Run the installer and follow the wizard.

       .. tab-set::

          .. tab-item:: Windows

             Double-click the ``.exe``. The default install location is:

             .. code-block:: text

                 C:\Program Files\ANSYS Inc\SAF Solutions\Game of Life Solution\1\

             It might be necessary to run the ``.exe`` as an administrator.

          .. tab-item:: Linux

             Make the file executable and run it from a terminal:

             .. code-block:: bash

                 chmod +x <installer>
                 ./<installer>

             The default install location depends on whether you run it as a regular user or
             with ``sudo``:

             .. code-block:: text

                 ~/.local/share/ansys_inc/saf_solutions/Game of Life Solution/1/
                 /opt/ansys_inc/saf_solutions/Game of Life Solution/1/

    #. Launch the newly-installed solution — from the Start menu or the desktop shortcut on
       Windows, and from the desktop entry or the executable in the installation directory on
       Linux.

    #. Reproduce the full end-to-end flow from :ref:`phase 4 <game_of_life_frontend>`:

       - Pick a couple of patterns and verify the heatmap redraws.
       - Move the grid-size slider and verify the heatmap redraws.
       - Click :guilabel:`Start simulation`, wait for the run to complete, and verify the completion
         notification.

    If any of that fails, the ``--display-console-window`` build you produced first will show
    the traceback. Fix the issue, rebuild, retest.

Where to go from here
=====================

Congratulations — you now have a fully functional, distributable SAF solution. To continue expanding your SAF fluency, explorethese three next steps:

- :ref:`installer` — the full reference for ``saf build``, including options for encrypting or
  obfuscating your source code, excluding the Python interpreter, or bundling as a directory
  when the installer exceeds the 4 GB single-file limit.
- :ref:`user_guide` — dive deeper into the SAF concepts you touched in this tutorial (product
  instances, BDM storage, HPS job submission, testing, deployment).
- The examples gallery in ``examples/src/saf/solutions/examples/`` on the
  `SAF examples repository <https://github.com/ansys/saf>`_ — a growing library of small,
  focused solutions that showcase one SAF feature at a time.

Key takeaways
=============

.. important::

    - ``saf build <solution-name>`` produces a **standalone desktop installer** that bundles
      the solution, its dependencies, and a Python interpreter.
    - The command is **platform-specific**: it targets the OS it runs on. Build on Windows for
      a Windows installer, on Linux for a Linux one — there is no cross-compilation.
    - The command only works for **Dash-based** solutions.
    - Use ``--offline-package`` when the target machine is offline or air-gapped.
    - Use ``--display-console-window`` during development to see logs and tracebacks; drop the
      flag for release builds so end users don't see a stray console window.
    - Always test the generated installer on a **clean machine** before distributing it — that
      is the only reliable way to catch missing dependencies that happen to be installed
      globally on your development workstation.
    - See :ref:`installer` for advanced options (encryption, obfuscation, custom entry points,
      excluding Python, and more).