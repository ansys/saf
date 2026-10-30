.. _asynchronous_execution:

Long running execution
##############################################

A transaction method exposed to the Python client or REST API may take a significant time to execute.
This is often problematic, as it blocks the Python client and causes the REST ``POST`` method to hang
for the duration of the method's execution. To ensure that the Python client is not blocked and that the
REST ``POST`` call completes immediately (before the transaction method finishes executing), you can annotate
the method with the ``@long_running decorator`` (imported from ``ansys.saf.glow.solution``).


Types of method execution
==========================

Transaction methods can be defined as either blocking or long-running.

Blocking methods
 By default, methods run synchronously, blocking other methods until execution is complete. In this case, the API server holds its response until the method is finished executing.

 This is reflected in both the UI client server (which blocks calls to the method) and the REST API (which delays the ``POST`` response) until method execution is complete.

Long-running methods
 When the ``@long_running`` decorator is used, the annotated method runs asynchronously, allowing other methods to run while its own execution is still in progress.

 In this case, the API server returns a response immediately and there are no delays for actions performed by the UI client server and the REST API.


Declare a long-running method
================================

Use the ``@long_running`` decorator to define asynchronous execution for a  transaction method.

For example, the ``start_solver_product`` method defined below launches a product that will perform a solve (and the product startup may be a lengthy process). Because the method executes asynchronously, however, other operations can be performed during the time it takes for the solver product to start.

.. code:: python

    @transaction(self=StepSpec(upload=["results_file", "solve_status"], download=["setup_file"]))
    @long_running
    def start_solver_product(self, setup_step: SetupStep, project_selection_step: ProjectSelectionStep) -> None:
        """Start the solver product that will perform the fluid analysis solve."""

.. _uploading_field_during_async_execution:

Upload a field during asynchronous execution
================================================

When a transaction method is executing asynchronously, you can use the ``self.transaction.upload(["field_name"])`` function within the method to upload a changed field value while the execution is still in progress.

.. code:: python

    @transaction(self=StepSpec(upload=["x"]))
    @long_running
    def upload_x_within_method(self):
        for i in range(2):
            self.x = i
            self.transaction.upload(["x"])
            time.sleep(0.5)
        self.x = 33


Check method execution status
=================================

You can check whether a method is still running using either the REST interface or the Python client. The following status values are possible:

* ``RunRequired``
* ``Running``
* ``Completed``
* ``Failed``


Check execution status with the REST API
-------------------------------------------

To check the execution status using the REST API:

#. Open the solution's REST interface.

#. Invoke the method using the ``POST /projects/{project_id}/steps/{step_id}:method`` endpoint.

   For the previous example, this would be:

   .. code:: text

        POST /projects/129dke20/steps/emag-solution-step:start-solver-product

#. Check the execution status using the ``GET projects/{project_id}/steps/{step_id}:method`` endpoint.

   For the previous example, this would be:

   .. code:: text

        GET /projects/129dke20/steps/emag-solution-step:start-solver-product


The method's execution status is shown in the :guilabel:`Response` body's ``status`` field.

.. code-block:: python
    :caption: **Response body**

    {"status": "running", "exception_message": null, "exception_stack": null}

.. _checking-execution-status:

Check execution status with the client library
--------------------------------------------------
To check the execution status of a transaction method using the Python client, you can use the ``get_method_state()`` class method. This class method works for both regular and long-running methods.

.. code:: python

    status = step.get_method_state("start_solver_product").status
    assert status == MethodStatus.Completed

To check the execution status of a long-running method using the Python client, you can use the ``LongRunning`` return value of the method.

.. code-block:: python

    long_running = step.start_solver_product()
    method_state = long_running.get_state()

    assert method_state.status == MethodStatus.Completed

It is also possible to verify if the long-running method is complete by using ``is_complete`` on the ``LongRunning`` return value.
If the parameter ``raise_for_error`` is ``True``, then a ``MethodException`` is raised if the long-running method has failed.

.. code:: python

    long_running = step.start_solver_product()
    is_method_complete = long_running.is_complete(raise_for_error=True)


An alternative method is to check the execution status using the
``get_long_running_method_state()`` class method.

.. code:: python

    status = step.get_long_running_method_state("start_solver_product").status

    assert status == MethodStatus.Completed

.. _wait-for-long-running:


Wait for a long-running method to complete with the client library
---------------------------------------------------------------------

To wait for the long-running method to be complete, you can use the ``wait`` method on the ``LongRunning`` return value of the method.

The following code waits for 60 seconds before the long-running method ``start_solver_product`` terminates.
If the method takes longer than the specified timeout, then a ``TimeoutError`` exception is raised.
It is safe to catch this exception and retry the wait.

.. code:: python

    long_running = step.start_solver_product()
    long_running.wait(timeout=60)


.. _child_process_cleanup:

Child process cleanup
========================

Long-running transaction methods run in a separate worker process. Code within these methods may spawn
additional child processes. After the transaction method completes, SAF GLOW Engine  inspects the worker process tree to
detect any child processes that are still alive.

The behavior for those surviving child processes is controlled by the :envvar:`GLOW_METHOD_CLEANUP_CHILD_PROCS`
environment variable:

- When set to ``True`` (default), SAF GLOW Engine  collects the PIDs of all child processes of the worker process at the
  end of the transaction, checks which ones are still alive, and terminates them.
- When set to ``False``, child processes are **not** killed. Instead, a warning is logged listing the PIDs that
  are still alive.
