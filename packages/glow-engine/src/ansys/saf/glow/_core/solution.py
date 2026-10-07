# Copyright (C) 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0
#
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from abc import ABC
from contextlib import contextmanager
from functools import cache
import logging
import shutil
import traceback
from typing import TYPE_CHECKING, Any, BinaryIO, ClassVar, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    field_validator,
    model_validator,
)

from ansys.saf.glow._config.const import INSTANCES_USED_BY_METHOD_ATTRIBUTE_STRING
from ansys.saf.glow._core.dag import DependencyGraph
from ansys.saf.glow._core.exceptions import SolutionLoadException
from ansys.saf.glow._core.migrations import Migration, MigrationContext
from ansys.saf.glow._core.state_engine import initialize_states
from ansys.saf.glow._core.step_model import StepModel
from ansys.saf.glow._server.exceptions import MalformedSolutionError

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from pathlib import Path
    from typing import Self

    from ansys.bdm.api import EntityHandle, IStorageScope

logger = logging.getLogger(__name__)


class MethodIdentifier:
    """A reference to a transaction method in a :py:class:`~ansys.saf.glow.solution.Solution` derived class.

    Parameters
    ----------
    step_name : str
        Name of the step containing the method. A 'step' is a field on a
        :py:class:`~ansys.saf.glow.solution.StepsModel` derived class.
        The name of a step is the name of the field. The :py:class:`~ansys.saf.glow.solution.StepsModel` derived
        class is the type of the :py:class:`~ansys.saf.glow.solution.Solution.steps` field which defines the set
        of steps in a :py:class:`~ansys.saf.glow.solution.Solution` derived class.

    method_name : str
        The Python identifier of the method on the step.

    Notes
    -----
    |saf-docs-transaction-methods-ref|_ explains the transaction method concept in
    more detail.
    """

    def __init__(self, step_name: str, method_name: str) -> None:
        self._step_name = step_name
        self._method_name = method_name

    def __hash__(self) -> int:
        return self._step_name.__hash__() * 7 + self._method_name.__hash__()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, MethodIdentifier):
            return self._step_name == other._step_name and self._method_name == other._method_name
        return False

    def __repr__(self) -> str:
        return f"MethodIdentifier(step_name={self._step_name}, method_name={self._method_name})"

    @property
    def step_name(self) -> str:
        """Name of the step containing the method.

        Returns
        -------
        str
            Name of the step containing the method. A 'step' is a field on a
            :py:class:`~ansys.saf.glow.solution.StepsModel` derived class.
            The name of a step is the name of the field. The :py:class:`~ansys.saf.glow.solution.StepsModel`
            derived class is the type of the :py:class:`~ansys.saf.glow.solution.Solution.steps` field which
            defines the set of steps in a :py:class:`~ansys.saf.glow.solution.Solution` derived class.
        """
        return self._step_name

    @property
    def method_name(self) -> str:
        """Name of the method.

        Returns
        -------
        str
            Name of the method.
        """
        return self._method_name


