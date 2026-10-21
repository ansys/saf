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

import json
import logging
import os
import queue
from typing import Any

import gql
from gql import Client
from gql.transport.exceptions import TransportServerError
from gql.transport.requests import RequestsHTTPTransport
from graphql import DocumentNode
from opentelemetry import propagate

from ansys.saf.glow._access.principal import ON_BEHALF_OF_HEADER
from ansys.saf.glow._config.const import GLOW_GRAPHQL_POOL_SIZE
from ansys.saf.glow._core.client_exceptions import PermissionException, UnauthorizedException, raise_for_graphql_status

logger = logging.getLogger(__name__)


class GqlClientConnectionPool:
    """The graphql client is not thread safe. This leads to the following exception when used from DashClient:
    ``gql.transport.exceptions.TransportAlreadyConnected: Transport is already connected``
    The reason for this is, that one thread is trying to call ``connect()`` on the transport object when calling
    ``with gql_client as session:``, although it is already connected by another thread.
    This class is therefore used to ensure thread-safety when using gql.
    See: https://github.com/graphql-python/gql/issues/314
    """

    def __init__(
        self,
        url: str,
        pool_size: int = 3,
        access_token: str | None = None,
        api_key: str | None = None,
        on_behalf_of: str | None = None,
    ):
        self._queue: queue.Queue[Client] = queue.Queue()
        self._pool_size = int(os.environ.get(GLOW_GRAPHQL_POOL_SIZE, 0)) or pool_size
        self.access_token = access_token
        self.api_key = api_key
        # Id of the user on whose behalf requests authenticated with the API key are made.
        self.on_behalf_of = on_behalf_of
        for _ in range(self._pool_size):
            client = Client(
                transport=RequestsHTTPTransport(
                    url=url,
                    retries=10,
                    retry_backoff_factor=1,
                ),
            )
            self._queue.put(client)

    def _execute(self, query: DocumentNode, **kwargs: Any) -> dict[str, Any]:
        client = self._queue.get(timeout=60)
        with client as session:
            if session.transport.headers is None:  # type: ignore
                session.transport.headers = {}  # type: ignore
            if self.api_key:
                session.transport.headers["x-api-key"] = self.api_key  # type: ignore
                session.transport.headers.pop("Authorization", None)  # type: ignore
                if self.on_behalf_of:
                    session.transport.headers[ON_BEHALF_OF_HEADER] = self.on_behalf_of  # type: ignore
                else:
                    session.transport.headers.pop(ON_BEHALF_OF_HEADER, None)  # type: ignore
            elif self.access_token:
                session.transport.headers["Authorization"] = f"Bearer {self.access_token}"  # type: ignore
                session.transport.headers.pop("x-api-key", None)  # type: ignore
                session.transport.headers.pop(ON_BEHALF_OF_HEADER, None)  # type: ignore
            else:
                session.transport.headers.pop("Authorization", None)  # type: ignore
                session.transport.headers.pop("x-api-key", None)  # type: ignore
                session.transport.headers.pop(ON_BEHALF_OF_HEADER, None)  # type: ignore

            propagate.inject(session.transport.headers)  # type: ignore
            response = session.execute(query, **kwargs)  # type: ignore
        self._queue.put(client)

        return response  # type: ignore

    def run_query(
        self,
        request_string: str,
        payload: dict[str, Any],
    ) -> None:
        variable_values = get_variable_values(payload)
        mutation = gql.gql(request_string)
        try:
            result = self._execute(mutation, variable_values=variable_values)["update_project_steps_with_json"]
        except TransportServerError as ex:
            if ex.code == 403:
                raise PermissionException("Not authenticated") from None
            elif ex.code == 401:
                raise UnauthorizedException("Not authenticated") from None
            raise
        raise_for_graphql_status(result)


def get_update_project_steps_request_str(
    payload: dict[str, Any],
    project_id: str,
    step_name: str,
) -> str | None:
    field_map = ", ".join([f"{name}: ${name}" for name in payload])
    arguments = ", ".join([f"${name}: String!" for name in payload])
    if arguments:
        return f"""
        mutation({arguments}) {{
            update_project_steps_with_json(
                project_id: "{project_id}", steps : {{ {step_name} : {{ {field_map} }} }}
            )
            {{ status, error }}
        }}
        """


def get_variable_values(payload: dict[str, Any]) -> dict[str, Any]:
    return {name: json.dumps(value) for name, value in payload.items()}
