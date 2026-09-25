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

from collections.abc import Callable
from functools import wraps
import inspect
import logging
from typing import Annotated, Any, ParamSpec, TypeVar, get_origin, get_type_hints

from ansys.bdm.api import IStorageScope
from ansys.iam.oidc import OidcClient
from fastapi import Body
import httpx2
from pydantic import (
    BaseModel,
    ConfigDict,
    PydanticUserError,
    create_model,
)

from ansys.saf.glow._bdm.datarepo import DataRepository
from ansys.saf.glow._bdm.multiplexor import SafMultiplexorStorageScopeFactory
from ansys.saf.glow._config.settings import Settings
from ansys.saf.glow._core.blob_managers import AssetManager, HpsBlobManager
from ansys.saf.glow._core.exceptions import SolutionLoadException
from ansys.saf.glow._core.gql import GqlClientConnectionPool
from ansys.saf.glow._core.instance.decorator import InstancesUsedByMethod
from ansys.saf.glow._core.instance.iinstance_system import IProductInstanceSystemFactory
from ansys.saf.glow._core.instance.manager import ProductInstanceManager
from ansys.saf.glow._core.livehandles import (
    WrapperBuilder,  # pyright: ignore[reportPrivateUsage]
)
from ansys.saf.glow._core.solution import Solution
from ansys.saf.glow._core.step_model import StepModel
from ansys.saf.glow._core.step_spec import StepSpec
from ansys.saf.glow._crud.solution_configuration_models import SolutionConfiguration
from ansys.saf.glow._executor.local import transaction_local
from ansys.saf.glow._executor.transaction import TransactionStepModel
from ansys.saf.glow._utilities.conversion import python_identifier_to_url_part

# ruff: noqa: C901
logger = logging.getLogger(__name__)
T = TypeVar("T")
TSolutionConfig = TypeVar("TSolutionConfig", bound=SolutionConfiguration)
P = ParamSpec("P")
TModel = TypeVar("TModel", bound=BaseModel)


class SolutionConfigParam(BaseModel):
    name: str
    type: type[TSolutionConfig]  # pyright: ignore[reportGeneralTypeIssues]


def _has_entity_handles(step_func: Callable[..., Any], **kwargs: StepSpec) -> Callable[[str, Solution], bool]:
    def has_entity_handles(step_name: str, solution: Solution) -> bool:
        # Leave any validation to _validate_transaction
        signature = inspect.signature(step_func)
        solution_steps = solution.get_steps_fields()
        for parameter_name, _ in signature.parameters.items():
            if parameter_name not in kwargs:
                continue
            step_spec = kwargs[parameter_name]
            resolved_step_name = parameter_name if parameter_name != "self" else step_name
            step = solution_steps[resolved_step_name]()
            for field_name in step_spec.download + step_spec.upload:
                # Cover transactions that define entity handles within the step spec fields, either from themselves or
                # from other steps.
                if step._entity_handle_fields.field_has_handles(field_name):  # pyright: ignore[reportPrivateUsage]
                    logger.debug(f"Transaction {step_func.__name__} has entity handles in its {field_name=}")
                    return True

        step_func_type_hints = get_type_hints(step_func)
        for param, type_hint in step_func_type_hints.items():
            # Cover transactions that define entity handles directly in their input parameters or return value
            wrapper_type = WrapperBuilder().build_handle_containing_type_wrapper(type_hint)
            if wrapper_type.has_handles():
                logger.debug(
                    f"Transaction {step_func.__name__} has entity handles in its {param=} with type hint {type_hint=}",
                )
                return True
            # Cover transactions that create or use BDM-based product instances. They use entity handles for the product
            # state.
            try:
                if issubclass(type_hint, ProductInstanceManager):
                    logger.debug(
                        f"Transaction {step_func.__name__} uses a BDM-based instance manager in its {param=} "
                        f"with type hint {type_hint=}",
                    )
                    return True
            except:  # noqa: E722, S110  # not interested on errors caused by issubclass when applied to invalid types
                pass
        return False

    return has_entity_handles


