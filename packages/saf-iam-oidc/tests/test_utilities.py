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

import base64
from typing import Any
from unittest.mock import Mock

import pytest

from ansys.iam.oidc._fastapi import DEFAULT_SUBPROTOCOL_PREFIX, get_websocket_subprotocol
from ansys.iam.oidc._utilities import decode_base64_token, encode_base64_token


def test_encode_decode_round_trip_jwt_token(dummy_jwt_token: str) -> None:
    assert decode_base64_token(encode_base64_token(dummy_jwt_token)) == dummy_jwt_token


def test_encode_decode_round_trip_special_and_unicode_characters() -> None:
    original = "token+with/special=chars&symbols!@#$%^*()_+-={}[]|\\:;\"'<>?,.~`and_unicode: café, naïve, résumé, 北京"
    assert decode_base64_token(encode_base64_token(original)) == original


def test_encoded_token_has_no_padding() -> None:
    token = "a"
    encoded = base64.b64encode(token.encode("utf-8")).decode("utf-8")
    assert "=" in encoded
    assert len(encoded) % 4 == 0
    encoded_without_padding = encode_base64_token(token)
    assert "=" not in encoded_without_padding
    assert len(encoded_without_padding) % 4 != 0


def test_encoded_token_is_url_safe() -> None:
    token = "This string contains characters that will produce + and / in standard base64 encoding: >>>???"
    default_encoded = base64.b64encode(token.encode("utf-8")).decode("utf-8")
    assert "+" in default_encoded
    assert "/" in default_encoded
    encoded = encode_base64_token(token)
    assert "+" not in encoded
    assert "/" not in encoded


@pytest.mark.parametrize(("token", "encoded_token"), [("a", "YQ"), ("ab", "YWI"), ("abc", "YWJj")])
def test_decode_padding_is_restored(token: str, encoded_token: str) -> None:
    token_with_padding = encoded_token + ("=" * ((4 - len(encoded_token) % 4) % 4))
    assert len(token_with_padding) % 4 == 0
    assert decode_base64_token(encoded_token) == decode_base64_token(token_with_padding) == token


def test_decode_invalid_base64_raises_error() -> None:
    with pytest.raises(ValueError, match="Token cannot be decoded"):
        decode_base64_token("this is not base64 at all")


def test_decode_url_unsafe_token() -> None:
    assert decode_base64_token("Pj4+Pz8/") == ">>>???"


@pytest.mark.parametrize("prefix", [DEFAULT_SUBPROTOCOL_PREFIX, "custom.auth."])
def test_get_websocket_subprotocol_with_matching_prefix(prefix: str) -> None:
    """Test get_websocket_subprotocol returns the first subprotocol that matches the prefix."""
    mock_websocket = Mock()
    mock_websocket.scope = {"subprotocols": [f"{prefix}token123", "other-protocol"]}
    args: Any = {}
    if prefix != DEFAULT_SUBPROTOCOL_PREFIX:
        args["subprotocol_prefix"] = prefix
    assert get_websocket_subprotocol(mock_websocket, **args) == f"{prefix}token123"


@pytest.mark.parametrize("header_value", [None, "", "other-protocol"])
def test_get_websocket_subprotocol_empty_header(header_value: str | None) -> None:
    mock_websocket = Mock()
    if header_value is None:
        mock_websocket.scope = {}
    else:
        mock_websocket.scope = {"subprotocols": [header_value]}
    assert get_websocket_subprotocol(mock_websocket) is None


def test_get_websocket_subprotocol_multiple_matching_subprotocols() -> None:
    mock_websocket = Mock()
    mock_websocket.scope = {
        "subprotocols": [f"{DEFAULT_SUBPROTOCOL_PREFIX}first", f"{DEFAULT_SUBPROTOCOL_PREFIX}second", "other-protocol"],
    }
    assert get_websocket_subprotocol(mock_websocket) == f"{DEFAULT_SUBPROTOCOL_PREFIX}first"
