.. _best_practices_logic:

Business logic
##############

What is "business logic" in the context of a SAF Solution?
===========================================================

Business logic refers, in the context of a SAF Solution, to code that interacts with the APIs of Ansys Products typically via their PyAnsys packages.
Often this code is the initial code that was created by a simulation analyst to prototype the steps needed to perform the simulation tasks
that will be automated by the SAF solution.

Where should business logic source code be located within a solution source tree?
====================================================================================

It is recommended that business logic is kept in separate modules and directories from the rest of the solution code.
This separation will enable the business logic, solution UI and solution data schema to evolve and be tested independently of each other.

It is recommended that business logic modules are located in the ``logic`` directory with the ``solution`` directory.

For example consider the following solution source tree:

.. code-block:: text

    my_solution/
    ├── pyproject.toml
    ├── README.md
    ├── src
    │   └── ansys
    │       └── solutions
    │           └── rocket_launch_simulator
    │               └── solution
    │                   └── logic
    │                       └── logic.py

The module ``logic.py`` would contain business logic code that interacts with the PyAnsys product APIs to perform simulation tasks.

What are the Python code forms that should be used in business logic modules?
=================================================================================

To ensure maintainability, readability, and testability of the application, all business logic must be implemented in a modern, modular,
and Pythonic manner. This includes adhering to the following principles:

#. Modular design

    - Business logic must be organized into dedicated Python modules based on functionality or domain responsibility.
    - Each module should contain either:
        - Functions that encapsulate well-defined tasks, or
        - Classes that represent logical objects or services with cohesive behavior.

#. No Top-Level Code

    - Avoid writing executable code at the top level of a module (that is, not inside a function or class). This includes any logic that performs computations, file I/O, network calls, or data processing.
    - Top-level code should be strictly limited to:
        - Function/class definitions
        - Constant declarations
        - Optional guard blocks like ``if __name__ == "__main__":`` for module testing

#. Separate starting and stopping products from code that operates on the product.

   - Instead of having a single function that both starts a product and operates on the product's API (normally via its PyAnsys library), split these responsibilities into separate functions.

Why This Matters?

- Improves code reusability and testability
- Prevents side effects during imports
- Enables unit testing and code introspection
- Promotes clean architecture and separation of concerns
- Enables future flexibility as to how a product is launched and managed. SAF provides different ways to start products so ensuring business logic that uses a product is separated from the code that starts the product enables easy refactoring to use different approaches.

Here is an example of a bad practice:

.. code:: python

    data = load_data("file.csv")  # Top-level code: runs on import


    def process_data(data): ...

Here is an example of a good practice:

.. code:: python

    def load_data(file_path): ...  # Function definition only, no execution


    if __name__ == "__main__":
        data = load_data("file.csv")  # Executed only when run as a script