def _validate_transaction(step_func: Callable[..., Any], **kwargs: StepSpec):
    def validate(step_name: str, solution: Solution):
        signature = inspect.signature(step_func)
        step_func_type_hints = get_type_hints(step_func)
        self_arg = kwargs.get("self")
        if not self_arg:
            raise SolutionLoadException("Missing 'self' StepSpec attribute in the @transaction decorator.")

        instance_decorators: InstancesUsedByMethod = getattr(
            step_func,
            "_instances_used_by_method",
            InstancesUsedByMethod(),
        )
        instance_decorators.validate(kwargs, step_name)

        # Verify that method args match the transaction step specs.
        for parameter_name, _ in signature.parameters.items():
            step_spec = kwargs.get(parameter_name)
            is_instance_identifier = parameter_name in [i.identifier for i in instance_decorators.instance_attributes]
            if step_spec:
                if is_instance_identifier:
                    raise SolutionLoadException(
                        f"The @transaction parameter '{parameter_name}' is used as the identifier of an instance.",
                    )

                if parameter_name != "self" and len(step_spec.upload) > 0:
                    raise SolutionLoadException(
                        f"The @transaction parameter '{parameter_name}' "
                        "cannot contains upload fields. Upload fields are specific to 'self'.",
                    )

                solution_steps = solution.get_steps_fields()
                if parameter_name != "self" and parameter_name not in solution_steps:
                    raise SolutionLoadException(
                        f"The parameter '{parameter_name}' does not match any steps in the solution.",
                    )
                else:
                    step_name = parameter_name if parameter_name != "self" else step_name
                    step_spec_fields = step_spec.download + step_spec.upload
                    step_fields = solution_steps[step_name].model_fields.keys()
                    for step_spec_field in step_spec_fields:
                        if step_spec_field not in step_fields:
                            raise SolutionLoadException(
                                f"The download/upload field: '{step_spec_field}' does not exist.",
                            )
            elif is_instance_identifier:
                instance = None
                for i in instance_decorators.instance_attributes:
                    if i.identifier == parameter_name:
                        instance = i
                        break
                if instance is None:
                    raise RuntimeError(
                        "[internal error] parameter_name is not instance identifier, call is_instance_identifier first",
                    )
                referenced_step_name, _ = instance.parse_field_reference(step_name)
                step = solution.get_steps_fields().get(referenced_step_name)
                if step is None:
                    raise SolutionLoadException(
                        f"@{instance.decorator_name} refers to non-existent step '{referenced_step_name}'"
                        f" in '{step_name}'",
                    )
                create_instance_decorator = step._get_create_instance_by_name().get(  # pyright: ignore[reportPrivateUsage]
                    instance.instance_name,
                )
                if create_instance_decorator is None:
                    raise SolutionLoadException(
                        "The @instance decorator with instance_name argument referring "
                        f"to {instance.get_full_name(step_name)} "
                        "does not have a corresponding @create_instance decorator",
                    )
                instance_type = create_instance_decorator.declared_instance_type
                parameter_type = step_func_type_hints.get(parameter_name)
                if parameter_type is not None and instance_type != parameter_type:
                    raise SolutionLoadException(
                        f"The argument {parameter_name} has type {parameter_type} "
                        "which does not match the corresponding "
                        f"instance manager type {instance_type} "
                        f"declared on the matching @create_instance",
                    )
            else:  # input parameters
                parameter_type = step_func_type_hints.get(parameter_name)
                if parameter_type is None:
                    raise SolutionLoadException(
                        f"The parameter '{parameter_name}' does not have any type hint defined.",
                    )

        try:
            if "return " in inspect.getsource(step_func) and step_func_type_hints.get("return") is None:
                raise SolutionLoadException(
                    "The @transaction contains a return statement but no return type hint is defined.",
                )
        except OSError:
            logger.debug(f"Can't validate return type of {step_func.__name__}: source code is unavailable.")

    return validate


def _get_step_name_from_self(required_step_type: type[StepModel], solution_type: type[Solution]) -> str:
    # TODO: Refactor this and ProjectProxy.get_step()
    # We can move the case len(step_names) > 1 to StepsModel as a validator and also have a
    # solution_type.get_step_name(step_type), instead of having to manually iterate the dict.
    step_names = [
        step_name
        for step_name, step_type in solution_type.get_steps_fields().items()
        if step_type == required_step_type
    ]
    if len(step_names) == 0:
        raise RuntimeError(f"no step of type {required_step_type} exists in {solution_type}")
    if len(step_names) > 1:
        raise RuntimeError(
            f"More than one step of type {required_step_type} exists in {solution_type}. "
            "Supply string 'step_name' argument to indicate which step is required",
        )
    return step_names[0]


