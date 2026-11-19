.. _step_models:

Step models
###########

The steps of the solution are typically associated with the pages of the solution app UI. A step is defined in a step definition file, which must include at least one field and can include one or more methods.

When you create a solution by invoking the ``ansys-templates`` tool's ``new solution`` command, two step definition template files are created in the ``<solution name>/src/ansys/solutions/<solution name>/solution`` directory:

* ``first_step.py``
* ``other_step.py``

.. note::
    For the sake of clarity, this documentation assumes that steps are defined individually, each in a separate module. However, you can adjust the structure of your solution definition as needed. For example, the steps for a simple solution could all be defined in a single file.

.. _defining-step:

Define a step
==============

Define a solution step as a class with inheritance from the ``StepModel`` base class (imported from ``ansys.saf.glow.solution``). For example, the template files ``first_step.py`` and ``other_step.py`` define the step classes ``FirstStep`` and ``OtherStep``, respectively.

At minimum, each step must have at least one field. Each field must have a name, type, and default value defined using the following syntax: ``name: type = value``

.. note::
    Internally, step fields are defined using Pydantic, so you can use `all the field types available from Pydantic <https://docs.pydantic.dev/2.1/usage/types/types/>`_ and use Pydantic practices to implement your own types.

For the ``minimal`` sample solution, the step definition in shown below defines the step class ``MinimalStep``. This class has a single field named ``x``, with type ``int`` and a default value of ``99``.

.. code-block:: python
    :caption: ``minimal\solution\minimal_step.py``

    from ansys.saf.glow.solution import StepModel


    class MinimalStep01(StepModel):
        x: int = 99


If a field has no default value, then you must designate it as ``Optional``. For example, in the step class ``NoDefaultStep``, the ``optional_thing`` field has a type of ``str`` and no default value.

.. code-block:: python
    :caption: ``minimal\solution\no_default_step.py``

    from ansys.saf.glow.solution import StepModel


    class NoDefaultStep(StepModel):
        x: int = 99
        name: str = "Field Name"
        optional_thing: Optional[str]


If you want to declare a custom field type, it can be done by inheriting from Pydantic's ``BaseModel``.

.. code-block:: python
    :caption: ``minimal\solution\custom_type.py``

    from ansys.saf.glow.solution import StepModel
    from pydantic import BaseModel


    class CustomType(BaseModel):
        x: int
        y: int
        z: int


    class CustomTypeStep(StepModel):
        custom_type: CustomType = CustomType(x=1, y=2, z=3)

Additional examples are available in Pydantic's `Models <https://docs.pydantic.dev/2.1/usage/models/>`_ documentation.


In development mode, the type of a field may change. Every project created before the change cannot be run again, as Pydantic will find a conflict. More generally, every time a change is
brought to a step class, Ansys recommends that you start with a fresh project.

.. _adding-steps-to-solution:

Add steps to a solution
========================

Add steps to a solution using a ``Steps`` class with inheritance from the ``StepsModel`` base class (imported from ``ansys.saf.glow.solution``).

At minimum, the ``Steps`` class must have at least one field. Each field maps the name of a given step to the type of that step (the step class) using the following syntax:  ``name: type``

Add a field for each of the steps defined for the solution.

The ``Steps`` class shown below includes fields for the two template steps provided.

.. code-block::
    :caption: ``minimal\solution\definition.py``

    class Steps(StepsModel):
        first_step: FirstStep
        other_step: OtherStep


Note that the step name must be unique, but the type can be reused. For example, in the code sample below, there are two steps with type ``FirstStep``.

.. code-block::
    :caption: ``minimal\solution\definition.py``

    class Steps(StepsModel):
        first_step: FirstStep
        other_step: OtherStep
        miniimal_step: MinimalStep
        no_default_step: NoDefaultStep
        duplicate_type_step: FirstStep
        last_step: LastStep

