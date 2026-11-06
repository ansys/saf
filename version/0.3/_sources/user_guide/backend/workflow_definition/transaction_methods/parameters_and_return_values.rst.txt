.. _parameters_and_return_values:

Method parameters and return values
###########################################

As explained earlier, the transaction method can access and modify data persisted in the project by using the ``StepSpec()`` annotation.

If you need to send data from a client or solution UI straight to the transaction method, you can declare dedicated parameters.
Similarly, the returned value of the transaction method can be received straight in the UI.

.. code:: python

    @transaction(self=StepSpec())
    def say_hello(self, name: str) -> str:
        return f"hello {name}!"

You must declare the type of the parameters in the method, using standard Python type annotations.
If the method returns something, the return type annotation must also be specified.

SAF GLOW Engine will use the type annotation to:

- Validate the data sent by the client and raise an explicit exception if the data is invalid.
- Validate the response.
- Generate the OpenAPI interactive API docs.

.. note::
    The type annotations can be a dict, list, singular values as ``str``, ``int``, but also a complete Pydantic model.


Execute a method with parameters
================================

To execute ``say_hello``, the input ``name`` must be sent as a request body for HTTP request:

.. code:: text

    POST http://127.0.0.1:5432/projects/654a1c3787c99c7ef02fbdc6/steps/my-step:say-hello
    {
      "name": "foobar"
    }

    > Response: "hello foobar!"


or using keyword arguments in the Python client:

.. code-block:: python

    @callback(
        State("url", "pathname"),
    )
    def say_hello(project: SimpleSolution):
        # keyword argument is mandatory!
        response = project.steps.my_step.say_hello(name="foobar")
        assert response == "hello foobar!"

.. warning::
    Only keyword arguments are supported. Using positional argument will fail.


Method parameter types
=======================

You can use standard type annotations such as lists, dictionaries, scalar values like integers, booleans, etc.
But you can also use Pydantic models or Pydantic ``Field`` to further customize the validation of the input and output data.

.. code:: python

    from pydantic import BaseModel, Field


    class User(BaseModel):
        name: str


    @transaction(self=StepSpec())
    def example_types(self, name: str, short_str: Annotated[str, Field(max_length=3)], optional: int | None = None) -> User:
        return User(name=name)


Combine input data and persisted data
=======================================

You can also persist input data by setting the given value to a step field and using ``StepSpec(upload=["step_field"])``:

.. code:: python

    class TransactionStep(StepModel):
        last_name: str = ""

        @transaction(self=StepSpec(upload=["last_name"]))
        def say_hello(self, name: str) -> str:
            self.last_name = name
            return f"hello {name}!"