def transaction(enable_termination_event: bool = False, **kwargs: StepSpec):
    """A method decorator that indicates that the decorated method is a `transaction method`. A transaction method is
    accessible to clients of the containing solution. Transaction methods can only be defined on
    :py:class:`~ansys.saf.glow.solution.StepModel` derived classes. A ``transaction`` decorator defines, via its
    :py:class:`~ansys.saf.glow.solution.StepSpec` arguments, which fields of the solution are
    transferred to and from the project and the method execution environment.

    Parameters
    ----------
    enable_termination_event : bool, optional
        A boolean indicatinf if the transaction method should raise an event through the
        transaction's default event stream containing a serialization of its assigned
        :py:class:`~ansys.saf.glow._core.method_status.MethodState`. If `True`, the event will
        always be raised even if the transaction was not successful.

    **kwargs : dict, optional
        A mapping of keyword arguments to :py:class:`~ansys.saf.glow.solution.StepSpec` objects.
        The argument keywords are the names of steps, the only exception, following python convention,
        being that ``self`` refers to the step on which the transaction method is defined.
        For each referenced step and keyword argument the argument value is a
        :py:class:`~ansys.saf.glow.solution.StepSpec` object that defines which
        fields of the step are transferred to and from the project and the method execution environment.

    Notes
    -----
    A 'step' is a field on a
    :py:class:`~ansys.saf.glow.solution.StepsModel` derived class.
    The name of a step is the name of the field. The :py:class:`~ansys.saf.glow.solution.StepsModel` derived
    class is the type of the :py:class:`~ansys.saf.glow.solution.Solution.steps` field which defines the set of
    steps in a :py:class:`~ansys.saf.glow.solution.Solution` derived class.

    The user guide section :ref:`here <saf-docs:transaction_methods>` describes how the ``transaction``
    decorator is used to define transaction methods.

    Examples
    --------
    >>>        @transaction(self=StepSpec(download=["x"]))
    >>>        def my_step_method(self):
    >>>            print(self.x)
    >>>
    >>>        @transaction(self=StepSpec(download=["x"]), enable_termination_event=True)
    >>>        def my_step_method_with_termination_event(self):
    >>>            print(self.x)
    """
    # The self entry in transaction's argument is required for the decorator logic to work properly
    # because self is a mandatory argument of the decorated method.
    # It is valid for this self step spec to have no arguments when the method uses a shared product
    # instance. To avoid the developer having to add a step spec with no arguments we create a
    # a step spec without arguments assigned to self if self is not passed to the decorator.
    if "self" not in kwargs:
        kwargs["self"] = StepSpec()

    def decorator(step_func: Callable[..., T]) -> Callable[..., T]:
        # There is some weird collision if these param names are also used by the solution developer as param names
        # of the transaction. Specially, for the ones here typed as "| None = None". In that case, get_type_hints
        # will return that the parameter specified by the solution developer has base Typing.Optional(). This does not
        # happen if @longrunning is set before @transaction, though... In any case, we prepend the optional params here
        # with underscores to reduce probability of collision.
        @wraps(step_func)
        def step_method_wrapper(
            step_self: StepModel,
            project_url: str,
            solution: Solution,
            name_of_step_containing_method: str,
            http_client: httpx2.Client,
            settings: Settings,
            instance_system_factory: IProductInstanceSystemFactory,
            storage_scope: IStorageScope,
            graphql_client: GqlClientConnectionPool,
            oidc_client: OidcClient,
            asset_manager: AssetManager,
            _multiplexor_storage_factory: SafMultiplexorStorageScopeFactory,
            _hps_blob_manager: HpsBlobManager,
            _access_token: str | None = None,
            _input_params: dict[str, Any] | None = None,
            _solution_configuration_param: SolutionConfigParam | None = None,
            _data_repository: DataRepository | None = None,
        ) -> T:
            result = None
            solution_type = type(solution)
            args_for_step_func: dict[str, Any] = _input_params or {}
            project_id = project_url.rstrip("/").split("/")[-1]
            project_files_dir = settings.computed_project_files_directory / project_id

            # load step params
            transaction_step_models: list[TransactionStepModel] = []
            for step_name, step_spec in kwargs.items():
                if step_name == "self":
                    step_type = step_self.__class__
                    step_name_str = _get_step_name_from_self(step_type, solution_type)
                else:
                    step_type = solution_type.get_steps_fields()[step_name]
                    step_name_str = step_name
                step_url = f"{project_url}/steps/{python_identifier_to_url_part(step_name_str)}"
                transaction_step_model = TransactionStepModel(
                    step_url=step_url,
                    step_spec=step_spec,
                    step_method=step_method_wrapper,  # pyright: ignore[reportArgumentType]
                    step_type=step_type,
                    http_client=http_client,
                    settings=settings,
                    project_files_dir=project_files_dir,
                    storage_scope=storage_scope,
                    graphql_client=graphql_client,
                    oidc_client=oidc_client,
                    asset_manager=asset_manager,
                    access_token=_access_token,
                    data_repository=_data_repository,
                    hps_blob_manager=_hps_blob_manager,
                )
                transaction_step_model.download()
                args_for_step_func[step_name] = transaction_step_model
                transaction_step_models.append(transaction_step_model)

            # load solution configuration params
            if _solution_configuration_param:
                args_for_step_func[_solution_configuration_param.name] = _get_solution_configuration(
                    http_client,
                    project_url,
                    _solution_configuration_param.type,
                )

            # Setting transaction thread-local variable for managing unshared products
            transaction_local.settings = settings
            transaction_local.project_directory = project_files_dir
            transaction_local.instance_system_factory = instance_system_factory
            transaction_local.multiplexor_storage_factory = _multiplexor_storage_factory

            # Setting transaction thread-local variable for HPS job submission API
            transaction_local.access_token = _access_token
            transaction_local.hps_blob_manager = _hps_blob_manager
            transaction_local.step_type = step_self.__class__

            try:
                if hasattr(step_func, "__wrapped__"):
                    # step_func is not the real step method, but a decorated function
                    # (@long_running, @create_instance or @instance)
                    # so let's pass the needed arguments
                    result = step_func(
                        step_self,
                        project_url,
                        solution,
                        name_of_step_containing_method,
                        settings,
                        http_client,
                        **args_for_step_func,
                    )
                else:
                    # step_func is the real step method: use only the arguments it needs
                    result = step_func(**args_for_step_func)

                for transaction_step_model in transaction_step_models:
                    transaction_step_model.upload()
            finally:
                for transaction_step_model in transaction_step_models:
                    transaction_step_model.release_live_file_locks()
            return result

        step_method_wrapper._wrapped_transaction_method = step_func  # pyright: ignore[reportAttributeAccessIssue]
        step_method_wrapper._transaction = kwargs  # pyright: ignore[reportAttributeAccessIssue]
        step_method_wrapper._enable_termination_event = (  # pyright: ignore[reportAttributeAccessIssue]
            enable_termination_event
        )
        step_method_wrapper._validate = _validate_transaction(  # pyright: ignore[reportAttributeAccessIssue]
            step_func,
            **kwargs,
        )
        step_method_wrapper._has_entity_handles = _has_entity_handles(  # pyright: ignore[reportAttributeAccessIssue]
            step_func,
            **kwargs,
        )
        return step_method_wrapper

    return decorator


