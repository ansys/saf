.. _client_side:

Client-side interaction
#######################

This guide explains how to leverage the Python client to interact with the solution REST API (backend) from the Dash server (frontend).

.. _project-injection:

Project injection in callbacks
===============================

To access the solution project instance within a Dash callback, you need to pass the project via the pathname property of the ``dcc.Location`` component,
usually tagged with the ``"url"`` identifier, as an input or state in the callback decorator.

Basic usage
-----------

Here's how to inject the project instance into your callback:

.. code-block:: python

    from ansys.saf.glow.client import callback
    from ansys.solutions.minimal.solution.definition import MyMinimalSolution
    from dash_extensions.enrich import Input, State, Output


    @callback(..., Input("button", "n_clicks"), State("url", "pathname"))  # Your output here
    def my_callback(n_clicks: int, project: MyMinimalSolution):
        # Your callback logic here
        pass

The ``project`` parameter will be automatically injected with the current project instance, allowing you to interact with the solution backend.

Access the solution backend
============================

Once you have the project instance injected into your callback, you can access various solution components:

Access steps
---------------

Use the ``project.steps`` attribute to access and interact with the solution steps:

.. code-block:: python

    from ansys.saf.glow.client import callback
    from ansys.solutions.minimal.solution.definition import MyMinimalSolution
    from dash_extensions.enrich import Input, State, Output


    @callback(..., Input("button", "n_clicks"), State("url", "pathname"))  # Your output here
    def my_callback(n_clicks: int, project: MyMinimalSolution):
        # Access a specific step
        my_step = project.steps.my_step_name

        # Execute a transaction method in the step
        my_step.my_transaction()

        # Set a step field
        my_step.field_name = new_value

        ...

Access storage scope
-----------------------

Use the ``project.storage_scope`` attribute to manage data persistence and storage:

.. code-block:: python

    from ansys.saf.glow.client import callback
    from ansys.solutions.minimal.solution.definition import MyMinimalSolution
    from dash_extensions.enrich import Input, State, Output


    @callback(..., Input("button", "n_clicks"), State("url", "pathname"))  # Your output here
    def my_callback(n_clicks: int, project: MyMinimalSolution):
        # Access the storage scope
        storage = project.storage_scope

Best practices for troubleshooting
===================================

When encountering issues with project injection, follow these debugging steps:

1. **Verify type hints**: Ensure all callback arguments have proper type annotations.

2. **Check Dash version**: Confirm you're using Dash 3.0.0 or higher:

   .. code-block:: python

       import dash

       print(dash.__version__)

3. **Validate project type**: Make sure your project type annotation matches your solution class:

   .. code-block:: python

       from ansys.solutions.your_solution.definition import YourSolution


       @callback(State("url", "pathname"))
       def my_callback(project: YourSolution):  # Use your actual solution class
           pass

4. **Check import statements**: Ensure you're importing the callback decorator from the correct module:

   .. code-block:: python

       from ansys.saf.glow.client import callback  # Correct import

5. **Enable debug logging**: Add logging to help diagnose issues:

   .. code-block:: python

       import logging

       logging.basicConfig(level=logging.DEBUG)


       @callback(State("url", "pathname"))
       def my_callback(project: YourSolution):
           logging.debug(f"Project injected: {type(project)}")
           # Your callback logic
           pass