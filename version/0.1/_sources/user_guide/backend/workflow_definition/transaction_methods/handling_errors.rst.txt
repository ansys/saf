.. _handling_errors:

Handle errors
###############

When developing a solution, there are situations in which you need to provide a notification that a client using the solution encountered an error.

.. note::
    The "client" could be the solution UI written in Dash, but it could also be a browser with a frontend, a script, an so on.

What you need to tell the client depends on the cause of the error:

- The item the client was trying to access doesn't exist.
- The data sent by the client to the solution are invalid.
- The client is using the solution in an invalid way.
- The client doesn't have enough privileges for that operation.
- And so on.




Use SAF GLOW Engine exceptions
================================

Use SAF GLOW Engine exceptions to return an appropriate error to the client when executing a transaction method. The most common exceptions are:

.. list-table::
    :header-rows: 1

    * - Exception
      - Description
      - Example
    * - ``BadRequestError``
      - The request sent by the client is invalid.
      - A ``@transaction`` method has been called too early or the data used by the ``@transaction`` method are invalid.

    * - ``NotFoundError``
      - The item the ``@transaction`` method was trying to access is missing.
      - A client is executing a ``@transaction`` method that needs a specific file, but the file hasn't been uploaded yet.

.. rubric:: Example

In this example, the SAF GLOW Engine  exceptions thrown by the ``@transaction`` method mean that there was an error from the client.

However, a standard Python exception raised during the execution of a ``@transaction`` method means that there was an error from the solution itself.


.. code-block:: python

    from ansys.bdm.api import NO_ENTITY, EntityHandle
    from ansys.saf.glow.solution import BadRequestError, NotFoundError


    class ExceptionsStep(StepModel):
        status: str = "busy"
        my_solve_file: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(download=["status"]))
        def solve_if_status_not_busy(self):
            if self.status == "busy":
                raise BadRequestError("Cannot execute this transaction while the status is pending.")
            solve()

        @transaction(self=StepSpec(download=["my_solve_file"]))
        def process_solve_file(self):
            if self.my_solve_file == NO_ENTITY:
                raise NotFoundError("The solve file cannot be found. Please upload it first.")
            ...

        @transaction(self=StepSpec(download=["my_solve_file"]))
        def internal_error_thrown(self):
            raise Exception("This error won't be seen by the client. A 500 Internal Server Error will be shown instead.")


Responses
=============

When those ``@transaction`` methods are executed from the REST API, the client receives an HTTP status code and a detailed JSON response in one of the following errors:

Error: Bad Request
 .. code-block:: JSON

     {
       "detail": "Cannot execute this transaction while the status is pending."
     }

404: Error: Not Found
 .. code-block:: JSON

     {
       "detail": "The file 'solve_file.dat' cannot be found. Please upload it again."
     }


If a standard Python ``Exception`` is raised within a ``@transaction`` method, the client will not see the original error message. Instead, the client receives a generic ``500 Internal Server Error``.

The purpose behind this design is as follows: If a Python exception is thrown in your code that does not originate from the client request, it actually indicates a bug in your code. While you fix it, your clients shouldn't have access to internal information about the error, as that could expose a security vulnerability.

500: Error: Internal Server Error
 .. code-block:: JSON

     {
       "detail": "The solution encountered an internal error and was unable to complete the request. More information about this error may be available in the server error log."
     }

Solution developers have the ability to view full internal error messages, either within the log files or by running the solution in debug mode.
