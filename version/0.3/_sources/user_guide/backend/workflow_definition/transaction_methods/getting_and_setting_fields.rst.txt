.. _getting_and_setting_fields:

Fetch and modify step fields
#############################

This page describes how to fetch and modify step fields with a transaction method.

The ``@transaction`` decorator takes keyword arguments which are step names which indicate which steps the method will access.
The value of these arguments must be a ``StepSpec`` object.

* The step name is the name of the step containing the data the method needs. It must match a field name given within the ``Steps`` class, or ``self`` if the step is the one defining the transaction method.
* The ``StepSpec`` defines which fields of the step will be downloaded before and uploaded after the method is executed.

.. note::
    The order of ``StepSpec`` arguments does not impose any ordering limitations for the arguments of the transaction method.

The annotated method must have arguments whose names correspond to the step names defined in the ``@transaction`` annotations.

Fetch and modify step fields on the same step as the method
===========================================================

The code sample below shows a ``generate_username`` transaction method used to generate a random username with a predefined prefix.
The ``StepSpec`` object specifies that the method performs the following actions:

#. Before the method is executed: download the value of the ``prefix`` field that is stored in the project database, so that ``self.prefix`` can be used.
#. After the method is completed: upload the ``username`` field back to the Solution API server to persist/store its value in the project.

.. code-block:: python

    class UsernameStep(StepModel):
        prefix: str = "user_"
        username: str = ""

        @transaction(self=StepSpec(download=["prefix"], upload=["username"]))
        def generate_username(self):
            """Generate a random username such as user_1234."""
            random_number = random.randint(0, 9999)
            self.username = f"{self.prefix}{random_number:04d}"


    class Steps(StepsModel):
        username_step: UsernameStep


    class MinimalSolution(Solution):
        display_name: str = "Minimal Solution"
        steps: Steps

Fetch step fields on a different step from the method
======================================================

It is possible for a transaction method to fetch fields from steps other than the one defining the method.
In this case, the ``StepSpec`` objects are defined for each step whose fields are accessed within the method using
the step name as arguments to the ``@transaction`` decorator. The step name being the member name corresponding to
the step within the ``Steps`` class.

It is not possible to upload field data to a different step from a transaction method.

The following is an alternative implementation of the ``generate_username`` method, where the ``prefix`` field is defined on another step.

.. code-block:: python

    class PrefixStep(StepModel):
        prefix: str = "user_"


    class UsernameStep(StepModel):
        username: str = ""

        @transaction(self=StepSpec(upload=["username"]), prefix_step=StepSpec(download=["prefix"]))
        def generate_username(self, prefix_step: PrefixStep) -> None:
            """Generate a random username such as user_1234."""
            random_number = random.randint(0, 9999)
            self.username = f"{prefix_step.prefix}{random_number:04d}"


    class Steps(StepsModel):
        prefix_step: PrefixStep
        generate_step: UsernameStep


    class MinimalSolution(Solution):
        display_name: str = "Minimal Solution"
        steps: Steps



