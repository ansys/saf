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

from abc import ABC, abstractmethod
from collections.abc import Iterable
from types import NoneType, UnionType
from typing import Any, Self, final, get_args, get_origin

from pydantic import BaseModel, Field, PrivateAttr, model_validator
from pydantic_settings import BaseSettings

from ansys.bdm.api import NO_ENTITY, EntityHandle, RecursiveDictionaryOfEntityHandles


class TypeContainingHandleTypeMismatchError(Exception):
    """Raised when there is a mismatch between expected and actual handle-containing types."""


class TypeContainingHandleWrapper(ABC):
    @abstractmethod
    def has_handles(self, ignore: "ModelContainingHandleTypeWrapper | None" = None) -> bool:
        """Indicates whether the object contains any entity handles."""
        ...

    @abstractmethod
    def get_handles(self, obj: Any, context: str) -> list[EntityHandle]:
        """Extracts entity handles from the given object."""
        ...


class IWrapperBuilder(ABC):
    @abstractmethod
    def build_handle_containing_type_wrapper(self, t: type[Any]) -> TypeContainingHandleWrapper:
        """Factory method to build a TypeContainingHandleWrapper for the given type."""
        ...

    @abstractmethod
    def register_forward_reference(self, t: type[Any], wrapper: TypeContainingHandleWrapper) -> None:
        """Registers a wrapper for a forward reference type."""
        ...


@final
class UnknownTypeContainingHandleWrapper(TypeContainingHandleWrapper):
    def has_handles(self, ignore: "ModelContainingHandleTypeWrapper | None" = None) -> bool:
        # we return False here - we simply assume that any unsupported type doesn't contain handles
        # this is just an assumption GC will break when this doesn't hold
        return False

    def get_handles(self, obj: Any, context: str) -> list[EntityHandle]:
        return []


class NoneContainingHandleTypeWrapper(TypeContainingHandleWrapper):
    def has_handles(self, ignore: "ModelContainingHandleTypeWrapper | None" = None) -> bool:
        return False

    def get_handles(self, obj: Any, context: str) -> list[EntityHandle]:
        if obj is not None:
            raise TypeContainingHandleTypeMismatchError(f"Expected None at {context}.")
        return []


class EntityHandleTypeWrapper(TypeContainingHandleWrapper):
    def has_handles(self, ignore: "ModelContainingHandleTypeWrapper | None" = None) -> bool:
        return True

    def get_handles(self, obj: Any, context: str) -> list[EntityHandle]:
        if not isinstance(obj, EntityHandle):
            raise TypeContainingHandleTypeMismatchError(f"Expected an EntityHandle instance at {context}.")
        return [] if obj == NO_ENTITY else [obj]


@final
class CollectionTypeContainingHandleTypeWrapper(TypeContainingHandleWrapper):
    def __init__(self, t: type[list[Any]] | type[set[Any]], builder: IWrapperBuilder):
        subtypes = get_args(t)
        subtypes_count = len(subtypes)
        if subtypes_count == 0:
            self._subtype_wrapper = UnknownTypeContainingHandleWrapper()
        elif subtypes_count == 1:
            subtype = subtypes[0]
            wrapper = builder.build_handle_containing_type_wrapper(subtype)
            self._subtype_wrapper = wrapper
        else:
            raise TypeContainingHandleTypeMismatchError(
                f"Expected a single subtype for collection {t}, but found {len(subtypes)} subtypes.",
            )

    def has_handles(self, ignore: "ModelContainingHandleTypeWrapper | None" = None) -> bool:
        return self._subtype_wrapper.has_handles(ignore)

    def get_handles(self, obj: Any, context: str) -> list[EntityHandle]:
        if not isinstance(obj, Iterable):
            raise TypeContainingHandleTypeMismatchError(f"Expected Iterable at {context}.")
        handles: list[EntityHandle] = []
        for i, item in enumerate(obj):  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
            item_context = f"{context}[{i}]"
            handles.extend(self._subtype_wrapper.get_handles(item, item_context))
        return handles


@final
class DictionaryContainingHandleTypeWrapper(TypeContainingHandleWrapper):
    def __init__(self, t: type[Any], builder: IWrapperBuilder):
        subtypes = get_args(t)
        subtypes_count = len(subtypes)
        if subtypes_count == 0:
            self._subtype_wrappers = [UnknownTypeContainingHandleWrapper(), UnknownTypeContainingHandleWrapper()]
        elif subtypes_count == 2:
            self._subtype_wrappers = [builder.build_handle_containing_type_wrapper(subtype) for subtype in subtypes]
        else:
            raise TypeContainingHandleTypeMismatchError(f"Expected two subtypes for dictionary at {t}.")

    def has_handles(self, ignore: "ModelContainingHandleTypeWrapper | None" = None) -> bool:
        return any(wrapper.has_handles(ignore) for wrapper in self._subtype_wrappers)

    def get_handles(self, obj: Any, context: str) -> list[EntityHandle]:
        if not isinstance(obj, dict):
            raise TypeContainingHandleTypeMismatchError(f"Expected dict at {context}.")
        handles: list[EntityHandle] = []
        content: list[Iterable[Any]] = [obj.keys(), obj.values()]
        function_names = ["keys", "values"]
        for subtype_wrapper, items, func_name in zip(self._subtype_wrappers, content, function_names, strict=True):
            if subtype_wrapper.has_handles():
                for i, item in enumerate(items):
                    item_context = f"{context}.{func_name}()[{i}]"
                    handles.extend(subtype_wrapper.get_handles(item, item_context))

        return handles


