.. _prerequisites_python_interpreter:

Python interpreter
##################

Supported Python versions
=========================

.. list-table::
   :header-rows: 1
   :stub-columns: 1
   :widths: 30 70

   -  - Python version
      - End of life

   -  - :bdg-success:`3.11`
      - October 2027

   -  - :bdg-success:`3.12`
      - October 2028

   -  - :bdg-success:`3.13`
      - October 2029

   -  - :bdg-success:`3.14`
      - October 2030

Installation
============

#. Download the Ansys Python Manager tool:

   Download the latest version from `here <https://github.com/ansys/python-installer-qt-gui/releases/download/v0.3.10/Ansys-Python-Manager-Setup-v0.3.10.exe>`_.

#. Run the installer:

   a. Double-click the installer.
   b. For installation type, select **STANDARD** and **Python 3.11** or **Python 3.12** or **Python 3.13** or **Python 3.14**.
   c. Proceed with the installation.

#. Add the selected interpreter to the ``PATH`` environment variable:

   a. Find the ``PATH`` environment variable in the session settings.
   b. Add the following lines:

      - ``C:\Users\<username>\AppData\Local\Programs\Python\Python3xx\Scripts\``
      - ``C:\Users\<username>\AppData\Local\Programs\Python\Python3xx\``

        .. important::

         - Be sure to replace ``<username>`` with your actual username and ``3xx`` with the version you installed (for example, ``311`` for Python 3.11, ``312`` for Python 3.12, ``313`` for Python 3.13, or ``314`` for Python 3.14).
         - If you have multiple Python versions installed, be sure to add the new entries at the top of the list. Use the :guilabel:`Move Up` button to move the new entries to the top of the list.
         - Don't mix conflicting entries. If System Path environment variable contains
           other Python versions, they may take precedence over the new
           Python order defined in the user :envvar:`Path` environment variable. To avoid this, make sure the new Python entries are at the top of the list in both :envvar:`Path` environment variables.

   c. Click :guilabel:`OK` to save the changes.

#. Verify the installation:

   a. Open a command prompt.
   b. Type ``python --version`` and press :kbd:`Enter`.

   You should see the version of Python you just installed: ``Python 3.xx``

   .. warning::

      If the command outputs a Python version that is not the one you just installed, it means that the order of the Python interpreters
      in the :envvar:`PATH` environment variable is not correct.

#. Install ``toml`` and ``packaging`` on your current system Python interpreter:

   a. Open a command prompt.
   b. Type the following command and press :kbd:`Enter`:

      .. code-block:: bash

        pip install toml packaging
