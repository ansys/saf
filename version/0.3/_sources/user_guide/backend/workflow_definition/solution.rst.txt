.. _solution_definition:

Solution definition
###################

The solution itself is defined using a class that inherits from the ``Solution`` base class (imported from ``ansys.saf.glow.solution``).
Instances of this ``Solution`` subclass are referred to as ":dfn:`projects`" of this particular solution.

.. warning::
  Changing the solution subclass name will render old projects inoperable.

Fields that must be defined on a ``Solution`` subclass
======================================================

At minimum, the ``Solution`` subclass must have the following fields, which use the ``name: type`` syntax:

``display_name``
  String that specifies the display name shown in the SAF Portal header, the OpenAPI documentation, etc.

``version``
  Integer that specifies the version of the solution.

``steps``
  Specifies the ``Steps`` class used to group the solution steps.

The following is an example of a minimal solution definition:

.. code-block:: python
    :caption: ``minimal\solution\definition.py``

    class MinimalSolution(Solution):
        display_name: str = "Minimal Solution"
        version: int = 1
        steps: Steps

The :ref:`steps page <step_models>` describes how to define the ``Steps`` class and the step classes used in a solution.

Optional fields of the ``Solution`` subclass
============================================

There are two more fields that are optional and also use ``name: type`` syntax. To know more about them, check the corresponding sections: :ref:`solution configuration <solution_configuration>`
and :ref:`project migration API <project_migration>`.

``solution_configuration``
  Object of the class ``SolutionConfiguration`` or a subclass of it that specifies the solution configuration to be used in the Solution.

.. code-block:: python
    :caption: ``solution_with_configuration\solution\definition.py``

    class SolutionWithConfig(Solution):
        display_name: str = "Solution with Configuration"
        version: int = 1
        steps: Steps
        solution_configuration: MySolutionConfiguration = MySolutionConfiguration()

``migrations``
  List of objects of the ``Migration`` class. This class links a ``MigrationTransformation`` to the solution definition version it has to be applied to.
  A ``MigrationTransformation`` defines the modifications needed to migrate a project from a specific version of the solution definition to the next one.

.. code-block:: python
    :caption: ``solution_with_migrations\solution\definition.py``

    class MigrateToVersion2(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            # Modifications needed to migrate a project from solution definition version 1 to version 2.
            ...


    class MigrateToVersion3(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            # Modifications needed to migrate a project from solution definition version 2 to version 3.
            ...


    class SolutionWithConfig(Solution):
        display_name: str = "Solution with Configuration"
        version: int = 1
        steps: Steps
        migrations: list[Migration] = [
            Migration(version=1, migration_transformation=MigrateToVersion2()),
            Migration(version=2, migration_transformation=MigrateToVersion3()),
        ]

.. note::
    These field names are defined by GLOW and cannot be changed.