class StepsModel(BaseModel, ABC):
    """Collection of steps for a :py:class:`~ansys.saf.glow.solution.Solution` derived class (a "Solution").
    A step is a subsection of a Solution.

    A class derived from ``StepsModel`` will define the set of steps in a Solution by containing a set of fields each
    derived from a class of :py:class:`~ansys.saf.glow.solution.StepModel`. These steps form a Solution when
    the class derived from ``StepsModel`` is the type of the :py:class:`~ansys.saf.glow.solution.Solution.steps`
    field of the Solution.

    The name of a :py:class:`~ansys.saf.glow.solution.StepModel` field is the "name" of the step. Each field can
    have, and typically has, a unique type derived from :py:class:`~ansys.saf.glow.solution.StepModel`.

    Notes
    -----
    You can read more about how a Solution is defined using ``StepsModel`` |saf-docs-step-models-ref|_.

    ``StepsModel`` is derived from the pydantic ``BaseModel`` class to enable parsing and validation of project data.
    You can read more about pydantic `here <https://docs.pydantic.dev/>`_.

    Examples
    --------
    >>> class FluidsSteps(StepsModel):
    >>>     my_step: MyStep
    >>>     my_second_step: MySecondStep
    """

    @model_validator(mode="before")
    @classmethod
    def _upgrade_steps(cls, values: dict[str, Any], info: ValidationInfo):
        if (context := info.context) and context.get("mode") in ["upgrade", "import"]:
            default_solution = context["default_solution"]

            step_names = set(cls.model_fields.keys())
            old_step_names = set(values.keys())
            obsolete_step_names = old_step_names - step_names
            new_step_names = step_names - old_step_names

            if (new_step_names or obsolete_step_names) and not context["automatic_project_migration"]:
                raise ValueError(
                    f"Project is missing steps {sorted(new_step_names)}, "
                    f"and contains extra steps {sorted(obsolete_step_names)}",
                )

            # Removing obsolete steps
            for obsolete_step in obsolete_step_names:
                del values[obsolete_step]

            # Adding new steps
            for new_step_name in new_step_names:
                logger.info(f"Adding step {new_step_name}...")
                new_step = getattr(default_solution.steps, new_step_name)
                values[new_step_name] = new_step

        return values

    @field_validator("*", mode="before")
    @classmethod
    def validate_steps(cls, value: Any, info: ValidationInfo):
        """Return the ``value``.

        Raises an exception if the ``value`` parameter doesn't contain ``StepModel``.

        Parameters
        ----------
        value : any
        field : pydantic.ValidationInfo
            Validation information of the field containing the Solution steps.

        Returns
        -------
        Any:
             The ``value`` parameter.
        """
        step_type = cls.model_fields[info.field_name].annotation  # type: ignore
        if step_type is not None:
            assert issubclass(  # noqa: S101  #nosec
                step_type,
                StepModel,
            ), f"Invalid type defined in steps: the field '{info.field_name}' is not a type derived from StepModel."
        return value

    model_config = ConfigDict(extra="forbid")


