.. _solution_rest_api:

Solution REST API
#################

SAF GLOW Engine's **Solution API** server serves a REST API derived from a given solution that exposes a view of project data and enables transaction methods to be executed.

The GLOW API server's responsibilities include:

* Reading and writing project data to / from project storage
* Starting method execution
* Recording state management information about fields, methods, and product instances


Interactive API
===============

The **Solution API** server implements a solution-specific **REST API** that is consumed by the Solution UI server (a Dash UI server by default, and potentially other clients) and exposed in a documented, interactive **OpenAPI UI**.

.. note::
  The OpenAPI UI is intended for use by solution developers and dev-ops. Solution end-users are not expected to access this UI.


.. _user_guide_backend_solution_rest_api:

Access the OpenAPI UI
---------------------

To access the REST API UI:

1. After running ``glow_engine api``, review the console output.
2. Find the line containing ``Running GLOW API server on``.

   The URL on this line is address of the Solution API server.

3. Enter the URL into your browser and append ``/docs`` to it.

The UI that opens enables invocation of the REST API, providing a mechanism both for testing and diagnosing issues in the running solution and for documenting the API.


Invoke a route in the OpenAPI UI
--------------------------------

To invoke a particular route using OpenAPI:

1. Navigate to the route of interest.
2. Expand the route.
3. Click the :guilabel:`Try it out` button.

.. figure:: /_static/images/openapi.png
