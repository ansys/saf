.. _execution_from_client:

Execute a method
################

The transaction method can be executed using an HTTP request:

.. code:: text

    POST http://127.0.0.1:5432/projects/654a1c3787c99c7ef02fbdc6/steps/username-step:generate-username

or by using the Python client:

.. code-block:: python

    @callback(
        State("url", "pathname"),
    )
    def generate_username(project: SimpleSolution):
        project.steps.username_step.generate_username()