@final
class UnionContainingHandleTypeWrapper(TypeContainingHandleWrapper):
    def __init__(self, t: UnionType, builder: IWrapperBuilder):
        subtypes = get_args(t)
        self._subtype_wrappers = [
            handle_subtype
            for handle_subtype in (builder.build_handle_containing_type_wrapper(subtype) for subtype in subtypes)
            if handle_subtype.has_handles()
        ]

    def has_handles(self, ignore: "ModelContainingHandleTypeWrapper | None" = None) -> bool:
        return any(wrapper.has_handles(ignore) for wrapper in self._subtype_wrappers)

    def get_handles(self, obj: Any, context: str) -> list[EntityHandle]:
        for subtype_wrapper in self._subtype_wrappers:
            try:
                return subtype_wrapper.get_handles(obj, context)
            except TypeContainingHandleTypeMismatchError:
                continue
        return []


@final
class ModelContainingHandleTypeWrapper(TypeContainingHandleWrapper):
    def __init__(self, t: type[BaseModel], builder: IWrapperBuilder):
        builder.register_forward_reference(t, self)
        self._model_type = t
        self._field_wrappers: dict[str, TypeContainingHandleWrapper] = {}
        for field_name, field_info in t.model_fields.items():
            annotation = field_info.annotation
            if annotation is not None:
                wrapper = builder.build_handle_containing_type_wrapper(annotation)
                self._field_wrappers[field_name] = wrapper

        # We determine whether to keep field wrappers based on whether they have handle
        # as a second step to handle recursion where the recursive field can be in any order
        # relative to the non-recursive fields.
        # We are careful to avoid generating a field wrapper for this model type if
        # the model type is recursive but nothing in the model contains handles, as otherwise we
        # would end up with field wrappers that traverse the entire recursive object instance structure
        # just to find that there are no handles.
        if any(wrapper.has_handles(ignore=self) for wrapper in self._field_wrappers.values()):
            for field_name in t.model_fields:
                if field_name in self._field_wrappers and not self._field_wrappers[field_name].has_handles():
                    del self._field_wrappers[field_name]
        else:
            self._field_wrappers = {}

    def has_handles(self, ignore: "ModelContainingHandleTypeWrapper | None" = None) -> bool:
        if ignore == self:
            return False
        return any(wrapper.has_handles(ignore=self) for wrapper in self._field_wrappers.values())

    def field_has_handles(self, field_name: str) -> bool:
        return field_name in self._field_wrappers

    def get_handles(self, obj: Any, context: str) -> list[EntityHandle]:
        if not isinstance(obj, self._model_type):
            raise TypeContainingHandleTypeMismatchError(f"Expected an instance of {self._model_type} at {context}.")
        handles: list[EntityHandle] = []
        for field_name, field_wrapper in self._field_wrappers.items():
            field_value = getattr(obj, field_name, None)
            field_context = f"{context}.{field_name}"
            handles.extend(field_wrapper.get_handles(field_value, field_context))
        return handles


@final
class TupleContainingHandleTypeWrapper(TypeContainingHandleWrapper):
    def __init__(self, t: type[tuple[Any, ...]], builder: IWrapperBuilder):
        subtypes = get_args(t)
        self._subtype_wrappers = [builder.build_handle_containing_type_wrapper(subtype) for subtype in subtypes]

    def has_handles(self, ignore: "ModelContainingHandleTypeWrapper | None" = None) -> bool:
        return any(wrapper.has_handles(ignore) for wrapper in self._subtype_wrappers)

    def get_handles(self, obj: Any, context: str) -> list[EntityHandle]:
        if not isinstance(obj, tuple):
            raise TypeContainingHandleTypeMismatchError(f"Expected tuple at {context}.")
        if len(obj) != len(self._subtype_wrappers):  # pyright: ignore[reportUnknownArgumentType]
            raise TypeContainingHandleTypeMismatchError(
                f"Expected tuple of length {len(self._subtype_wrappers)} at {context}.",
            )
        handles: list[EntityHandle] = []
        for i, (item, subtype_wrapper) in enumerate(  # pyright: ignore[reportUnknownVariableType]
            zip(obj, self._subtype_wrappers, strict=True),  # pyright: ignore[reportUnknownArgumentType]
        ):
            if subtype_wrapper.has_handles():
                item_context = f"{context}[{i}]"
                handles.extend(subtype_wrapper.get_handles(item, item_context))
        return handles


