.. _script_solution:

Script a solution
#################

.. warning::

    The following assumes that:

    - The solution has been created using SAF CLI.
    - The solution virtual environment has been installed using the SAF CLI.
    - The solution is running on the local machine.
    - The script is created / downloaded in the solution root directory.

    This is temporary until an end-to-end workflow that includes the initialization of the solution API is provided.

The examples described here demonstrate how to use GLOW's ``Client`` from ``ansys.saf.glow.client`` to interact with a running Solution API server.

Basic interaction with the solution API
=======================================

The first section of this guide provides a basic example of how to interact with a SAF based solution using the GLOW API client.


Start the solution
---------------------

To start the solution API, the following SAF CLI command can be used:

.. code-block:: bash

    saf run my_solution --no-ui --solution-api-port 50000

It starts the solution API without the UI, listening on port 50000 for the requests that are made in the example.

For more information on how to run a solution, see :ref:`Run a solution <user_guide_run_on_desktop>`.


Run the example script
-----------------------

The example script can be run with SAF CLI, which automatically activates the solution virtual environment.

The full example script can be downloaded here: :download:`solution_example_script.py <../_static/examples/solution_scripting/solution_example_script.py>`. It contains all the code snippets provided in this guide.
To execute it, open a new terminal and run the following command:

.. code-block:: bash

    saf execute my_solution "python solution_example_script.py"

Perform imports and define the GLOW API server URL
--------------------------------------------------

Perform required imports.

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Perform required imports
    :end-before: # ----

Define the GLOW API server URL.

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Define the GLOW API server URL
    :end-before: # ----

Create a GLOW client
--------------------

Create a GLOW client to interact with the solution backend.

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Create a GLOW Client
    :end-before: # ----

List existing projects
----------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # List existing projects
    :end-before: # ----

Get an existing project
-----------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Get an existing project
    :end-before: # ----

Upgrade an existing project
---------------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Upgrade an existing project
    :end-before: # ----

Delete an existing project
--------------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Delete an existing project
    :end-before: # ----

Create a new project
--------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Create a new project
    :end-before: # ----

Get step fields
---------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Get step fields
    :end-before: # ----

Set step fields
---------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Set step fields
    :end-before: # ----

Run the calculate method
------------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Run the calculate method from the first step
    :end-before: # ----

Get the calculation result
--------------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Get the result
    :end-before: # ----

Handle method execution exceptions
------------------------------------

In case the method fails, an exception with information about the failure is raised. For more information, check the `Client API <https://glow-engine.docs.solutions.ansys.com/version/stable/api/client.html>`_
documentation.

Shut down the GLOW API server
---------------------------------

To shut down the GLOW API server, focus on the terminal where the solution API is running and press `Ctrl+C`. This stops the server and terminate the script.
If prompted to confirm the termination of the batch job, type `Y` and press `Enter`.

Manage projects
===============

This section provides an example of how to manage projects using the GLOW API client. For more details on how to manage projects, check :ref:`solution_projects_api`.

Export the project
------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Export the project
    :end-before: # ----

Delete the project
------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Delete the project
    :end-before: # ----

Import the project
------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Import the project
    :end-before: # ----

Access the project properties
-----------------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Access the project properties
    :end-before: # ----

Modify the project display name
-------------------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Modify the project display name
    :end-before: # ----

Delete the imported project
---------------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Delete the imported project
    :end-before: # ----

Create and manage multiple projects
===================================

This section provides an example of how to create and manage multiple projects using the GLOW Client.

Create a matrix of projects with different arguments
----------------------------------------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Create a matrix of projects with different arguments
    :end-before: # ----

Create multiple projects using a loop
-------------------------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Create multiple projects using a loop
    :end-before: # ----

Print the results of all project calculations
---------------------------------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Print the results of all project calculations
    :end-before: # ----

Get the available projects list
-----------------------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Getting the available projects list
    :end-before: # ----

Example output of the projects list:

.. code-block:: bash

    [
        {
            "display_name": "Project A",
            "date_created": "2025-07-07T10:44:10.790164",
            "date_modified": "2025-07-07T10:44:10.790164",
            "name": "projects/6867daaa13ae5d5ca473900d"
        },
        {
            "display_name": "Project B",
            "date_created": "2025-07-07T12:41:01.922904",
            "date_modified": "2025-07-07T12:41:01.922904",
            "name": "projects/686ba43d13ae5d8544081b3b"
        },
        {
            "display_name": "Project C",
            "date_created": "2025-07-07T12:45:10.235752",
            "date_modified": "2025-07-07T12:47:23.124312",
            "name": "projects/686ba43d13ae5d8544081b3b"
        }
    ]

Delete all created projects
---------------------------

.. literalinclude:: ../_static/examples/solution_scripting/solution_example_script.py
    :language: python
    :start-after: # Delete all created projects
    :end-before: # ----

