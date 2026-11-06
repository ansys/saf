.. _troubleshooting_backend_operations:

Backend operations
##################

This section covers common issues and solutions related to the backend operations of a solution application built with SAF.


Transaction method execution setup fails when creating a temporary directory
============================================================================

**Problem**:
 A transaction method execution fails with a permissions error, with ``transaction_step_method`` calling
 ``tempfile.mkdtemp``. A temporary directory is not created.

**Solution**:
 Create a directory in which temporary directories can be created and set the
 :envvar:`GLOW_METHOD_EXECUTION_DIRECTORY` environment variable to point to it.


Transaction method request returns a 500 error
==============================================

**Problem**:
 A client makes a ``POST`` request to invoke a transaction method at the wrong time or with incorrect data, and
 the method throws an exception. The request returns a 500 error.

**Cause**:
 The 500 error is not the correct response, because the client has made the mistake.

**Solution**:
 Within the transaction method, detect the error (perhaps by handling the exception that is currently raised) and
 raise a ``ansys.saf.glow.solution.BadRequestError`` exception. This ensures that the ``POST`` response has a 400
 status code.


No detail on internal error exception
=====================================

**Problem**:
 No detail is provided with the following exception:

 .. code-block:: text

     The solution encountered an internal error and was unable to complete the request

**Cause**:
 This issue occurs when a Python exception (which is not a SAF GLOW Engine exception) is thrown. The lack of details is by
 design, because those exceptions are actually bugs in your code. You don't want the users to have access to
 these details, as that could expose a security vulnerability.

**Solution**:
 Running the solution in debug mode (:envvar:`GLOW_DEBUG="True"`) gives the ability to see the details of those
 internal errors. This should only be used while developing the solution.


GLOW becomes unresponsive during AEDT solve
===========================================

**Problem**:
 In desktop mode, running the PyAEDT ``analyze`` or ``analyze_setup`` method in a ``@transaction`` method causes
 the solution to hang while AEDT is solving. Once the solve is done, the solution resumes.

 .. code-block:: python

     @transaction(self=StepSpec())
     @long_running
     @instance("maxwell_2d_instance")
     def run_maxwell_analyze(self, maxwell_2d_instance: Maxwell2DManager):
         maxwell_2d_instance.instance.analyze_setup(setup_name)

**Cause**:
 This is a known AEDT limitation.

**Solution**:
 If the solution is using AEDT 2023 R2, replace ``analyze_setup()`` with ``analyze(setup_name, blocking=False)``.
 Using the ``blocking=False`` option launches the analysis and releases the command, therefore not blocking SAF GLOW Engine.
 You need to check when the simulation ends via another command—for example, in another transaction—to
 continue the workflow.

 If the solution is using an older version of AEDT, use ``solve_in_batch=True`` combined with
 ``run_in_thread=True`` in ``analyze(setup_name, solve_in_batch=True, run_in_thread=True)``.


Deleting a project or a product instance does not shut down the product instance in HPS
=======================================================================================

**Problem**:
 A desktop deployment uses Keycloak-based authentication and the HPS authentication has not yet been triggered by
 any means (via transaction, Client API, and so on). Although the request returns success, a warning message is
 logged informing the user that the product instance has not been removed from HPS.

**Solution**:
 Manually remove the product instances using the HPS Dashboard, or trigger the authentication before deleting the
 project or instance (for example, by launching a transaction that uses the instance).


Deleting a project does not stop jobs or parametric studies in HPS
==================================================================

**Problem**:
 A desktop deployment uses Keycloak-based authentication and the HPS authentication has not yet been triggered by
 any means (via transaction, Client API, and so on). Although the request returns success, a warning message is
 logged informing the user that the job or parametric study instance has not been stopped in HPS.

**Solution**:
 Manually stop the jobs or parametric studies using the HPS Dashboard, or trigger the authentication before
 deleting the project (for example, by launching a transaction that interacts with HPS).


Requests made within a Dash background callback are unauthenticated
===================================================================

**Problem**:
 The authorization header present in the original request made to open the Dash app is not passed to the
 background callback. Therefore, requests made within the callback to other services (for example, the GLOW API
 server) are unauthenticated.
