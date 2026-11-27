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

"""
Authenticator
=============

A minimal Dash app showing how to use the
:class:`~ansys.solutions.dash_super_components.Authenticator` component.

See the `Authenticator
<https://upgraded-carnival-wn6lkym.pages.github.io/version/stable/api/dash-super-components/user-guide/authenticator.html#ref_authenticator>`_
page in the User Guide for the full reference documentation.

.. note::

   Run this file directly to launch the app:

   .. code-block:: bash

       pip install ansys-solutions-dash-super-components
       python example_authenticator.py

   Then open ``http://localhost:8050`` in your browser.
"""

# %%
# Set up the Dash application
# ---------------------------
#
# :class:`~dash_mantine_components.MantineProvider` must wrap the entire layout
# for Mantine-based components to render correctly.  The React version must also
# be set **before** importing the component library — this is a Dash Mantine
# Components requirement when using Dash 2.x.

from ansys.solutions.dash_super_components import Authenticator
from dash import _dash_renderer
from dash_extensions.enrich import DashProxy, Input, Output, State, callback, html
import dash_mantine_components as dmc

# Required only for Dash 2.x to use Mantine-based components
_dash_renderer._set_react_version("18.2.0")

app = DashProxy(__name__)

# %%
# Build the layout
# ----------------
#
# An ``Authenticator`` with email, username, password and a *Sign in* button.
# The Sign in button stays disabled until all three fields contain text —
# demonstrated via a callback below.

app.layout = dmc.MantineProvider(
    html.Div(
        [
            dmc.Title("Authenticator", order=2, mb="md"),
            dmc.Text(
                "Fill in all fields to enable the Sign in button.",
                c="dimmed",
                mb="xl",
            ),
            Authenticator(
                aio_id="custom-auth",
                items=[
                    {
                        "type": "TextInput",
                        "id": "email",
                        "properties": {
                            "label": "Email",
                            "placeholder": "Enter your email",
                            "required": True,
                        },
                    },
                    {
                        "type": "TextInput",
                        "id": "username",
                        "properties": {
                            "label": "Username",
                            "placeholder": "Enter your username",
                            "required": True,
                        },
                    },
                    {
                        "type": "PasswordInput",
                        "id": "password",
                        "properties": {
                            "label": "Password",
                            "placeholder": "Enter your password",
                            "required": True,
                        },
                    },
                    {
                        "type": "Button",
                        "id": "submit",
                        "properties": {
                            "children": "Sign in",
                        },
                    },
                ],
                card_props={"w": 400},
            ),
            dmc.Space(h=32),
            dmc.Text(id="auth-status", c="dimmed"),
        ],
        style={"maxWidth": 640, "margin": "40px auto", "padding": "0 16px"},
    )
)

# %%
# Add callback to toggle the Sign in button
# -----------------------------------------
#
# Use :attr:`Authenticator.ids.button`, :attr:`Authenticator.ids.input`, and
# :attr:`Authenticator.ids.password` to reference sub-components by their
# ``aio_id`` and item ``id``.  The Sign in button stays disabled until all
# three input fields contain text.


@callback(
    Output(Authenticator.ids.button("custom-auth", "submit"), "disabled"),
    Input(Authenticator.ids.input("custom-auth", "email"), "value"),
    Input(Authenticator.ids.input("custom-auth", "username"), "value"),
    Input(Authenticator.ids.password("custom-auth", "password"), "value"),
)
def enable_disable_connect_button(
    email: str | None, username: str | None, password: str | None
) -> bool:
    """Enable the Sign in button only when all three fields are filled."""
    return not bool(email and username and password)


# %%
# Dummy authentication callback
# -----------------------------
#
# In a real application replace the ``_authenticate`` and
# ``_get_user_display_name`` stubs below with calls to your actual
# authentication backend (for example, LDAP, OAuth 2.0, a REST API, …).


def _authenticate(email: str, username: str, password: str) -> bool:
    """Stub — replace with a real credential check against your backend."""
    # Example: return auth_client.verify(email=email, username=username, password=password)
    return True


def _get_user_display_name(username: str) -> str:
    """Stub — replace with a real user-profile lookup."""
    # Example: return user_service.get_display_name(username)
    return username


@callback(
    Output("auth-status", "children"),
    Input(Authenticator.ids.button("custom-auth", "submit"), "n_clicks"),
    State(Authenticator.ids.input("custom-auth", "email"), "value"),
    State(Authenticator.ids.input("custom-auth", "username"), "value"),
    State(Authenticator.ids.password("custom-auth", "password"), "value"),
    prevent_initial_call=True,
)
def on_sign_in(
    n_clicks: int | None,
    email: str | None,
    username: str | None,
    password: str | None,
) -> str:
    """Attempt authentication and update the status message."""
    if not n_clicks or not email or not username or not password:
        return ""

    # Replace _authenticate with your real authentication call.
    success = _authenticate(email, username, password)

    if success:
        display_name = _get_user_display_name(username)
        return f"Signed in as {display_name}."
    return "Authentication failed. Please check your credentials."


# %%
# Run the app
# -----------

if __name__ == "__main__":
    app.run()
