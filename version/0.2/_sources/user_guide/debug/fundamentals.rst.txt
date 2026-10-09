.. _debug_fundamentals:

Debugging fundamentals
########################

SAF solutions support remote debugging using the ``debugpy`` package, which allows you to attach the
VS Code debugger to running solution processes. This section explains how the debugging mechanism works,
what you need to set up, and how to configure VS Code depending on whether you work with a single solution
or multiple solutions.


How SAF debugging works
========================

A SAF solution runs as two separate processes:

- **Solution API** (backend): Executes Python transaction methods.
- **Solution UI** (frontend): Runs the Dash application and callbacks.

When you start a solution with debugging enabled, each process opens a ``debugpy`` listener on a dedicated
port. The VS Code debugger then "attaches" to these already-running processes to enable breakpoint
debugging, variable inspection, and step-through execution.

.. list-table:: Debug ports
   :header-rows: 1

   * - Process
     - Default port
     - Purpose
   * - Solution API (backend)
     - 5724
     - Debug transaction methods
   * - Solution UI (frontend)
     - 5725
     - Debug Dash callbacks

The attachment model is **remote attach**: you first start the solution, then connect the debugger to the
running process. This is different from "launch" debugging where VS Code starts the process itself.



.. _debug_prerequisites:

Prerequisites
=============

Before setting up debugging, ensure you have:

* Installed the `Python extension <https://marketplace.visualstudio.com/items?itemName=ms-python.python>`_ in VS Code

* Installed the `Python Debugger extension <https://marketplace.visualstudio.com/items?itemName=ms-python.debugpy>`_ (``ms-python.debugpy``) in VS Code

* Installed and configured the SAF CLI
* Created a SAF-based solution using ``saf new``

.. note::
   When you scaffold a solution with ``saf new``, a ``.vscode/launch.json`` file is created automatically
   at the solution root. This file contains the debug configurations required to attach to the backend and
   frontend processes.


Debugging scenarios
====================

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 20 35 45

   * - Scenario
     - VS Code setup
     - Key requirement
   * - Single solution
     - | Open the solution folder directly
       | (``code my-solution``)
     - ``.vscode/launch.json`` must be at the VS Code root
   * - Multiple solutions
     - Use a ``.code-workspace`` file with each solution as a folder entry
     - Each solution folder retains its own ``.vscode/launch.json``


.. _debug_single_solution:

Single-solution debugging
==========================

This is the standard approach when you work on one solution at a time.

.. important::

   For single-solution debugging to work, the solution folder **must** be the root folder opened in
   VS Code. The ``.vscode/launch.json`` file must be located at the VS Code workspace root. If you open
   a parent directory that contains the solution as a subfolder, VS Code cannot resolve the debug
   configuration and the debugger does not attach.

   .. code-block:: text

      my-solution/              <-- Open THIS folder in VS Code
      ├── .vscode/
      │   └── launch.json      <-- Must be at the VS Code root
      ├── src/
      │   └── ansys/
      │       └── solutions/
      │           └── ...
      └── pyproject.toml


#. Open the solution folder directly in VS Code:

   .. code-block:: bash

      cd path/to/my-solution
      code .

   or equivalently:

   .. code-block:: bash

      code path/to/my-solution

#. Verify the ``.vscode/launch.json`` file exists at the solution root with the following content:

   .. code-block:: json

      {
        "version": "0.2.0",
        "configurations": [
          {
            "name": "Python: Remote Attach",
            "type": "python",
            "request": "attach",
            "connect": {
              "host": "localhost",
              "port": 5724
            },
            "justMyCode": false
          },
          {
            "name": "Python: Remote Attach Dash",
            "type": "python",
            "request": "attach",
            "connect": {
              "host": "localhost",
              "port": 5725
            },
            "justMyCode": false
          }
        ]
      }

#. If the ``.vscode/launch.json`` file is missing, create it manually.


.. _debug_multi_solution:

Multi-solution debugging
=========================

When you work with multiple solutions simultaneously, opening a parent directory in VS Code causes
the debugger to fail because VS Code cannot determine which ``.vscode/launch.json`` to use.

Consider this directory structure:

.. code-block:: text

   workspace-root/               <-- Do NOT open this in VS Code
   ├── solution-a/
   │   └── .vscode/
   │       └── launch.json
   ├── solution-b/
   │   └── .vscode/
   │       └── launch.json
   └── solution-c/
       └── .vscode/
           └── launch.json

.. important::

   If you open ``workspace-root`` in VS Code and press :kbd:`F5`, VS Code does not know which
   ``launch.json`` to use. The debugger either fails or picks an arbitrary configuration.


A `multi-root workspace <https://code.visualstudio.com/docs/editing/workspaces/multi-root-workspaces>`_
allows VS Code to treat each solution folder as an independent root, preserving the ``.vscode/launch.json``
resolution for each one.

#. Create a workspace file (for example, ``my-solutions.code-workspace``) in the parent directory:

   .. code-block:: json

      {
        "folders": [
          {
            "name": "Solution A",
            "path": "solution-a"
          },
          {
            "name": "Solution B",
            "path": "solution-b"
          },
          {
            "name": "Solution C",
            "path": "solution-c"
          }
        ],
        "settings": {}
      }

#. Open the workspace in VS Code:

   .. code-block:: bash

      code my-solutions.code-workspace

   or in VS Code: :menuselection:`File > Open Workspace from File` and select the ``.code-workspace`` file.

.. warning::

   SAF currently uses fixed ports (5724 for backend, 5725 for frontend). You cannot debug multiple
   solutions **simultaneously** because the ports would conflict. Debug one solution at a time and stop
   it before attaching to another.

