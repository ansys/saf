# ruff: noqa
# AUTO GENERATED FILE - DO NOT EDIT

import typing  # noqa: F401
from typing_extensions import TypedDict, NotRequired, Literal # noqa: F401
from dash.development.base_component import Component, _explicitize_args
try:
    from dash.types import NumberType  # noqa: F401
except ImportError:
    # Backwards compatibility for dash<=4.1.0
    if typing.TYPE_CHECKING:
        raise
    NumberType = typing.Union[  # noqa: F401
        typing.SupportsFloat, typing.SupportsInt, typing.SupportsComplex
    ]

ComponentSingleType = typing.Union[str, int, float, Component, None]
ComponentType = typing.Union[
    ComponentSingleType,
    typing.Sequence[ComponentSingleType],
]


class ProjectInfo(Component):
    """A ProjectInfo component.


Keyword arguments:

- project (dict; required):
    Project to show in the modal.

    `project` is a dict with keys:

    - name (string; required):
        The URI path identifying the project resource (e.g.,
        \"projects/2ztdlpa2\").

    - display_name (string; required):
        The project name displayed to the user.

    - description (string; optional):
        Optional project description.

    - date_created (string; optional):
        Date and time of creation (ISO 8601 format).

    - date_modified (string; optional):
        Date and time of last modification (ISO 8601 format).

    - icon (string; optional):
        URL for the project icon (per-project custom icon from the
        API)."""
    _children_props: typing.List[str] = []
    _base_nodes = ['children']
    _namespace = 'ansys_saf_projects_dashboard'
    _type = 'ProjectInfo'
    Project = TypedDict(
        "Project",
            {
            "name": str,
            "display_name": str,
            "description": NotRequired[str],
            "date_created": NotRequired[str],
            "date_modified": NotRequired[str],
            "icon": NotRequired[str]
        }
    )


    def __init__(
        self,
        project: typing.Optional["Project"] = None,
        onClose: typing.Optional[typing.Any] = None,
        onOpen: typing.Optional[typing.Any] = None,
        **kwargs
    ):
        self._prop_names = ['project']
        self._valid_wildcard_attributes =            []
        self.available_properties = ['project']
        self.available_wildcard_properties =            []
        _explicit_args = kwargs.pop('_explicit_args')
        _locals = locals()
        _locals.update(kwargs)  # For wildcard attrs and excess named props
        args = {k: _locals[k] for k in _explicit_args}

        for k in ['project']:
            if k not in args:
                raise TypeError(
                    'Required argument `' + k + '` was not specified.')

        super(ProjectInfo, self).__init__(**args)

setattr(ProjectInfo, "__init__", _explicitize_args(ProjectInfo.__init__))
