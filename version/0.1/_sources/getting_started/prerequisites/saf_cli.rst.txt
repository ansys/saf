.. _prerequisites_saf_cli:

SAF CLI
#######

There are two ways to install SAF CLI. Choose the approach that best suits your workflow.


Central installation
====================

Install SAF CLI directly into your base Python interpreter:

.. code-block:: bash

   pip install ansys-saf-cli

This makes the ``saf`` command available system-wide without activating any virtual environment. It is
the quickest approach and suitable when you only need a single version of SAF CLI.


(Recommended) Installation in a virtual environment
====================================================

Installing SAF CLI in a dedicated virtual environment keeps your base Python interpreter clean and
lets you maintain multiple versions of SAF CLI side by side---for example, one per project or one per
SAF release.

.. note::
   Name the virtual environment ``.cli`` to distinguish it from the solution virtual environments
   created by SAF CLI itself, which are named ``.venv``.

#. Create the dedicated virtual environment at a convenient location (for example, your home directory
   or a shared tools folder):

   .. code-block:: bash

      python -m venv .cli

#. Activate the virtual environment:

   .. tab-set::

      .. tab-item:: Windows PowerShell

         .. code-block:: powershell

            .cli\Scripts\Activate.ps1

      .. tab-item:: Linux/macOS

         .. code-block:: bash

            source .cli/bin/activate

#. Install SAF CLI:

   .. code-block:: bash

      pip install ansys-saf-cli

#. Verify the installation:

   .. code-block:: bash

      saf --version

The ``saf`` command is available whenever the ``.cli`` virtual environment is active.
