.. _troubleshooting_project_injection:

Project injection in Dash callbacks
###################################

This section covers common issues encountered when the solution project instance is not
injected as expected into a Dash callback. See :ref:`project-injection` for a description
of the injection mechanism.

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
