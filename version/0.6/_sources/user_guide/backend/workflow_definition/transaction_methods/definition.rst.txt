.. _transaction_method_definition:

Definition
##########

A transaction method is a method on a step class annotated with the ``@transaction`` decorator,
imported from ``ansys.saf.glow.solution``. When annotated, the method is automatically exposed
as an endpoint in the solution REST API and can be called from the application UI or any Python
client.

The ``@transaction`` decorator
===============================

The ``@transaction`` decorator is the core mechanism for defining transaction methods. It accepts
arguments that control which step fields the method reads from and writes to:

.. code-block:: python

    from ansys.saf.glow.solution import StepModel, transaction


    class MyStep(StepModel):
        input_value: float = 0.0
        result: float = 0.0

        @transaction(
            self=["input_value"],
            output=["result"],
        )
        def compute(self) -> None:
            self.result = self.input_value * 2.0

In the example above:

- ``self`` lists the fields that are **fetched** from the persisted step state before the method runs.
- ``output`` lists the fields that are **written back** to the persisted step state after the method completes.

Fetching and modifying step fields
====================================

Transaction methods can read and update persisted step data. The decorator arguments define
which fields are loaded into memory before the method executes and which are saved back to
the database after it returns. This mechanism also
:ref:`establishes dependencies between fields <field_states>`, so that downstream
fields are automatically invalidated when their upstream inputs change.

REST API exposure
==================

Each transaction method is automatically registered as a REST API endpoint by SAF GLOW Engine.
This means that the method can be invoked:

- From the **Dash frontend** using the :py:class:`DashClient <ansys.saf.glow.client.dash_client.DashClient>`.
- From a **Python script** using the solution's REST API directly.
- From any other HTTP client that can authenticate with the solution.

Cloud compatibility
====================

The implementation of transaction methods is designed to support both cloud and on-premises
deployments. See :ref:`cloud_compatibility` for guidelines on writing transaction
methods that work correctly in distributed environments.

.. note::

    Child processes started by a transaction method are automatically terminated when the
    method completes, regardless of whether the method succeeds or raises an exception.
