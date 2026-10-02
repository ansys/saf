.. _debug_dash_callbacks:


Debug Dash callbacks
####################

The Dash framework provides a set of debug tools (as described in the official `Dash Dev Tools <https://dash.plotly.com/devtools>`_ documentation) that are specialized for debugging your solution's frontend interface, particularly focusing on Dash callbacks and component rendering.

This section describes how to use the Visual Studio Code (VS Code) development environment to attach a debugger inside Dash callbacks.


.. attention::

  Debugging code inside Dash callbacks using the remote debugger disables the tools described in the `Dash Dev Tools <https://dash.plotly.com/devtools>`_ documentation. Only one debugging method can be active at a time.

Prerequisites
=============

Before setting up debugging, ensure you have:

- Installed the Python extension in VS Code (see :ref:`debug_prerequisites`)
- Opened a single solution (see :ref:`debug_single_solution`) or a multi-root workspace with multiple solutions (see :ref:`debug_multi_solution`)
- Verified the ``.vscode/launch.json`` file at the root of the solution folder (see :ref:`debug_prerequisites`)
- Verified that the ``.vscode/launch.json`` file contains the **Python: Remote Attach Dash** debug configuration


Debugging workflow
==================

Step 1: Run in debug mode
--------------------------

.. tab-set::

    .. tab-item:: SAF CLI

      Run the solution in UI debug mode using SAF CLI:

      #. Open the solution folder directly in VS Code:

         .. code-block:: bash

              code path/to/my-solution

      #. Start the solution with the ``--ui-debugger`` flag:

         .. code-block:: bash

             saf run --ui-debugger

    .. tab-item:: Solutions Manager

      Run the solution in UI debug mode using Solutions Manager:

      #. Open Visual Studio Code.

      #. In the Activity Bar, click the **Solutions Manager** icon.

      #. In the **Solutions Manager** pane, expand the **Run Solution** view.

         .. image:: /_static/images/solutions_manager_run_solution_view_ui_debug_mode.png
           :alt: Solutions Manager Run Solution view with UI debugging mode enabled
           :width: 40%

      #. Provide the following values:

         a. Select the solution you want to debug.

         b. When selecting your run options, ensure that **UI debugger** is selected.

         c. Provide other values as needed. For more information, see :ref:`user_guide_run_on_desktop`.

      #. Run the solution.

         Click the :guilabel:`Run solution` button. Alternatively, you can copy the command under
         **Solution run command** and run it in the terminal.

.. admonition:: Result

  When the solution is run, it performs the following actions:

  * Enables Python debugging in the solution UI process.
  * Starts ``debugpy`` listening on port ``5725`` or the next available port and logs the port to the terminal.
  * Disables the Dash/Flask debugger because it is incompatible with ``debugpy``.

The solution runs in UI debug mode and the output is displayed in the terminal.

.. tip::

  Instead of using the ``--ui-debugger`` flag, you can enable UI debug mode by setting the :envvar:`GLOW_UI_PYTHON_DEBUGGING` environment variable to any value. This starts solutions in UI debug mode automatically, eliminating the need to specify the ``--ui-debugger`` flag each time you run a solution.

  .. tab-set::

    .. tab-item:: Windows

        .. tab-set::

            .. tab-item:: PowerShell

                .. code-block:: powershell

                    $env:GLOW_UI_PYTHON_DEBUGGING = "True"

            .. tab-item:: Command Prompt

                .. code-block:: batch

                  set GLOW_UI_PYTHON_DEBUGGING=True

    .. tab-item:: Linux/macOS

        .. code-block:: bash

          export GLOW_UI_PYTHON_DEBUGGING=True


.. _user_guide_debug_dash_callbacks_attach_debugger:

Step 2: Attach the debugger
---------------------------

#. Wait for the solution UI server to start. The output should contain a line similar to:

   .. code-block:: text

      INFO - Starting Solution UI...

#. Open the **Run and Debug** by pressing :kbd:`Ctrl+Shift+D`.

#. In the **Search configurations** menu, select **Python: Remote Attach Dash** (if it is not already selected.)

   .. image:: /_static/images/solutions_manager_run_solution_view_debug_remote_attach.png
     :alt: Python: Remote Attach debug configuration
     :width: 40%

#. Press :kbd:`F5` or click the green **Start Debugging** button to attach the debugger.


#. Validate that the debugger is attached by checking the VS Code status bar and **Debug Console**.

   .. image:: /_static/images/solutions_manager_run_solution_view_debug_remote_attach_confirm.png
     :alt: Python: Remote Attach debug confirmation
     :width: 100%

.. admonition:: Result

  After attaching the debugger, you should see:

  * The VS Code status bar shows: **Python: Remote Attach (<name-of-your-solution>)**.
  * The **Debug Console** indicates a successful connection.
  * The **Run and Debug** panel shows that the solution UI process is running.


.. _user_guide_debug_dash_callbacks_set_breakpoint:

Step 3: Set a breakpoint
------------------------

#. Set a breakpoint in a Dash callback by clicking the gutter to the left of the line numbers:

   .. image:: /_static/images/debugging_set_breakpoint_dash_callback.png
     :alt: Set a breakpoint in a Dash callback
     :width: 85%

#. Invoke the Dash callback using the :ref:`solution UI <solution_servers_ui_server>`.

This causes the debugger to pause at the breakpoint in the callback.


.. admonition:: Result

  When the breakpoint in the Dash callback is hit:

  * The debugger pauses execution at the breakpoint and highlights the paused line in the editor.
  * The **Call Stack** pane shows the current stack and the **Variables/Locals** panes are populated for the active frame.
  * **Step Over** / **Step Into** / **Continue** controls are enabled and you can evaluate expressions in the **Debug Console**.



UI debugger port
==================

Automatic port selection
------------------------

By default, SAF GLOW Engine uses port **5725** for frontend debugging.

If multiple processes are run simultaneously or the port is used by another non-GLOW process, then SAF GLOW Engine attempts to find an available port dynamically.

To find the port being used, check the GLOW UI logs:

#. Find the line containing ``#### UI server listening for debug on port: 5725 ####``.

   .. note::

     The UI server logs the debug port on startup. Look for a line like:

     .. code-block:: text

       #### UI server listening for debug on port: 5725 ####

     If the port differs, update your "Python: Remote Attach Dash" configuration or set :envvar:`GLOW_DEBUG_UI_PORT` to a fixed value.

#. If the port  is different than **5725**, then modify your :guilabel:`Python: Remote Attach Dash` debug configuration accordingly, setting the ``port`` key with the value obtained from the log line:

   .. code-block:: json

    {
      "name": "Python: Remote Attach Dash",
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

You can specify a particular debug port by setting the :envvar:`GLOW_DEBUG_UI_PORT` environment variable and then modifying the :guilabel:`Python: Remote Attach Dash` debug configuration to refer to it.

#. Set the :envvar:`GLOW_DEBUG_UI_PORT` environment variable to the port you want to use.

#. In the ``launch.json`` file found in the ``.vscode`` folder at the root of the project, set the key value of the ``port`` to the value of :envvar:`GLOW_DEBUG_UI_PORT`:

   .. code-block:: json

    {
      "name": "Python: Remote Attach Dash",
      "type": "python",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": "${env:GLOW_DEBUG_UI_PORT}"
      },
      "justMyCode": false
    }

If the specified port is unavailable, SAF GLOW Engine cannot use it, resulting in a connection error and subsequent shutdown.