def _get_solution_configuration(
    http_client: httpx2.Client,
    project_url: str,
    solution_configuration_type: type[TSolutionConfig],
) -> TSolutionConfig:
    solution_configuration_url = project_url.split("/projects/")[0] + "/solution-configuration"
    response = http_client.get(solution_configuration_url)
    response.raise_for_status()
    return solution_configuration_type.model_validate(response.json())


def categorize_transaction_parameters(
    method_type_hints: dict[str, Any],
    signature: inspect.Signature,
) -> tuple[dict[str, Any], SolutionConfigParam | None]:
    body_params: dict[str, Any] = {}
    solution_configuration_param: SolutionConfigParam | None = None
    for param_name, param_type in method_type_hints.items():
        if param_name == "return":
            continue
        # issubclass is raising the following exception 'arg 1 must be a class'
        # for generic types such as dict[...]
        # we are using get_origin to overcome this issue
        base_type = get_origin(param_type)
        if base_type is Annotated:
            base_type = param_type.__origin__
        origin_type = param_type if base_type is None else base_type
        if issubclass(origin_type, StepModel | ProductInstanceManager):
            continue
        if issubclass(origin_type, SolutionConfiguration):
            solution_configuration_param = SolutionConfigParam(name=param_name, type=param_type)
            continue
        param_signature = signature.parameters[param_name]
        default = ... if param_signature.default is inspect.Parameter.empty else param_signature.default
        body = Body(default)  # using Body as a way to annotate dynamic fields.
        body_params[param_name] = Annotated[param_type, body]

    return body_params, solution_configuration_param


def _build_body_model_from_transaction_body_parameters(method_id: str, body_params: dict[str, Any]) -> Any:
    try:
        # Let's create a dynamic pydantic model out of the @transaction body parameters,
        # to be used as a fastapi Body(), so that we get validation and documentation from fastapi and openapi
        DynamicTransactionBodyModel = create_model(  # noqa: N806
            "DynamicTransactionBodyModel",
            **body_params,
            __config__=ConfigDict(extra="forbid"),
        )
        return DynamicTransactionBodyModel
    except PydanticUserError:
        raise SolutionLoadException(
            f"Invalid parameter types for the @transaction '{method_id}'!"
            " Check that the parameters are valid pydantic field types.",
        ) from None


def build_pydantic_model_from_transaction_parameters(
    method: Callable[..., Any],
) -> tuple[Any, SolutionConfigParam | None]:
    method_type_hints = get_type_hints(method, include_extras=True)
    signature = inspect.signature(method)
    body_params, solution_configuration_param = categorize_transaction_parameters(
        method_type_hints,
        signature,
    )
    DynamicTransactionBodyModel = _build_body_model_from_transaction_body_parameters(  # noqa: N806
        method.__name__,
        body_params,
    )
    return DynamicTransactionBodyModel, solution_configuration_param
