.. _deploy_desktop:

Desktop deployment
##################


Prerequisites
=============

For desktop deployments, the target machine must meet the following prerequisites:

* Administrative privileges are required only when installing to system-level locations (for example,
  ``C:\Program Files`` on Windows or ``/opt`` on Linux).
* On Windows:

  * The long path option should be enabled in the system settings.
    For more information, see `Maximum Path Length Limitation
    <https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation?tabs=registry>`_ in the official Microsoft
    documentation.

    .. note::
       The installer UI provides a **Check Windows Long Path enabled** checkbox (checked by default) that controls
       whether this requirement is enforced at installation time. You can deselect it to bypass the long path
       validation. See :ref:`bypassing-long-path-check` for details.

  * The ``WebView2`` runtime must be installed.
    You can download it from the official
    `Microsoft Edge WebView2 <https://developer.microsoft.com/en-us/microsoft-edge/webview2/?form=MA13LH>`__ page.


Installation
============

To install the solution from the generated installer, run the installer executable file located in the ``dist`` directory of the solution root directory.
For example, on Windows, run the ``<solution-name>-installer.exe`` file.

Once the installer UI appears, you can configure the installation directory of the solution using the ``Installation Location`` field.
On Windows, a **Check Windows Long Path enabled** checkbox is also displayed. When checked (the default), the installer
validates that Windows Long Path support is enabled before proceeding. You can deselect it to skip this validation;
see :ref:`bypassing-long-path-check` for guidance on when this is appropriate.

By default, the solution is installed in the following locations:


* **On Windows**:

  * Preferred location (if writable):
    ``C:\Program Files\ANSYS Inc\SAF Solutions\<solution-display-name> Solution``
  * Fallback locations (if needed):

    * ``%APPDATA%\ANSYS Inc\SAF Solutions\<solution-display-name> Solution``
    * ``%USERPROFILE%\AppData\Roaming\ANSYS Inc\SAF Solutions\<solution-display-name> Solution``
    * ``%USERPROFILE%\ANSYS Inc\SAF Solutions\<solution-display-name> Solution``

* **On Linux**:

  * Root install (when ``SUDO_USER`` is set):
    ``/opt/ansys_inc/saf_solutions/<solution-display-name> Solution``
  * Non-root install:
    ``~/.local/share/ansys_inc/saf_solutions/<solution-display-name> Solution``

After the installation is complete:

* On Windows, you can find the shortcut on the desktop and in the Start menu.
* On Linux:

  * Non-root installs create a desktop shortcut on the desktop and an application launcher entry.
  * Root installs create a system application launcher entry in ``/usr/share/applications``. The administrator is
    responsible for creating a desktop shortcut for the users.

    The administrator can do so by running the following commands:

    .. code-block:: bash

      chmod -R 755 "/opt/ansys_inc/saf_solutions/<solution-display-name> Solution/"  # Make the solution executable for all users
      cp "/usr/share/applications/<solution-display-name>.desktop" "/home/<username>/Desktop/"  # Copy the shortcut to a user's Desktop
      chown <username>:<username> "/home/<username>/Desktop/<solution-display-name>.desktop"  # Change the owner of the shortcut


Installer executable options
----------------------------

The installer executable also supports command-line options.

Run the following command to list all available options:

.. code-block:: text

  <solution-name>-installer --help

Common options include:

* ``--no-ui``: Run the installer without the UI.
* ``--installation-directory <PATH>``: Specify the installation directory.
* ``--metadata-file <PATH>``: Specify the solution metadata JSON file.
* ``--python-interpreter <PATH>``: Use a specific Python interpreter for installation.
* ``--use-pip``: Use pip to perform the installation.
* ``--port <INTEGER>``: Set the UI port when running with the UI.

For example:

.. code-block:: text

  <solution-name>-installer --no-ui --installation-directory "C:\\MySolutions"


.. _deploy_desktop_check_installation:

Check installation
==================

To verify that the solution is installed correctly, you can first try to launch the solution using the desktop shortcut or from the Start menu (on Windows).
If the solution launches, it indicates that the installation was successful. Otherwise, if nothing happens, the installation may have failed.

In case of failure, you can start the solution from the command line to see any error messages. Follow these steps:

#. Open a terminal (Command Prompt or PowerShell on Windows).

#. Navigate to the installation directory of the solution.

   The default location is:

   * **On Windows**: ``C:\Program Files\ANSYS Inc\SAF Solutions\<solution-display-name> Solution\<version>\definitions\<solution-name>``
   * **On Linux**: ``/opt/ansys_inc/saf_solutions/<solution-display-name> Solution/<version>/definitions/<solution-name>``

#. Activate the virtual environment:

   .. tab-set::

     .. tab-item:: Windows

         .. code-block:: PowerShell

           .\.venv\Scripts\activate

     .. tab-item:: Linux

         .. code-block:: bash

           source .venv/bin/activate

#. Run the following command:

   .. code-block:: text

     python -m ansys.saf.desktop.orchestrator --solution-main-module-name ansys.solutions.<solution-name>.main --portal

   Replace ``<solution-name>`` with the actual name of your solution.

If the solution fails to launch, the terminal should display error messages, which can help you to diagnose the installation issue.

.. note::

  To run the command from any location without navigating to the installation directory, you must add the ``--env-file`` option to specify the path to the ``.env`` file located in the installation directory:

  .. code-block:: text

    python -m ansys.saf.desktop.orchestrator --solution-main-module-name ansys.solutions.<solution-name>.main --portal --env-file "C:\Program Files\ANSYS Inc\SAF Solutions\<solution-display-name> Solution\<version>\definitions\<solution-name>\.env"

  To verify that it's loaded, check the terminal output for a line similar to the following:

  .. code-block:: text

    INFO - Environment variables loaded from C:\Program Files\ANSYS Inc\SAF Solutions\<solution-display-name> Solution\0.0.0\definitions\<solution-name>\.env

.. tip::

  Also, you can replace the ``python`` executable to point to the one in the virtual environment instead of going to the installation directory and activating it. For example:

  .. code-block:: text

    "C:\Program Files\ANSYS Inc\SAF Solutions\<solution-display-name> Solution\<version>\definitions\<solution-name>\.venv\Scripts\python.exe" -m ansys.saf.desktop.orchestrator --solution-main-module-name ansys.solutions.<solution-name>.main --portal --env-file "C:\Program Files\ANSYS Inc\SAF Solutions\<solution-display-name> Solution\<version>\definitions\<solution-name>\.env"

.. seealso::

    For common problems encountered during or after a desktop deployment, and their workarounds, see
    :ref:`troubleshooting_deployment`. If the solution fails to start on a machine with corporate proxy
    settings configured, see :ref:`troubleshooting_proxy_startup_failure`.


Uninstall
=========

To uninstall the solution, delete both the installation directory of the solution and the desktop shortcut.