class Solution(BaseModel, ABC):
    """
    Classes derived from this class contain the definition of a Solution.
    A Solution is a user guided workflow application in the GLOW framework.

    Instances of this class are referred to as 'projects'.
    Project files are the persisted form of a ``Solution`` instance.

    Notes
    -----
    |saf-docs-user-guide-ref|_ provides information on how create
    an application that uses a class derived from ``Solution``.
    |saf-docs-solution-definition-ref|_ provides information on how to modify a
    class derived from ``Solution``.

    ``Solution`` is derived from the pydantic ``BaseModel`` class to enable parsing and validation of project data.
    A Solution definition follows pydantic conventions when defining its schema.
    You can read more about pydantic `here <https://docs.pydantic.dev/>`_.
    """

    model_config = ConfigDict(validate_assignment=True, validate_default=True, extra="forbid")

    dag: ClassVar[DependencyGraph]

    display_name: str
    """The name of the Solution that identifies the Solution to the end user.
    This name is displayed in UIs that are exposed to the end user.
    Declare this field in a derived class to set a value appropriate to that Solution.

    Examples
    --------

     >>> class FluidsSolution(Solution):
     >>>     display_name: str = "Fluids"


    """

    version: int = 1
    """The data schema version of the Solution.
    Declare this field in a derived class to indicate the schema version for that Solution.

    Examples
    --------

     >>> class FluidsSolution(Solution):
     >>>     version: int = 2
    """

    migrations: list[Migration] = []

    def get_steps(self) -> StepsModel:
        """The set of objects derived from :py:class:`~ansys.saf.glow.solution.StepModel` that comprise project
        data and implement Solution functionality through their methods.
        Declare this field in a derived class to provide the steps for that Solution.
        The type of the derived field is itself derived from :py:class:`~ansys.saf.glow.solution.StepsModel`.

        Examples
        --------

        >>> class FluidsSolution(Solution):
        >>>     steps: FluidsSteps
        """
        # We cannot use a field `steps: StepsModel` for that purpose.
        # pyright would complain for each solution definition in the following way:
        # - error: "steps" overrides symbol of same name in class "Solution"
        # -     Variable is mutable so its type is invariant
        # -     Override type "Steps" is not the same as base type "StepsModel" (reportIncompatibleVariableOverride)
        return self.steps  # type: ignore

    @property
    def live_handles(self) -> list[EntityHandle]:
        """A list of entity handles that are referring to blobs and are stored in project fields."""
        handles: list[EntityHandle] = []
        steps = self.get_steps()
        for step_name in steps.model_fields:  # pyright: ignore[reportDeprecated]
            step: StepModel = getattr(steps, step_name)
            handles.extend(step.live_handles)
        return handles

    @model_validator(mode="before")
    @classmethod
    def _validate_fields(cls, values: dict[str, Any]):
        """Validate ``values`` argument which contains the data for a ``Solution``.

        Throws exceptions if ``values`` contains keys that are not a field of a Solution.

        Parameters
        ----------
        values : dictionary with str keys
            Set of potential values for a Solution object's fields.

        Returns
        -------
        dictionary with str keys
            The ``values`` argument.
        """

        allowed_fields = {"steps", "solution_configuration", *Solution.model_fields.keys()}
        for field_name in values:
            if field_name not in allowed_fields:
                raise ValueError(f"{field_name} is not an allowed field in the Solution.")
        if not values.get("steps"):
            raise ValueError("The Solution must define at least one step.")
        return values

    @model_validator(mode="after")
    def _validate_migrations(self) -> Self:
        # Check that the version integers in migrations increase without gaps and are lower than the current version
        version_list = [migration.version for migration in self.migrations]
        if not version_list:
            return self
        if version_list[0] < 1 or version_list != list(range(version_list[0], self.version)):
            raise ValueError(
                "The migration versions must be an increasing list of integers no lower than 1, without gaps, and "
                f"reaching up to the current version minus 1. The current version is {self.version} and the migration "
                f"version list is {version_list}.",
            )
        return self

    @model_validator(mode="before")
    @classmethod
    def _upgrade_solution(cls, values: dict[str, Any], info: ValidationInfo):
        if info.context and info.context.get("mode") in ["upgrade", "import"]:
            default_instance: Solution = info.context["default_solution"]
            values["migrations"] = default_instance.migrations
            migration_context_constructor = cast(
                "Callable[[dict[str, Any]], MigrationContext]",
                info.context.get("migration_context_constructor"),
            )
            migration_context = migration_context_constructor(values)
            cls._apply_solution_migrations(
                values,
                migration_context,
                info.context.get("mode"),
                info.context.get("automatic_project_migration"),
            )
            values["display_name"] = default_instance.display_name
            values["version"] = default_instance.version
        return values

    @classmethod
    def _apply_solution_migrations(
        cls,
        values: dict[str, Any],
        migration_context: MigrationContext,
        mode: str,
        automatic_project_migration: bool,
    ) -> None:
        migrations_field = cls.model_fields.get("migrations")
        migrations: list[Migration] = migrations_field.default if migrations_field else []
        if not migrations:
            return
        if automatic_project_migration:
            logger.warning(
                "Applying a migration transformation while automatic project migration is enabled. This could lead to "
                "errors while migrating projects.",
            )
        version_to_update = values.get("version", 1)
        if version_to_update < migrations[0].version:
            raise MalformedSolutionError(
                f"the solution version of the project ({version_to_update}) is lower than the lowest migratable "
                f"version ({migrations[0].version}).",
            )
        project_directory = migration_context.project_directory
        project_directory_backup = project_directory.parent / f"backup_{project_directory.name}"
        shutil.copytree(project_directory, project_directory_backup)
        for migration in migrations:
            if version_to_update > migration.version:
                continue
            try:
                migration.migration_transformation.migrate(migration_context)
            except Exception as e:
                if project_directory.is_dir():
                    shutil.rmtree(project_directory)
                    # project_directory is not preserved on failed import
                    if mode == "upgrade":
                        shutil.move(project_directory_backup, project_directory)
                # Using ValueError allows this error to be presented to the user as an UnprocessableEntityError
                logger.debug("Migration Transformation failure stack trace:\n%s", traceback.format_exc())
                raise ValueError(
                    "Could not migrate: migration transformation "
                    f"{type(migration.migration_transformation).__name__} failed "
                    f"with error: '{e}'",
                ) from e
        shutil.rmtree(project_directory_backup)

    @model_validator(mode="wrap")
    @classmethod
    def _validate_solution(cls, values: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo):
        self_solution = handler(values)
        cls.dag = cls._get_dag()
        if info.context and info.context.get("mode") == "init":
            initialize_states(self_solution)
        return self_solution

    @classmethod
    def initialize(cls) -> Solution:
        """Initialize the solution with default values."""
        default_values = cls.model_construct().model_dump()
        steps = {name: _type() for name, _type in cls.get_steps_fields().items()}
        # we need to pass the default values in addition to the steps to build a default solution
        # because we want to validate them and make sure no extra fields were added.
        solution = {"steps": steps, **default_values}
        default_solution_instance = cls.model_validate(solution, context={"mode": "init"})
        return default_solution_instance

    @classmethod
    def get_steps_fields(cls) -> dict[str, type[StepModel]]:
        """Return a dictionary of the step classes in the Solution.

        Returns
        -------
        dict
            Dictionary where the keys are the names of steps and the values are the step classes derived from
            :py:class:`~ansys.saf.glow.solution.StepModel`. Step names are the field names of the Solution
            :py:class:`~ansys.saf.glow.solution.StepsModel`. The step classes are the types of the fields of the
            :py:class:`~ansys.saf.glow.solution.StepsModel`.

            :py:class:`~ansys.saf.glow.solution.StepsModel` is the
            base class of the :py:attr:`~ansys.saf.glow.solution.Solution.steps` field of the ``Solution``.
        """
        steps = cls.model_fields.get("steps")
        if steps is None:
            raise SolutionLoadException("The solution does not contain any steps. Add a step to the solution.")
        return {
            step_name: step_type.annotation
            for step_name, step_type in steps.annotation.model_fields.items()  # type: ignore
        }

    @classmethod
    def get_step_instance_names(cls, query_step_name: str) -> set[str]:
        """Return the names of the shared product instances in a given
        step in the Solution.

        Parameters
        ----------
        query_step_name : str
            Name of the step. A 'step' is a field on a
            :py:class:`~ansys.saf.glow.solution.StepsModel` derived class.
            The name of a step is the name of the field. The :py:class:`~ansys.saf.glow.solution.StepsModel`
            derived class is the type of the :py:class:`~ansys.saf.glow.solution.Solution.steps` field which
            defines the set of steps in a :py:class:`~ansys.saf.glow.solution.Solution` derived class.


        Returns
        -------
        ``set of str``
            Names of the shared product instances in the step referred to by ``query_step_name``.
        """
        step = cls.get_steps_fields().get(query_step_name)
        if step is None:
            return set()
        return set(step._get_create_instance_by_name().keys())  # pyright: ignore[reportPrivateUsage]

    @classmethod
    @cache
    def _get_methods(cls) -> set[MethodIdentifier]:
        return {
            MethodIdentifier(step_name, method_name)
            for step_name, step in cls.get_steps_fields().items()
            for method_name in step.get_transaction_method_names()
        }

    @classmethod
    @cache
    def _get_dag(cls) -> DependencyGraph:
        return DependencyGraph(cls)

    @classmethod
    @cache
    def _get_normalized_references_to_method_instances(cls, method: MethodIdentifier) -> set[str]:
        method_func = getattr(cls.get_steps_fields()[method.step_name], method.method_name)
        instances_used_by_method = getattr(method_func, INSTANCES_USED_BY_METHOD_ATTRIBUTE_STRING)
        return {instance.get_full_name(method.step_name) for instance in instances_used_by_method.instance_attributes}

    @classmethod
    @cache
    def get_other_methods_with_same_instance(cls, method: MethodIdentifier) -> set[MethodIdentifier]:
        """For a given transaction method, return the other transaction methods that
        use or create any of the same shared product instances used or
        created by the given method.

        Parameters
        ----------
        method : ``ansys.saf.glow.solution.MethodIdentifier``
            Transaction method in this Solution.

        Returns
        -------
        ``set of ansys.saf.glow.solution.MethodIdentifier``
            Transaction methods that use or create any of the shared product instances that are used or created by
            ``method``.

        Notes
        -----
        |saf-docs-transaction-methods-ref|_ explains the transaction method
        concept in more detail.
        |saf-docs-instance-management-ref|_ explains the shared product
        instance concept in more detail.
        """
        method_instances = cls._get_normalized_references_to_method_instances(method)
        return {
            other_method
            for other_method in cls._get_methods()
            if method != other_method
            and method_instances.intersection(cls._get_normalized_references_to_method_instances(other_method))
        }

    @property
    def url(self) -> str:
        """URL of the project.

        Returns
        -------
        str
            URL of the project.
        """
        raise NotImplementedError()

    @property
    def project_id(self) -> str:
        """The ID of the project that identifies the project at the API level.

        Returns
        -------
        str
            Project ID.
        """
        raise NotImplementedError()

    @property
    def project_name(self) -> str:
        """The name of the project (format `projects/<project_id>`) that identifies the project at the API level.

        Returns
        -------
        str
            Project name.
        """
        raise NotImplementedError()

    @property
    def project_display_name(self) -> str:
        """The display name of the project that identifies the project to the end user.

        The value of this property is meant to be used in UIs that are exposed to the end user.
        (This is not an alias for ``display_name``. ``display_name`` refers to the Solution's display name,
        which has the same value for all projects whereas ``project_display_name`` is for this specific project.)

        Returns
        -------
        str
            Project's display name.
        """
        raise NotImplementedError()

    @property
    def project_description(self) -> str:
        """The description of the project.

        Returns
        -------
        str
            Project's description.
        """
        # We reserve "description" property for a future solution description, to follow the same pattern as
        # "display_name" and "project_display_name". It sounds reasonable that we could have that in the future.
        raise NotImplementedError()

    @contextmanager
    def get_storage_scope(self) -> Generator[IStorageScope, None, None]:
        """Return a storage scope context to enable access to blob storage
        (e.g. store or retrieve files or directories).
        Unlike the ``storage_scope`` property, this must be used with the with-statement
        when the project client is not created using a context manager.
        Note that this is not the recommended way to use the storage scope and must only be
        used for advanced usage.

        Returns
        -------
        ContextManager[IStorageScope]
            the project storage scope

        Examples
        --------
        >>>    client = Client(...)
        >>>    project = client.get_project(...)
        >>>    with project.get_storage_scope as scope:
        >>>        ...
        """
        raise NotImplementedError()

    @property
    def storage_scope(self) -> IStorageScope:
        """Return a storage scope context to enable access to blob storage
        (e.g. store or retrieve files or directories).
        This must be used when the project client is created using a context
        manager.
        Note that this is the recommended way to use storage scope client side and
        is what must be used within dash callbacks.

        Returns
        -------
        IStorageScope
            the project storage scope

        Examples
        --------
        >>>    with Client(...) as client:
        >>>        project = client.get_project(...)
        >>>        scope = project.storage_scope
        >>>        text = scope.get_text(...)
        >>>        ...

        or when using Dash:

        >>>   @callback(State("url", "pathname"))
        >>>   def something(project: MySolution):
        >>>       text_file_content = project.storage_scope.get_text(...)
        >>>       ...
        """
        raise NotImplementedError()

    def delete(self) -> None:
        """Delete the project."""
        raise NotImplementedError()

    def download_file(self, filepath: str, destination: Path) -> None:
        """Download a file in the project directory.

        Parameters
        ----------
        filepath : str
            Path of the source file in the project directory relative to the root of the project directory.
        destination : Path
            File path which will be created or overwritten with the content of the file referenced by ``filepath``.
        """
        raise NotImplementedError()

    def upload_file(self, target_filepath: str, binary_fileobj: BinaryIO) -> None:
        """Upload the content of the binary file-like object to a file
        in the project directory.

        Parameters
        ----------
        target_file_path : str
            Path of the destination file in the project directory relative to the root of the project directory.
        binary_fileobj : BinaryIO
            Binary file-like object which is the source of the data that will be written to the destination file.

            The binary file-like object is simply the returned value of ``with open()`` with binary mode.

        Examples
        --------
        >>>    with open('myfile.jpg', mode='rb') as binary_fileobj:
        >>>        project.upload_file("my_directory", "myfile.jpg", binary_fileobj)
        """
        raise NotImplementedError()

    def delete_file(self, target_filepath: str) -> None:
        """Remove a file from the project directory.

        Parameters
        ----------
        target_file_path : str
            Path of the file to be deleted in the project directory relative to the root of the project directory.
        """
        raise NotImplementedError()

    def delete_files(self, pattern: str, rmdir: bool = False) -> None:
        """Remove the files matching the relative glob pattern in the directory from the project.

        Parameters
        ----------
        pattern : str
            The glob pattern specifying sets of filenames with wildcard characters as listed by the glob module:
            https://docs.python.org/3/library/glob.html

        rmdir: bool
            Specify whether empty directories must be removed or not.

        Examples
        --------
        >>>    # Delete all python files
        >>>    project.delete_files("**/*.py")
        """
        raise NotImplementedError()

    def modify_info(
        self,
        display_name: str | None = None,
        description: str | None = None,
    ) -> None:
        """Modify project information.

        Leave a field as None to keep it unchanged. Set a field to an empty string to remove it.

        Parameters
        ----------
          display_name : str, optional
              The new display name.
          description : str, optional
              The new description.

        Examples
        --------
        >>>    project.modify_info(display_name="new_display_name")
        >>>    project.modify_info(description="Updated description")
        >>>    project.modify_info(display_name="new_display_name", description="Updated description")
        """
        raise NotImplementedError()

    def upload_data_uri_as_file(self, target_filepath: str, data_uri: str) -> None:
        """Write the content of a data URI to a remote file.

        Parameters
        ----------
        target_file_path : str
            Path of the destination file in the project directory relative to the root of the project directory.
        data_uri : str
            Data URI which is the source of the data that will be written to the destination file.

            The data URI is a scheme consisting of a mime type and a base64
            encoded string. For example:  ``data:text/plain;base64,SGVsbG8gV29ybGQh``
        """
        raise NotImplementedError()

    def export(self, destination: Path) -> None:
        """Export the project into a directory as an archive file.

        The project file will be saved in as ``<display_name>.safx`` in the directory specified by ``destination``

        Parameters
        ----------
        destination : Path
            Path of the directory where the ``safx`` archive is exported.
        """
        raise NotImplementedError()

    def authenticate_hps(
        self,
        hps_server_url: str | None = None,
        client_id: str | None = None,
    ) -> None:
        """Authenticate into the configured HPS system.

        Parameters
        ----------
        hps_server_url: str, optional
            HPS endpoint that the HPS client will connect to.

        client_id: str, optional
            Client ID of the HPS system in OAuth.
        """
        raise NotImplementedError()
