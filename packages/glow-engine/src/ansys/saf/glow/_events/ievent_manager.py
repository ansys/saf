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
from typing import Any, TypeAlias


class EventSourceIdentifier:
    def __init__(self, project_id: str, step_name: str, stream_name: str):
        self._project_id = project_id
        self._step_name = step_name
        self._stream_name = stream_name

    @property
    def project_id(self) -> str:
        return self._project_id

    @property
    def step_name(self) -> str:
        return self._step_name

    @property
    def stream_name(self) -> str:
        return self._stream_name


EventPayload: TypeAlias = Any  # a JSON derived structure # noqa: UP040


class IEventListener(ABC):
    @abstractmethod
    async def get_new_events_and_purge_queue(self) -> None | list[EventPayload]:
        """fetches all events that have not been processed by this listener

        Returns:
            None if the event source no longer exists, otherwise a list of event payloads
        """
        raise NotImplementedError()

    @abstractmethod
    async def destroy(self) -> None:
        """Cleans up any resources used by this listener"""
        raise NotImplementedError()


class IEventManager(ABC):
    @abstractmethod
    async def create_event_listener(self, event_source_identifier: EventSourceIdentifier) -> IEventListener:
        """Creates an event listener for the caller to receive events."""
        raise NotImplementedError()

    @abstractmethod
    async def store_event(self, event_source_identifier: EventSourceIdentifier, event: EventPayload) -> None:
        """Stores an event for transmission to listeners"""
        raise NotImplementedError()
