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
import logging
from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, ValidationInfo, ValidatorFunctionWrapHandler, model_validator

from ansys.saf.glow._config.const import INSTANCES_USED_BY_METHOD_ATTRIBUTE_STRING
from ansys.saf.glow._core.field_state import FieldState  # noqa: TC001
from ansys.saf.glow._core.livehandles import LiveHandlesModel

if TYPE_CHECKING:
    from ansys.bdm.api import EntityHandle, IStorageScope
    from ansys.iam.oidc import UserInfo
    from ansys.saf.glow._bdm.datarepo import DataRepository
    from ansys.saf.glow._core.instance.attribute import CreateInstance
    from ansys.saf.glow._core.instance.decorator import InstancesUsedByMethod
    from ansys.saf.glow._core.method_status import MethodState


logger = logging.getLogger(__name__)


class Transaction:
    """Execution context of a transaction method. Enables access to GLOW infrastructure functionality
    during the execution of a transaction method.

    Notes
    -----
    |saf-docs-uploading-field-during-async-execution-ref|_ provides an example of this
    class being accessed through the :py:attr:`~ansys.saf.glow.solution.StepModel.transaction` property on
    :py:class:`~ansys.saf.glow.solution.StepModel`.
    """

    def upload(self, field_names: list[str]) -> None:
        """Upload step fields to the project to persist their contents.
        Use this method to update fields during the execution of a method.

        Parameters
        ----------
        field_names : ``list of str``
            List of the fields (identified by name) whose content in the
            method execution environment is to be uploaded to the project.
            The names must match the field names of the step.

        Notes
        -----
        |saf-docs-uploading-field-during-async-execution-ref|_
        describes how to use this method with an example.
        """
        raise NotImplementedError()

    def raise_event(self, message: Any, stream_name: str | None = None) -> None:
        """Enqueue an event that contains the ``message`` on the ``stream_name`` queue,
        within a step of an existing project.

        Parameters
        ----------
        message : ``Any``
            Message to be enqueued. Can contain ``Any`` json-able type of data.
        stream_name : str, optional
            The name of the stream where the ``message`` will be enqueued to.
            If not set, the name of the transaction method the event is
            raised from will be used.

        Examples
        --------

         >>> class MyStep(StepModel):
         >>>    @transaction(self=StepSpec())
         >>>    def trigger_event(self) -> None:
         >>>        self.transaction.raise_event(message={"message":"Hello world!"}, stream_name="my-stream")
        """
        raise NotImplementedError()

    @property
    def access_token(self) -> str | None:
        """The current access token authorizing the execution of the transaction method.

        Returns
        -------
        str | None
            The current access token authorizing the execution of the transaction method.
        """
        raise NotImplementedError()

    @property
    def user_info(self) -> UserInfo:
        """Information about the user who executed the transaction method.

        Returns
        -------
        ansys.saf.glow.solution.UserInfo
            User information extracted from the token in the request's header.
        """
        raise NotImplementedError()

    def get_asset_entity_handle(self, asset_relative_path: str) -> EntityHandle:
        """Get the entity handle referring to the specified asset.

        Parameters
        ----------
        asset_relative_path: str
            The relative path of an asset in the "method_asset" directory.
            It could refer to a file or a directory.
            For encrypted file, the ``asset_relative_path`` should omit the ``.encrypted`` suffix.

        Returns
        -------
        EntityHandle
            The entity handle referring to the asset.

        Examples
        --------

         >>> class MyStep(StepModel):
         >>>    @transaction(self=StepSpec())
         >>>    def read_asset_file(self) -> None:
         >>>        asset_handle = self.transaction.get_asset_entity_handle("dir/encrypted_asset.txt")
         >>>        asset_content = self.storage_scope.get_text(asset_handle)
         >>>        ...
        """
        raise NotImplementedError()

    def get_user_info(self, fields: list[str] | None = None) -> UserInfo:
        """Get specific information about the user who executed the transaction method.

        Parameters
        ----------
        fields : list of str, optional
            List of fields to retrieve from the user information.

        Returns
        -------
        ansys.saf.glow.solution.UserInfo
            User information extracted from the token in the request's header including the requested fields.

        Raises
        ------
        ValueError
            If any of the requested fields are empty in the extracted user information.
        """
        raise NotImplementedError()


