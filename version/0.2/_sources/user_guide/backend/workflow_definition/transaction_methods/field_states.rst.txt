.. _field_states:

Field states and dependencies
#####################################

The ``StepSpec`` arguments to a ``@transaction`` decorator imply a dependency between the referenced fields.
Any field that is uploaded from a method is implicitly dependent on the fields that are downloaded to the method.
The GLOW server uses these implicit dependencies to track the state of fields and detect cyclic dependencies.

.. _dependency-graph:

Dependency graph
================
SAF GLOW Engine constructs a :dfn:`dependency graph` from the instances of the ``transaction`` decorator in a solution. The graph consists of nodes representing fields and methods.

* A method is downstream of a field if the field is downloaded to the method.
* A field is downstream of a method if the field is uploaded from the method.

These downstream linkages form a directed graph covering all the fields of the solution representing the flow of data through the solution.
This directed graph is the `dependency graph`.

The example below shows a step definition within a method. The diagram that follows shows the dependency graph extracted from the transaction method.

.. code-block:: python

    class StepB(StepModel):

        b1: int = 99


    class StepA(StepModel):

        a1: int = 0
        a2: int = 1
        a4: int = 3

        @transaction(
            self=StepSpec(download=["a1", "a2"], upload=["a4"]),
            step_b=StepSpec(download=["b1"]),
        )
        def a_thing(self, step_b: StepB) -> None:
            self.a4 = f"{self.a1}.{self.a2}.{step_b.b1}"

.. figure:: /_static/images/transaction_dependency_extraction.png


Transaction field validations
=============================

Field validations are performed on the transaction method when the solution is started. Any of the following errors cause the solution to exit:

* A field cannot be defined as both ``download`` and ``upload`` (input and output) for the same ``StepSpec``.
* Upload fields are restricted to the current step of the method (``self``).
* Fields cannot have cyclic dependencies. Specifically, the :ref:`dependency graph <dependency-graph>` has no cycles.


.. _field-states:

Field states
==============

Field states can be retrieved from the ``state`` property from a step object.

.. note::
    Assignments and modifications to the ``state`` property field are possible but are not recommended.


The ``state`` property is a dictionary mapping the name of each field on the step to the state of the field.
The state of a field can be considered a conservative estimate by the GLOW server of whether the field is consistent with upstream field values (``UPTODATE``) or inconsistent with upstream field values (``OUTOFDATE``).

Field state algorithm
----------------------

The GLOW server uses a simple algorithm described below to make this estimate:

A field `A` is upstream of field `B` if there is a path from `A` to `B` in the :ref:`dependency graph <dependency-graph>`.

SAF GLOW Engine  computes a field's state based on:

* the type of the field;
* whether the field value has been modified; and
* whether a field value upstream is modified.

A field becomes ``OUTOFDATE`` if any of the field's upstream field values are modified.

A field becomes ``UPTODATE`` if the field's value is modified.

Initial field states
----------------------

The initial ``FieldState`` of a field is determined as follows:

* Fields with upstream fields are initially ``OUTOFDATE``.
* Fields that are not in the above category are initially ``UPTODATE``.
