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

import logging
import socket
import time

import httpx2

from ansys.saf.desktop.orchestrator._config.schema import LOCALHOST_IP

logger = logging.getLogger(__name__)


def next_free_port(port: int, max_port: int = 65535) -> int:
    """Return a port string for the first free socket port in a given
    range.

    This function should be used as a convenience. It is possible that given the
    same port number this function running concurrently will encounter a race
    condition because this function does not reserve a port. It is recommended
    that where possible the 'port' parameter is set to a value unique to the given
    case.

    Parameters
    ----------
    port : int
        first port number to try and number to start a scan for a free port on
    max_port : int, optional
        last port in range to try

    Returns
    -------
    str
        currently free port
    """
    while port <= max_port and not port_is_free(port):
        port = port + 1
    if port > max_port:
        raise OSError("no free ports")
    return port


def get_random_free_port() -> int:
    """Return a free socket port. Handled by the OS."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("", 0))
            return sock.getsockname()[1]
        except OSError as err:
            raise OSError("no free ports") from err


def port_is_free(port: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.connect(("127.0.0.1", port))
        except OSError:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.bind(("127.0.0.1", port))
                return True
            except OSError:
                return False
    return False


def wait_for_response(url: str, tries: int = 30, interval: float = 5):
    """Wait for GET to be successful (HTTP code 200) on a given URL.

    If the final attempt fails an exception is raised

    Parameters
    ----------
    url : string
        URL for which the GET is attempted
    tries : integer
        Number of attempts
    interval : number
        Interval between attempts in seconds

    Returns
    -------
    None
    """

    if tries < 1:
        raise RuntimeError("tries is less than one")
    if tries != int(tries):
        raise RuntimeError("tries is not an integer")
    if interval < 0:
        raise RuntimeError("interval is less than zero")

    response = try_response(url)
    i = tries - 1
    while not response:
        if i == 0:
            raise RuntimeError("Error: unable to reach " + url)
        logger.debug(f"Waiting {interval}s. (To give " + url + " time to respond)")
        time.sleep(interval)
        response = try_response(url)
        i = i - 1


def try_response(url: str) -> bool:
    """Return whether GET is successful (HTTP code 200) on a given
    URL.

    will return false if unable to connect or if HTTP code is not 200

    Parameters
    ----------
    url : string
        URL for which the GET is attempted

    Returns
    -------
    bool :
        whether a GET on the given url is successful
    """
    try:
        logger.debug(f"trying {url}")
        with httpx2.Client(timeout=60) as http_client:
            return http_client.get(url).status_code == 200
    except httpx2.HTTPError:  # https://httpx2.pydantic.dev/exceptions/
        return False


def get_local_ip():
    """Returns the unique ipv4 address of this node.

    Returns
    -------
    str :
        the unique ipv4 address of this node
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


def resolve_ip(ip_or_url: str) -> str:
    """
    Checks if the provided IP or URL contains 0.0.0.0 and replaces it with the localhost IP.

    Parameters
    ----------
    ip_or_url : str
        The input IP address or URL.

    Returns
    -------
    str:
        The modified IP or URL with 0.0.0.0 replaced by the local host IP (127.0.0.1).
    """
    if "0.0.0.0" in ip_or_url:  # noqa: S104
        return ip_or_url.replace("0.0.0.0", LOCALHOST_IP)  # noqa S104

    return ip_or_url