class StepModel(LiveHandlesModel, ABC):
    """A derived class defines the schema and methods for a subsection of the application defined by a
    :py:class:`~ansys.saf.glow.solution.Solution` derived class.

    Notes
    -----
    You can read more about creating a class derived from ``StepModel`` |saf-docs-step-models-ref|_.

    ``StepModel`` is derived from the pydantic ``BaseModel`` class to enable parsing and validation of step data.
    A ``StepModel`` derived class follows pydantic conventions when defining its schema.
    You can read more about pydantic `here <https://docs.pydantic.dev/>`_.

    A ``StepModel`` derived class becomes part of a Solution by its use as the type of a field on a
    :py:class:`~ansys.saf.glow.solution.StepsModel` derived class that is in turn the type of the
    :py:attr:`~ansys.saf.glow.solution.Solution.steps` field of the Solution.
    ("Solution" here means a class derived from the :py:class:`~ansys.saf.glow.solution.Solution` class.)
    """

    state: dict[str, FieldState] = {}
    """A mapping from the names of each fields on the step to the state of the field.

    Notes
    -----
    This field is described in more detail |saf-docs-field-states-ref|_.
    """

    model_config = ConfigDict(
        validate_assignment=True,
        validate_default=True,
        extra="forbid",
        revalidate_instances="always",
    )

    @property
    def transaction(self) -> Transaction:
        """Execution context of the currently running transaction method.
        The returned object enables access to GLOW infrastructure functionality for the step during execution of a
        transaction method.

        Returns
        -------
        ansys.saf.glow.solution.Transaction
            Execution context of the currently running transaction method.

        Notes
        -----
        |saf-docs-uploading-field-during-async-execution-ref|_ provides an
        example of using the ``transaction`` property.
        """
        return Transaction()

    @property
    def storage_scope(self) -> IStorageScope:
        """Return a storage scope to enable access to blob storage (e.g. store or retrieve files or directories)."""
        raise NotImplementedError()

    @classmethod
    def _get_method_names(cls, tag: str) -> list[str]:
        return [method for method in dir(cls) if not method.startswith("__") and hasattr(getattr(cls, method), tag)]

    @classmethod
    def get_transaction_method_names(cls) -> list[str]:
        """Return the list of transaction methods on this step.

        Returns
        -------
        ``list of str``
            The list of transaction methods on this step.

        Notes
        -----
        You can read more about how transaction methods are defined |saf-docs-transaction-methods-ref|_.
        """
        return cls._get_method_names("_wrapped_transaction_method")

    @classmethod
    def get_instance_method_names(cls) -> list[str]:
        """Return the list of transaction methods on this step
        that create or use shared product instances.

        Returns
        -------
        ``list of str``
            List of transaction methods on this step that create or
            use shared product instances.

        Notes
        -----
        You can read more about how transaction methods create or use shared product instances
        |saf-docs-instance-management-ref|_.
        """
        return cls._get_method_names(INSTANCES_USED_BY_METHOD_ATTRIBUTE_STRING)

    @classmethod
    def get_instance_references(cls) -> list[str]:
        """Return reference strings for the shared product instances
        that are created or used in this step.

        Returns
        -------
        ``list of str``
            Reference strings for the shared product instances that
            are created or used in this step.
            A reference string is either a name without a period (`.`)
            or two names separated by a period.
            If there are two names, then the first is the name of a step
            and the second is the name of an instance.
            If there is only one name, then the name refers to an instance
            created in this step.

        Notes
        -----
        You can read more about how transaction methods create or use shared product instances
        |saf-docs-instance-management-ref|_.
        """

        instance_references: list[str] = []
        method_names = cls.get_instance_method_names()
        for method_name in method_names:
            step_func = getattr(cls, method_name)
            method_instance_attributes: InstancesUsedByMethod = getattr(
                step_func,
                INSTANCES_USED_BY_METHOD_ATTRIBUTE_STRING,
            )
            instance_references.extend([i.instance_reference for i in method_instance_attributes.instance_attributes])
        return instance_references

    @classmethod
    def _get_create_instance_by_name(cls) -> dict[str, CreateInstance]:
        """Return a mapping between the name of an instance and its @create_instance on this step
        that create or use shared product instances.

        Returns
        -------
        ``dict[str, CreateInstance]``
            A CreateInstance attribute mapped by its instance name.

        Notes
        -----
        You can read more about how transaction methods create or use shared product instances
        |saf-docs-instance-management-ref|_.
        """
        create_instance_by_name: dict[str, CreateInstance] = {}
        method_names = cls.get_instance_method_names()
        for method_name in method_names:
            step_func = getattr(cls, method_name)
            method_instance_attributes: InstancesUsedByMethod = getattr(
                step_func,
                INSTANCES_USED_BY_METHOD_ATTRIBUTE_STRING,
            )
            create_instance = method_instance_attributes.find_create_instance()
            if create_instance:
                create_instance_by_name[create_instance.instance_name] = create_instance
        return create_instance_by_name

    @classmethod
    def get_long_running_method_names(cls) -> list[str]:
        """Return the list of long-running transaction methods on this step.

        Returns
        -------
        ``list of str``
            List of long-running transaction methods on this step.

        Notes
        -----
        |saf-docs-asynchronous-execution-ref|_ describes the concept of
        long running methods in detail.
        """
        return cls._get_method_names("__wrapped_long_running_method__")

    def get_method_state(self, method_name: str) -> MethodState:
        """Return the state of a transaction method on this step.

        Parameters
        ----------
        method_name : str
            Name of a transaction method on this step.

        Returns
        -------
        ansys.saf.glow.solution.MethodState
            State of the given method.
        """
        # return the run status of a specific method on this step in a specific project
        raise NotImplementedError()

    def get_long_running_method_state(self, method_name: str) -> MethodState:
        """Return the state of a long-running transaction method on this step.

        Parameters
        ----------
        method_name : str
            Name of a long-running transaction method on this step.

        Returns
        -------
        ansys.saf.glow.solution.MethodState
            State of the given method.

        Notes
        -----
        |saf-docs-asynchronous-execution-ref|_ describes the concept of
        long running methods in detail.
        """
        # return the run status of a specific method on this step in a specific project
        raise NotImplementedError()

    def get_fields(self, field_names: list[str] | None = None) -> dict[str, Any]:
        """Return a dictionary with the values of the requested fields.

        Parameters
        ----------
        field_names : ``list of str``
            Names of the fields to retrieve the value of.

        Returns
        -------
        ``dict of [str, Any]``
            Dictionary containing the values of the requested fields.
        """
        raise NotImplementedError()

    def set_fields(self, fields: dict[str, Any]) -> None:
        """Set the value of the referenced fields on this step.

        Parameters
        ----------
        fields : ``dict``
            Dictionary of field names and their values.
        """
        raise NotImplementedError()

    def get_entity_url(self, entity_field_name: str) -> str:
        """Return the content of the referenced entity step field.

        Parameters
        ----------
        entity_field_name : ``str``
            The name of a step field containing an entity handle that points to a file.

        Returns
        -------
        ``str``
            Contents of the file associated to the entity step field.
        """
        raise NotImplementedError()

    def get_data(
        self,
        datapath: str = "",  # pyright: ignore[reportUnusedParameter]
        substitute_file_handles_with_urls: bool = False,  # pyright: ignore[reportUnusedParameter]
        substitute_directory_handles_as_dictionaries: bool = False,  # pyright: ignore[reportUnusedParameter]
    ) -> Any:
        """Get data of a step field at any level within its data structure.
        This is useful to retrieve only a subset of a large nested custom data structure stored in a step field.
        It gives you the ability to traverse the data structure using a URI path syntax.

        Parameters
        ----------
        datapath : str, default ``""``
            A URI path to a nested data item. The path is used to traverse persisted data to locate the data
            to be returned by the method.
            If datapath is empty it refers to all the data in the step.
            If non empty, it can refer to a step field, an entity handle or any nested data item within the step field.

            The syntax and semantics of the path is as follow:
              - The path is composed of segments separated by slashes (``/``).
              - The first segment of the path refers to a step field name.
              - Subsequent segments represent a key in a dictionary, an index in a list, a field of a custom model or
                an entity handle.
              - If a segment is an entity handle referencing a directory, the next segment refers to a file
                or sub-directory within the directory referenced by the entity handle.
              - If a segment is an entity handle referencing a file, or a simple field, no further segments are allowed.
              - Examples of valid paths:
                  - ``""`` (refers to the whole content of the step)
                  - ``"field_name"`` (refers to the entire content of the step field named `field_name`)
                  - ``"dict_field_name/key1/key2"`` (refers to the value associated with `key2` in a nested dictionary
                    structure within the step field `dict_field_name`)
                  - ``"list_field_name/0"`` (refers to the value of the first element of a list within the step field
                    `list_field_name`)
                  - ``"entity_field_name/subdir/file.txt"`` (refers to the file `file.txt` within the sub-directory
                    `subdir` of the directory referenced by the entity handle named `entity-field-name`)
                  - ``"my_model/my_field"`` (refers to the field `my_field` within a custom pydantic model `my_model`)

            If a key contains ``/`` or ``\\`` characters, they should be escaped as ``\\/`` or ``\\\\`` respectively.

        substitute_file_handles_with_urls : bool, default ``False``
            If ``True`` each entity handle that refers to a file in the returned data will be replaced with a URL that
            refers to the file.  (The URL is not based on the filesystem location of the file but instead it refers to
            a GLOW API server end point that can resolve the content of the file wherever the content is located.)

            This flag is useful for rendering data in a web application because the URLs can be passed directly to a
            browser which can then download the file content when needed.  This approach is especially useful when
            the number of files in a given data set varies depending on how the user interacts with the solution.

            The returned URLs will be prefixed by the value of the ``GLOW_EXTERNAL_API_URL``
            environment variable if set.  If ``GLOW_EXTERNAL_API_URL`` is not set the returned URLs will be prefixed by
            a URL derived from the ``GLOW_API_HOST`` environment variable (with a default of ``127.0.0.1`` if not set)
            and the ``GLOW_API_PORT`` environment variable (with a default of ``5432`` if not set).

        Returns
        -------
        ``Any``
            The data item located at the specified datapath in a json form.

        """
        raise NotImplementedError()

    @model_validator(mode="before")
    @classmethod
    def _upgrade_step(cls, values: dict[str, Any], info: ValidationInfo) -> dict[str, Any]:
        if (context := info.context) and context.get("mode") in ["upgrade", "import"]:
            default_solution = context["default_solution"]
            step_name = next(
                step_name
                for step_name, step_info in default_solution.steps.model_fields.items()
                if step_info.annotation == cls
            )
            field_names = set(cls.model_fields.keys())
            old_field_names = set(values.keys())
            obsolete_field_names = old_field_names - field_names
            new_field_names = field_names - old_field_names

            if (new_field_names or obsolete_field_names) and not context["automatic_project_migration"]:
                raise ValueError(
                    f"Step '{step_name}' is missing fields {sorted(new_field_names)}, "
                    f"and contains extra fields {sorted(obsolete_field_names)}",
                )

            # Removing obsolete step fields
            for obsolete_field in obsolete_field_names:
                logger.info(f"Deleting obsolete field {obsolete_field} from step {step_name}...")
                del values["state"][obsolete_field]
                del values[obsolete_field]

            # Adding new step fields
            for new_field_name in new_field_names:
                logger.info(f"Adding new field {new_field_name} from step {step_name}...")
                step = getattr(default_solution.steps, step_name)
                new_field = getattr(step, new_field_name)
                values[new_field_name] = new_field
                values["state"][new_field_name] = step.state[new_field_name]

        return values

    @model_validator(mode="wrap")
    @classmethod
    def _validate_stored_step_fields(cls, values: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo):
        self_step = handler(values)
        if info.context and (mode := info.context.get("mode")) and mode == "from_db":
            current_step_fields = set(self_step.model_fields.keys())
            original_step_fields = set(values.keys())
            if current_step_fields != original_step_fields:
                raise ValueError(
                    "extra step fields are not allowed without upgrading the solution. "
                    f"Extra step fields: {current_step_fields - original_step_fields}",
                )

        return self_step

    @property
    def data_repository(self) -> DataRepository:
        """Returns data repository instance if it's configured. Otherwise it raises an exception."""
        raise NotImplementedError()
