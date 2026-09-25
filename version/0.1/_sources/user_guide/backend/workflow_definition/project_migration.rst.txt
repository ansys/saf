.. _project_migration:


Project migration API
#####################

The project migration API provides the means to transform a project that was created from an old version of a solution (an outdated project) so that it adjusts
to the latest version of this solution. The project migration process is triggered when the project is either imported or upgraded: trying to directly use an
outdated project might result in a ``422 UnprocessableEntityError``.

.. note::

    The migrations defined using the project migration API are always applied before the :ref:`automatic project migrations <upgrade-supported-modifications>` that the
    ``Solution`` class offers by default. These automatic project migrations are only active when :envvar:`GLOW_ENABLE_AUTOMATIC_PROJECT_MIGRATION` is set, and should
    only be used during development, never in production environments.

.. warning::

    The solution's ``version`` field MUST be increased when using the project migration API.

Project migration overview
===========================

The project migration API allows the manipulation of the values stored in the project we are migrating, and it also gives access to the project's files directory.
We can use this to:

1. change the value of a step's field of the project (normally to match the default value defined in the latest solution version),
2. change the value of a step's field of the project based on another field,
3. change a step's field type EVEN if the project value cannot be cast to the new type, and
4. create or access directories and files inside the project's files directory.

The project migration API includes the following 3 classes:

.. vale off

- :py:class:`~ansys.saf.glow.solution.MigrationTransformation`
- :py:class:`~ansys.saf.glow.solution.MigrationContext`
- :py:class:`~ansys.saf.glow.solution.Migration`

.. vale on

The ``MigrationTransformation`` class has a single method ``migrate`` that must include the logic to migrate the project from version ``n`` to version
``n + 1``. It accepts a ``ctx`` argument of type ``MigrationContext``. To create a migration transformation, define a subclass of ``MigrationTransformation`` and
implement its ``migrate`` method. This subclass can be defined directly in the solution definition or imported there from somewhere else, and must be linked to a
particular solution version through the class ``Migration``. A solution definition may include an arbitrary number of migration transformations.

