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

"""Utilities to create standardized AIO (All-In-One) Dash component IDs."""

from typing import Any

try:
    # dash-extensions < 2.0.5
    from dash_extensions.enrich import _Wildcard  # pyright: ignore[reportAttributeAccessIssue]
except ImportError:
    # dash-extensions >= 2.0.5
    from dash_extensions.enrich import (
        Wildcard as _Wildcard,  # pyright: ignore[reportAttributeAccessIssue]
    )


class AIOIds:
    """Provide a base class for AIO component ID namespaces.

    Subclass this in each AIO component and add one ``@classmethod`` per subcomponent.
    Each class method should call :meth:`make_id_dict` with the component name, the
    subcomponent name, and the ``aio_id``.

    Assigning the subclass (not an instance) to a class-level ``ids`` attribute on the
    component preserves the ``ids.label(aio_id)`` call-site API and enables full IDE
    auto-complete for all subcomponent names.

    Examples
    --------
    Create a custom IDs class for a component:

    >>> class MyComponent(html.Div):
    ...
    ...     class MyComponentIds(AIOIds):
    ...         @classmethod
    ...         def label(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
    ...             return cls.make_id_dict("my-component", "label", aio_id)
    ...
    ...         @classmethod
    ...         def button(cls, aio_id: str | _Wildcard) -> dict[str, Any]:
    ...             return cls.make_id_dict("my-component", "button", aio_id)
    ...
    ...     ids = MyComponentIds
    """

    @classmethod
    def make_id_dict(cls, component: str, subcomponent: str | _Wildcard, aio_id: str | _Wildcard) -> dict[str, Any]:
        """Return a standardized dict-style ID for Dash pattern-matching callbacks.

        The returned dict follows the pattern expected by Dash pattern-matching callbacks:
        ``{"component": component, "subcomponent": subcomponent, "aio_id": aio_id}``.

        Parameters
        ----------
        component : str
            The name of the component.
        subcomponent : str or _Wildcard
            The name of the subcomponent.
        aio_id : str or _Wildcard
            The component's unique identifier.

        Returns
        -------
        dict[str, Any]
            The standardized ID dictionary for Dash pattern-matching callbacks.
        """
        return {"component": component, "subcomponent": subcomponent, "aio_id": aio_id}
