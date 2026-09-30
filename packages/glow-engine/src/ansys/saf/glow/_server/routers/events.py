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

import asyncio
from json import JSONDecodeError
import logging

from ansys.iam.oidc import get_websocket_subprotocol
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from wsproto.utilities import LocalProtocolError

from ansys.saf.glow._events.ievent_manager import EventPayload, EventSourceIdentifier
from ansys.saf.glow._server.dependencies import (
    EventManagerDep,
    SettingsDep,
    WSEventManagerDep,
    oidc_scheme_with_api_key,
    oidc_scheme_ws_with_roles,
    validate_project,
    validate_project_for_websocket,
    validate_step,
    validate_step_for_websocket,
)
from ansys.saf.glow._utilities.conversion import url_part_to_python_identifier

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["events"])


async def _websocket_connected(websocket: WebSocket) -> bool:
    # We need something to detect that the websocket wasn't closed and close the connection if it did.
    # In FastAPI doc, they use this same receive() method, which besides waiting for a message also checks
    # the websocket status and raises disconnect exception. We do the same, although we don't expect to receive
    # any message and don't want to wait for it.
    try:
        await asyncio.wait_for(websocket.receive(), timeout=0.1)
    except TimeoutError:
        pass
    except RuntimeError:
        # If the client has disconnected, the receive() call will raise a RuntimeError
        # We catch that error and treat it as a disconnection.
        return False
    return True


def _create_event_source(project_id: str, step_id: str, stream_name: str) -> EventSourceIdentifier:
    return EventSourceIdentifier(
        project_id=project_id,
        step_name=url_part_to_python_identifier(step_id),
        stream_name=url_part_to_python_identifier(stream_name),
    )


def _message_summary(message: EventPayload) -> str:
    full_text = str(message)
    if len(full_text) > 60:
        return full_text[:60] + "..."
    return full_text


@router.post(
    "/projects/{project_id}/steps/{step_id}/streams/{stream_name}",
    # auth must be validated before project and step existence to avoid information leak.
    dependencies=[Depends(oidc_scheme_with_api_key), Depends(validate_project), Depends(validate_step)],
)
async def store_event(
    project_id: str,
    step_id: str,
    stream_name: str,
    request: Request,
    event_manager: EventManagerDep,
) -> None:
    try:
        data = await request.json()
    except JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON") from e
    logger.info(
        f"Storing event stream {stream_name}, payload {_message_summary(data)} "
        f"- for project {project_id}, step {step_id}",
    )
    event_source = _create_event_source(project_id, step_id, stream_name)
    await event_manager.store_event(event_source, data)


@router.websocket(
    "/projects/{project_id}/steps/{step_id}/streams/{stream_name}",
    # auth must be validated before project and step existence to avoid information leak.
    dependencies=[
        Depends(oidc_scheme_ws_with_roles),
        Depends(validate_project_for_websocket),
        Depends(validate_step_for_websocket),
    ],
)
async def stream_event(
    websocket: WebSocket,
    project_id: str,
    step_id: str,
    stream_name: str,
    event_manager: WSEventManagerDep,
    settings: SettingsDep,
) -> None:
    context = f"stream: {stream_name} step: {step_id} project: {project_id}"
    logger.info(f"Streaming events for {context}")
    subprotocol = get_websocket_subprotocol(websocket)
    await websocket.accept(subprotocol=subprotocol)
    logger.debug(f"web socket accepted for {context}")
    event_source = _create_event_source(project_id, step_id, stream_name)
    event_listener = await event_manager.create_event_listener(event_source)
    logger.debug(f"event listener created for {context}")
    messages: None | list[EventPayload] = []
    try:
        while await _websocket_connected(websocket):
            messages = await event_listener.get_new_events_and_purge_queue()
            if messages is None:
                logger.debug(f"event source no longer exists, exiting processing loop {context}")
                return
            for message in messages:
                logger.debug(f"sending event to websocket {_message_summary(message)} {context}")
                await websocket.send_json(message)
                logger.debug(f"event sent {context}")
                # this sleep seems to be essential to ensure all messages reach the Dash callback
                # something in the infrastructure can't cope when the message frequency is too high.
                await asyncio.sleep(0.1)
            await asyncio.sleep(
                settings.glow_ws_event_poll_interval,
            )  # sleep between requests for events to avoid overloading the repository
        logger.info(f"websocket disconnected (on receive) {context}")
    except WebSocketDisconnect:
        logger.info(f"websocket disconnected (on transmit) {context}")
    except LocalProtocolError:
        # according to the documentation this is incorrect but I kept seeing disconnections raising this error so....
        logger.info(f"websocket disconnected (on transmit) {context}")
    finally:
        if messages is not None:
            logger.debug(f"destroying event listener {context}")
            await event_listener.destroy()