.. code-block:: python

    class MigrateToVersion2(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            ctx.steps["first_step"]["x"] = 100

The ``MigrationContext`` class has access to the project to migrate in dictionary form and its files directory. The solution fields and steps can easily be accessed
through the ``solution`` and ``steps`` properties, respectively, and the path to the project's files directory can be accessed through the ``project_directory`` property.

.. code-block:: python

    class MigrateToVersion2(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            ctx.steps["first_step"]["x"] = 100
            input_file = ctx.project_directory / "input.txt"
            input_file.write_text(f"Hello world from solution {ctx.solution["display_name"]}")

The ``Migration`` class links a ``MigrationTransformation`` to the solution version it has to be applied to. All the necessary ``Migrations`` must be listed in
the ``migrations`` field of the ``Solution`` subclass.

.. code-block:: python

    class MySolution(Solution):
        version: int = 5
        display_name: str = "My Solution"
        steps: Steps
        migrations: list[Migration] = [
            Migration(version=1, migration_transformation=MigrateToVersion2()),
            Migration(version=2, migration_transformation=MigrateToVersion3()),
            Migration(version=3, migration_transformation=MigrateToVersion4()),
            Migration(version=4, migration_transformation=MigrateToVersion5()),
        ]

.. note::

    The ``Migrations`` listed in the ``migrations`` field must be ordered by the version of the solution to which its ``MigationTransformation`` is to be applied to.
    These versions must therefore form an strictly increasing sequence of integers (in the example above: 1, 2, 3, 4):
    - higher or equal than 1,
    - reaching up to the current solution version minus 1, and
    - containing no gaps.

.. warning::

    It is mandatory to increase the version of the solution when adding migration transformations to the solution definition.


Project migration examples
==========================

This section describes how to modify a solution definition to successfully migrate outdated projects to their latest solution version. The following examples present
updated solution definitions with respect to an initial solution definition. Thanks to the creation of one or more migration transformations, all of them are able
to migrate a project created from the initial solution definition to the latest solution version.

The initial version of the solution definition is as follows:

.. code:: python

    class FirstStep(StepModel):
        x: int = 88
        my_string: str = "my_string"
        unused_float: float = 0.5
        str_int: str = "1"


    class SecondStep(StepModel):
        y: int = 50
        results: dict[str, int] = {}
        results_file: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(download=["y"], upload=["results", "results_file"]))
        def compute_results(self, input_value: int) -> None:
            self.results = {
                "addition": self.y + input_value,
                "subtraction": self.y - input_value,
            }
            filepath = self.storage_scope.get_storage_root() / "result.txt"
            filepath.write_text(f"{self.y + input_value}")
            self.results_file = self.storage_scope.store(filepath)


    class Steps(StepsModel):
        first_step: FirstStep
        second_step: SecondStep


    class MySolution(Solution):
        version: int = 1  # This is the default version value. Adding the field here for clarity.
        display_name: str = "My Solution"
        steps: Steps


Example 1: Change the value of a step's field of the project
------------------------------------------------------------

.. code-block:: python

    class MigrateToVersion2(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            # Changing the value of 'x' stored in the outdated project to a new value that matches the current solution definition.
            ctx.steps["first_step"]["x"] = 100


    class FirstStep(StepModel):
        x: int = 100
        my_string: str = "my_string"
        unused_float: float = 0.5
        str_int: str = "1"


    class SecondStep(StepModel):
        y: int = 50
        results: dict[str, int] = {}
        results_file: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(download=["y"], upload=["results", "results_file"]))
        def compute_results(self, input_value: int) -> None:
            self.results = {
                "addition": self.y + input_value,
                "subtraction": self.y - input_value,
            }
            filepath = self.storage_scope.get_storage_root() / "result.txt"
            filepath.write_text(f"{self.y + input_value}")
            self.results_file = self.storage_scope.store(filepath)


    class Steps(StepsModel):
        first_step: FirstStep
        second_step: SecondStep


    class MySolution(Solution):
        version: int = 2
        display_name: str = "My Solution"
        steps: Steps
        migrations: list[Migration] = [Migration(version=1, migration_transformation=MigrateToVersion2())]


Example 2: Change the value of a step's field of the project based on another field
-----------------------------------------------------------------------------------

.. code-block:: python

    class MigrateToVersion2(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            addition = ctx.steps["second_step"]["results"]["addition"]
            subtraction = ctx.steps["second_step"]["results"]["subtraction"]
            input_value = int((addition - subtraction) / 2)
            # Changing the value of 'results' stored in the outdated project to include 'multiplication'
            # so that get_multiplication() can be called safely.
            ctx.steps["second_step"]["results"]["multiplication"] = ctx.steps["second_step"]["y"] * input_value


    class FirstStep(StepModel):
        x: int = 88
        my_string: str = "my_string"
        unused_float: float = 0.5
        str_int: str = "1"


    class SecondStep(StepModel):
        y: int = 50
        results: dict[str, int] = {}
        results_file: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(download=["y"], upload=["results", "results_file"]))
        def compute_results(self, input_value: int) -> None:
            self.results = {
                "addition": self.y + input_value,
                "subtraction": self.y - input_value,
                "multiplication": self.y * input_value,
            }
            filepath = self.storage_scope.get_storage_root() / "result.txt"
            filepath.write_text(f"{self.y + input_value}")
            self.results_file = self.storage_scope.store(filepath)

        @transaction(self=StepSpec(download=["results"]))
        def get_multiplication(self) -> int:
            return self.results["multiplication"]


    class Steps(StepsModel):
        first_step: FirstStep
        second_step: SecondStep


    class MySolution(Solution):
        version: int = 2
        display_name: str = "My Solution"
        steps: Steps
        migrations: list[Migration] = [Migration(version=1, migration_transformation=MigrateToVersion2())]


Example 3: Change a step's field type EVEN if the project value cannot be cast to the new type
----------------------------------------------------------------------------------------------

.. code-block:: python

    class MigrateToVersion2(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            # Changing the value of 'my_string' stored in the outdated project to a value of a type that the old
            # field's default value cannot be cast to.
            ctx.steps["first_step"]["my_string"] = 50


    class FirstStep(StepModel):
        x: int = 88
        my_string: int = 50
        unused_float: float = 0.5
        str_int: str = "1"


    class SecondStep(StepModel):
        y: int = 50
        results: dict[str, int] = {}
        results_file: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(download=["y"], upload=["results", "results_file"]))
        def compute_results(self, input_value: int) -> None:
            self.results = {
                "addition": self.y + input_value,
                "subtraction": self.y - input_value,
            }
            filepath = self.storage_scope.get_storage_root() / "result.txt"
            filepath.write_text(f"{self.y + input_value}")
            self.results_file = self.storage_scope.store(filepath)


    class Steps(StepsModel):
        first_step: FirstStep
        second_step: SecondStep


    class MySolution(Solution):
        version: int = 2
        display_name: str = "My Solution"
        steps: Steps
        migrations: list[Migration] = [Migration(version=1, migration_transformation=MigrateToVersion2())]


Example 4: Apply more than one migration
----------------------------------------

.. code-block:: python

    class MigrateToVersion2(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            ctx.steps["first_step"]["x"] = 100


    class MigrateToVersion3(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            ctx.steps["first_step"]["my_string"] = 50


    class FirstStep(StepModel):
        x: int = 100
        my_string: int = 50
        unused_float: float = 0.5
        str_int: str = "1"


    # Removing step SecondStep


    class Steps(StepsModel):
        first_step: FirstStep


    class MySolution(Solution):
        version: int = 3
        display_name: str = "My Solution"
        steps: Steps
        migrations: list[Migration] = [
            Migration(version=1, migration_transformation=MigrateToVersion2()),
            Migration(version=2, migration_transformation=MigrateToVersion3()),
        ]

.. note::

    ``Migrations`` are ordered by their version field forming a sequence of strictly increasing integers no lower than 1, without gaps, and that reaches up to the
    current version minus 1.

.. note::

    We have also removed SecondStep to show that the project migration API can be combined with the ``Solution`` class automatic updating functionalities.
    Remember that the changes applied through a ``MigrationTransformation`` are applied BEFORE the ``Solution`` class automatic update.


Example 5: Create or access files and directories in the project's files directory
----------------------------------------------------------------------------------

.. code-block:: python

    class MigrateToVersion2(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            input_file = ctx.project_directory / "input.txt"
            input_file.write_text("Crucial input information for version 2.")


    class FirstStep(StepModel):
        x: int = 88
        my_string: str = ""
        unused_float: float = 0.5
        str_int: str = "1"


    class SecondStep(StepModel):
        y: int = 50
        results: dict[str, int] = {}
        results_file: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(download=["y"], upload=["results", "results_file"]))
        def compute_results(self, input_value: int) -> None:
            self.results = {
                "addition": self.y + input_value,
                "subtraction": self.y - input_value,
            }
            filepath = self.storage_scope.get_storage_root() / "result.txt"
            filepath.write_text(f"{self.y + input_value}")
            self.results_file = self.storage_scope.store(filepath)


    class Steps(StepsModel):
        first_step: FirstStep
        second_step: SecondStep


    class MySolution(Solution):
        version: int = 2
        display_name: str = "My Solution"
        steps: Steps
        migrations: list[Migration] = [Migration(version=1, migration_transformation=MigrateToVersion2())]

Example 6: Remove a field from a step
-------------------------------------

.. code:: python

    class MigrateToVersion2(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            del ctx.steps["first_step"]["x"]


    class FirstStep(StepModel):
        my_string: str = "my_string"
        unused_float: float = 0.5
        str_int: str = "1"


    class SecondStep(StepModel):
        y: int = 50
        results: dict[str, int] = {}
        results_file: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(download=["y"], upload=["results", "results_file"]))
        def compute_results(self, input_value: int) -> None:
            self.results = {
                "addition": self.y + input_value,
                "subtraction": self.y - input_value,
            }
            filepath = self.storage_scope.get_storage_root() / "result.txt"
            filepath.write_text(f"{self.y + input_value}")
            self.results_file = self.storage_scope.store(filepath)


    class Steps(StepsModel):
        first_step: FirstStep
        second_step: SecondStep


    class MySolution(Solution):
        version: int = 2
        display_name: str = "My Solution"
        steps: Steps
        migrations: list[Migration] = [Migration(version=1, migration_transformation=MigrateToVersion2())]

Example 7: Remove a file from a project by removing the field that refers to it
-------------------------------------------------------------------------------

.. code:: python

    class MigrateToVersion2(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            del ctx.steps["second_step"]["results_file"]


    class FirstStep(StepModel):
        x: int = 88
        my_string: str = "my_string"
        unused_float: float = 0.5
        str_int: str = "1"


    class SecondStep(StepModel):
        y: int = 50
        results: dict[str, int] = {}

        @transaction(self=StepSpec(download=["y"], upload=["results"]))
        def compute_results(self, input_value: int) -> None:
            self.results = {
                "addition": self.y + input_value,
                "subtraction": self.y - input_value,
            }


    class Steps(StepsModel):
        first_step: FirstStep
        second_step: SecondStep


    class MySolution(Solution):
        version: int = 2
        display_name: str = "My Solution"
        steps: Steps
        migrations: list[Migration] = [Migration(version=1, migration_transformation=MigrateToVersion2())]


Example 8: Remove a file from a project by setting the field to NO_ENTITY
-------------------------------------------------------------------------


.. code:: python

    class MigrateToVersion2(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            ctx.steps["second_step"]["results_file"] = NO_ENTITY


    class FirstStep(StepModel):
        x: int = 88
        my_string: str = "my_string"
        unused_float: float = 0.5
        str_int: str = "1"


    class SecondStep(StepModel):
        y: int = 50
        results: dict[str, int] = {}
        results_file: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(download=["y"], upload=["results", "results_file"]))
        def compute_results(self, input_value: int) -> None:
            self.results = {
                "addition": self.y + input_value,
                "subtraction": self.y - input_value,
            }
            filepath = self.storage_scope.get_storage_root() / "result.txt"
            filepath.write_text(f"{self.y + input_value}")
            self.results_file = self.storage_scope.store(filepath)


    class Steps(StepsModel):
        first_step: FirstStep
        second_step: SecondStep


    class MySolution(Solution):
        version: int = 1  # This is the default version value. Adding the field here for clarity.
        display_name: str = "My Solution"
        steps: Steps
        migrations: list[Migration] = [Migration(version=1, migration_transformation=MigrateToVersion2())]

Example 9: Add a file to a project by setting an existing field to refer a file
----------------------------------------------------------------------------------

.. code:: python

    class MigrateToVersion2(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_file = Path(temp_dir) / "new_file.txt"
                temp_file.write_text("99")
                ctx.steps["second_step"]["results_file"] = ctx.create_entity_handle(temp_file)


    class FirstStep(StepModel):
        x: int = 88
        my_string: str = "my_string"
        unused_float: float = 0.5
        str_int: str = "1"


    class SecondStep(StepModel):
        y: int = 50
        results: dict[str, int] = {}
        results_file: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(download=["y"], upload=["results", "results_file"]))
        def compute_results(self, input_value: int) -> None:
            self.results = {
                "addition": self.y + input_value,
                "subtraction": self.y - input_value,
            }
            filepath = self.storage_scope.get_storage_root() / "result.txt"
            filepath.write_text(f"{self.y + input_value}")
            self.results_file = self.storage_scope.store(filepath)


    class Steps(StepsModel):
        first_step: FirstStep
        second_step: SecondStep


    class MySolution(Solution):
        version: int = 1  # This is the default version value. Adding the field here for clarity.
        display_name: str = "My Solution"
        steps: Steps
        migrations: list[Migration] = [Migration(version=1, migration_transformation=MigrateToVersion2())]


Example 10: Add a file to a project by adding a new field that refers to a file
----------------------------------------------------------------------------------

.. code:: python

    class MigrateToVersion2(MigrationTransformation):

        def migrate(self, ctx: MigrationContext):
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_file = Path(temp_dir) / "new_file.txt"
                temp_file.write_text("99")
                ctx.steps["second_step"]["another_results_file"] = ctx.create_entity_handle(temp_file)


    class FirstStep(StepModel):
        x: int = 88
        my_string: str = "my_string"
        unused_float: float = 0.5
        str_int: str = "1"


    class SecondStep(StepModel):
        y: int = 50
        results: dict[str, int] = {}
        results_file: EntityHandle = NO_ENTITY
        another_results_file: EntityHandle = NO_ENTITY

        @transaction(self=StepSpec(download=["y"], upload=["results", "results_file"]))
        def compute_results(self, input_value: int) -> None:
            self.results = {
                "addition": self.y + input_value,
                "subtraction": self.y - input_value,
            }
            filepath = self.storage_scope.get_storage_root() / "result.txt"
            filepath.write_text(f"{self.y + input_value}")
            self.results_file = self.storage_scope.store(filepath)


    class Steps(StepsModel):
        first_step: FirstStep
        second_step: SecondStep


    class MySolution(Solution):
        version: int = 1  # This is the default version value. Adding the field here for clarity.
        display_name: str = "My Solution"
        steps: Steps
        migrations: list[Migration] = [Migration(version=1, migration_transformation=MigrateToVersion2())]