class RecursiveDictionaryContainingHandleTypeWrapper(TypeContainingHandleWrapper):
    def has_handles(self, ignore: "ModelContainingHandleTypeWrapper | None" = None) -> bool:
        return True

    def get_handles(self, obj: Any, context: str) -> list[EntityHandle]:
        if not isinstance(obj, RecursiveDictionaryOfEntityHandles):
            raise TypeContainingHandleTypeMismatchError(f"Expected RecursiveDictionaryOfEntityHandles at {context}.")
        handles: list[EntityHandle] = []

        def _extract_handles_from_dict(d: RecursiveDictionaryOfEntityHandles, ctx: str) -> None:
            # in the following we check the types carefully in case a solution developer has gone off piste
            # hence the pyright ignore annotations

            for key, value in d.items():
                if isinstance(value, EntityHandle):
                    if value != NO_ENTITY:
                        handles.append(value)
                elif isinstance(value, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
                    _extract_handles_from_dict(value, f"{ctx}['{key}']")  # pyright: ignore[reportUnreachable]
                else:
                    raise TypeContainingHandleTypeMismatchError(
                        "Within RecursiveDictionaryOfEntityHandles expected EntityHandle or "
                        + f"RecursiveDictionaryOfEntityHandles at {ctx}['{key}'].  Instead got {type(value)}.",
                    )

        _extract_handles_from_dict(obj, context)
        return handles


def _safe_issubclass(t: type[Any], classinfo: type) -> bool:
    try:
        return issubclass(t, classinfo)
    except TypeError:
        return False


class GCSettings(BaseSettings):
    glow_bdm_gc_disabled: bool = Field(default=False)


def is_bdm_gc_disabled() -> bool:
    return GCSettings().glow_bdm_gc_disabled


class WrapperBuilder(IWrapperBuilder):
    def __init__(self):
        self._wrapper_dict: dict[type[Any], TypeContainingHandleWrapper] = {}

    def register_forward_reference(self, t: type[Any], wrapper: TypeContainingHandleWrapper):
        """Registers a wrapper for a forward reference type."""
        self._wrapper_dict[t] = wrapper

    def build_handle_containing_type_wrapper(self, t: type[Any]) -> TypeContainingHandleWrapper:
        """Factory method to build a TypeContainingHandleWrapper for the given type."""
        wrapper = self._wrapper_dict.get(t)
        if wrapper is None:
            wrapper = self._build_handle_containing_type_wrapper(t)
            self._wrapper_dict[t] = wrapper
        return wrapper

    def _build_handle_containing_type_wrapper(self, t: type[Any]) -> TypeContainingHandleWrapper:
        if t is EntityHandle or _safe_issubclass(t, EntityHandle):
            return EntityHandleTypeWrapper()
        elif t is NoneType:
            return NoneContainingHandleTypeWrapper()
        elif get_origin(t) in (list, set):
            return CollectionTypeContainingHandleTypeWrapper(t, self)  # pyright: ignore[reportUnknownArgumentType]
        elif get_origin(t) is tuple:
            return TupleContainingHandleTypeWrapper(t, self)  # pyright: ignore[reportUnknownArgumentType]
        elif get_origin(t) is dict:
            return DictionaryContainingHandleTypeWrapper(t, self)
        elif isinstance(t, UnionType):  # pyright: ignore[reportUnnecessaryIsInstance]
            return UnionContainingHandleTypeWrapper(t, self)  # pyright: ignore[reportUnreachable]
        elif _safe_issubclass(t, BaseModel):
            return ModelContainingHandleTypeWrapper(t, self)
        elif t is RecursiveDictionaryOfEntityHandles or _safe_issubclass(t, RecursiveDictionaryOfEntityHandles):
            return RecursiveDictionaryContainingHandleTypeWrapper()
        else:
            return UnknownTypeContainingHandleWrapper()


class LiveHandlesModel(BaseModel):
    """Base class for models that need to be tracked by the BDM garbage collector."""

    _entity_handle_fields: ModelContainingHandleTypeWrapper = PrivateAttr()
    """ A tree representing the type structure of the model that covers the subset of the
    structure containing entity handles.  It provides functionality to extract those handles from
    a model instance.
    """

    @model_validator(mode="after")
    def _set_entity_handle_fields(self) -> Self:
        self._entity_handle_fields = ModelContainingHandleTypeWrapper(self.__class__, WrapperBuilder())
        return self

    @property
    def has_handle_fields(self) -> bool:
        "for testing purposes - indicates whether live_handles property will traverse the object"
        return self._entity_handle_fields.has_handles()

    @property
    def live_handles(self) -> list[EntityHandle]:
        return self._entity_handle_fields.get_handles(self, "")
