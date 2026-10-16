.. _test_solution_api:

Solution API testing
######################

Solution API testing is done using the ``client_project`` fixture.

With ``client_project``, you gain direct access to your solution project's attributes and methods
(for example, ``client_project.steps.first_step.first_arg``), allowing you to interact with and validate your solution logic.
The fixture ensures a project is created for each test and automatically deletes it afterwards.

To use this fixture in your tests, you just need to add ``client_project`` as an argument to your test function.
pytest will automatically execute the fixture and provide the project instance.

Example setup
===============

For the tests, we are going to use a minimal SAF-based solution created with the SAF CLI ``saf new`` command.
This solution generated from the template is a simple two-step, first step that provides a simple
calculator to perform arithmetic operations and a second step with an empty page serving as a
placeholder.

For the minimal SAF-based solution we define a first step with a few fields and transactions:

.. code-block:: python

    class FirstStep(StepModel):
        """Step definition of the first step."""

        first_arg: float = 0
        second_arg: float = 0
        result: float = 0

        file_1: EntityHandle = NO_ENTITY
        file_2: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(upload=["result"], download=["first_arg", "second_arg"]))
        def calculate(self) -> None:
            """Compute the sum of two numbers."""
            self.result = self.first_arg + self.second_arg

        @transaction(self=StepSpec(upload=["file_2"], download=["file_1"]))
        def process_file(self) -> None:
            if self.file_1 is NO_ENTITY:
                raise ValueError("file_1 must be set before calling process_file.")

            modified_file = self.storage_scope.get_storage_root() / "my_second_file.txt"
            modified_file.write_text("NOT " + self.storage_scope.get_text(self.file_1))
            self.file_2 = self.storage_scope.store(modified_file)


Set and retrieve step fields
============================

.. code-block:: python

   def test_set_and_retrieve_basic_step_fields(client_project: MySolution):
       first_step = client_project.steps.first_step
       # retrieve step field
       assert first_step.first_arg == 0
       # set step field
       first_step.first_arg = 1.0
       # retrieve updated value
       assert first_step.first_arg == 1.0
       # set multiple fields
       first_step.set_fields({"first_arg": 2.0, "second_arg": 3.0})
       # retrieve updated values
       assert first_step.first_arg == 2.0
       assert first_step.second_arg == 3.0


Run a transaction
====================

.. code-block:: python

   def test_calculate(client_project: MySolution):
       first_step = client_project.steps.first_step
       first_step.first_arg = 5.0
       first_step.second_arg = 10.0
       first_step.calculate()
       assert first_step.result == 15.0

.. admonition:: Warning
   :class: warning

   **Long-running transaction tests may behave in a blocking way.**

   When launching long-running transactions in tests, the transaction may actually block until it completes, even though
   it is intended to run in the background. As a result, loops or waits for transaction completion in your tests may be
   misleading, since the transaction is already done when the request ends. Be aware of this behavior when writing and
   interpreting tests for long-running transactions.


Handle files using BDM
=======================

.. code-block:: python

    def test_bdm_fields_and_transactions(client_project: MySolution):
        # Write a test file
        text_file = client_project.storage_scope.get_storage_root() / "my_input_file.txt"
        text_file.write_text("This is a test file.")
        client_project.steps.first_step.file_1 = client_project.storage_scope.store(text_file)

        # Call transaction that uses entity handles and generated another one
        client_project.steps.first_step.process_file()

        # Retrieve content of second one
        assert client_project.storage_scope.get_text(client_project.steps.first_step.file_2) == "NOT This is a test file."
