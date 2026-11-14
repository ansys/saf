.. _debug_transaction_methods:


Debug transaction methods
#########################

Transaction methods form the backbone of your solution's backend logic. This debugging mode allows you to set breakpoints and step through your backend Python code as it executes.



Prerequisites
=============

Before setting up debugging, ensure you have:

- Installed the Python extension in VS Code (see :ref:`debug_prerequisites`)
- Opened a single solution (see :ref:`debug_single_solution`) or a multi-root workspace with multiple solutions (see :ref:`debug_multi_solution`)
- Verified the ``.vscode/launch.json`` file at the root of the solution folder (see :ref:`debug_prerequisites`)
- Verified that the ``.vscode/launch.json`` file contains the **Python: Remote Attach** debug configuration


Debugging workflow
==================

Step 1: Run in debug mode
--------------------------

.. tab-set::

    .. tab-item:: SAF CLI

      Run the solution in debug mode using SAF CLI:

      #. Open the solution folder directly in VS Code:

         .. code-block:: bash

              code path/to/my-solution

      #. Run the solution with the ``--debug`` flag:

         .. code-block:: bash

             saf run --debug

    .. tab-item:: Solutions Manager

      Run the solution in debug mode using Solutions Manager:

      #. Open Visual Studio Code.

      #. In the Activity Bar, click the **Solutions Manager** icon.

      #. In the **Solutions Manager** pane, expand the **Run Solution** view.

         .. image:: /_static/images/solutions_manager_run_solution_view_debug_mode.png
           :alt: Solutions Manager Run Solution view with Debugging mode enabled
           :width: 45%

      #. Provide the following values:

         a. Select the solution you want to debug.

         b. When selecting your run options, ensure that **Debug mode** is selected.

         c. Provide other values as needed. For more information, see :ref:`user_guide_run_on_desktop`.

      #. Run the solution.

         Click the :guilabel:`Run solution` button. Alternatively, you can copy the command under **Solution run command** and run it in the terminal.

The solution runs in debug mode and the output is displayed in the terminal.

.. admonition:: Result

  When the solution is run, it performs the following actions:

  * Enables Python debugging in the solution API server process.
  * Starts ``debugpy`` listening on port ``5724`` or the next available port and logs the port to the terminal.
  * Enables Uvicorn hot-reload when configured (controlled by :envvar:`GLOW_API_HOT_RELOAD`, enabled by default).


.. tip::

  Instead of using the ``--debug`` flag, you can enable debug mode by setting the :envvar:`GLOW_DEBUG`
  environment variable to any value. This starts solutions in debug mode automatically, eliminating
  the need to specify the ``--debug`` flag each time you run a solution.

  .. tab-set::

    .. tab-item:: Windows

      .. tab-set::

        .. tab-item:: PowerShell

          .. code-block:: powershell

            $env:GLOW_DEBUG = "True"

        .. tab-item:: Command Prompt

          .. code-block:: batch

            set GLOW_DEBUG=True

    .. tab-item:: Linux/macOS

      .. code-block:: bash

        export GLOW_DEBUG=True


.. _user_guide_debug_transaction_methods_attach_debugger:

Step 2: Attach the debugger
-----------------------------

#. Wait for the solution API server to start. The output should contain a line similar to:

   .. code-block:: bash

    INFO - Starting Solution API...

#. Open the **Run and Debug** panel by pressing :kbd:`Ctrl+Shift+D`

#. In the **Search configurations** menu, select **Python: Remote Attach** (if it is not already selected.)

   .. image:: /_static/images/solutions_manager_run_solution_view_debug_remote_attach.png
     :alt: Python: Remote Attach debug configuration
     :width: 45%

#. Press :kbd:`F5` or click the green **Start Debugging** button to attach the debugger.

#. Validate that the debugger is attached by checking the VS Code status bar and **Debug Console**.

   .. image:: /_static/images/solutions_manager_run_solution_view_debug_remote_attach_confirm.png
     :alt: Python: Remote Attach debug confirmation
     :width: 100%

.. admonition:: Result

  After attaching the debugger, you should see:

  * The VS Code status bar shows: **Python: Remote Attach (<name-of-your-solution>)**.
  * The **Debug Console** indicates a successful connection.
  * The **Run and Debug** panel shows that the solution API process is running.


.. _user_guide_debug_transaction_methods_set_breakpoint:

Step 3: Set a breakpoint
-------------------------

#. Set a breakpoint in a transaction method by clicking the gutter to the left of the line numbers:

   .. image:: /_static/images/debugging_set_breakpoint_transaction_method.png
         :alt: Set a breakpoint in a transaction method
         :width: 85%

#. Invoke the transaction method using the :ref:`solution UI <solution_servers_ui_server>` or the :ref:`API swagger interface <solution_servers_api_server>`.


This causes the debugger to pause at the breakpoint in the method.


.. admonition:: Result

  When the breakpoint in the transaction method is hit:

  * The debugger pauses execution at the breakpoint and highlights the paused line in the editor.
  * The **Call Stack** pane shows the current stack and the **Variables/Locals** panes are populated for the active frame.
  * **Step Over** / **Step Into** / **Continue** controls are enabled and you can evaluate expressions in the **Debug Console**.



Debugger port
=============

Automatic port selection
------------------------

By default, SAF GLOW Engine uses port **5724** for backend debugging.

If multiple processes are run simultaneously or the port is used by another non-GLOW process, then SAF GLOW Engine attempts to find an available port dynamically.

To find the port being used, check the GLOW API logs:

#. Find the line containing ``#### API server listening for debug on port: 5724 ####``.

   .. note::

     The API server logs the debug port on startup. Look for a line like:

     .. code-block:: text

       #### API server listening for debug on port: 5724 ####

     If the port differs, update your launch configuration or set :envvar:`GLOW_DEBUG_API_PORT` to a fixed value.

#. If the port  is different than **5724**, then modify your :guilabel:`Python: Remote Attach` debug configuration accordingly, setting the ``port`` key with the value obtained from the log line:

   .. code-block:: json

    {
      "name": "Python: Remote Attach",
      "type": "python",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": "$PORT_FROM_LOG"
      },
      "justMyCode": false
    }

.. seealso::
  For more information about the configuration file, see Visual Studio Code's `Python debugging instructions <https://code.visualstudio.com/docs/python/debugging>`_ .


Manual port selection
---------------------

You can specify a particular debug port by setting the :envvar:`GLOW_DEBUG_API_PORT` environment variable and then modifying the
:guilabel:`Python: Remote Attach` debug configuration to refer to it.

#. Set the :envvar:`GLOW_DEBUG_API_PORT` environment variable to the port you want to use.

#. In the ``launch.json`` file found in the ``.vscode`` folder at the root of the project, set the key value of the ``port`` to the value of :envvar:`GLOW_DEBUG_API_PORT`:

   .. code-block:: json

    {
      "name": "Python: Remote Attach",
      "type": "python",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": "${env:GLOW_DEBUG_API_PORT}"
      },
      "justMyCode": false
    }

If the specified port is unavailable, SAF GLOW Engine cannot use it, resulting in a connection error and subsequent shutdown.
