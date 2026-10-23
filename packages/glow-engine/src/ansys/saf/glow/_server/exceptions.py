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

from typing import Any

from fastapi import HTTPException

malformed_solution_error_prefix = "The solution definition is invalid"
malformed_database_error_prefix = "The database schema is invalid"
method_called_out_of_sequence_error_prefix = "The method has been called out of sequence."
bad_request_exception_prefix = "Bad Request:"

INTERNAL_ERROR_MESSAGE = "The solution encountered an internal error and was unable to complete the request. "


class GlowErrorBase(HTTPException):
    """Base class for all solution errors occurring server-side."""


class BadRequestError(GlowErrorBase):
    """The server cannot or will not process the request due to an apparent client error
    (e.g., malformed request syntax, size too large, invalid request message framing, or deceptive request routing).
    """

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=400, detail=detail)


class UnauthorizedError(GlowErrorBase):
    """For use when authentication is required and has failed or has not yet been provided."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=401, detail=detail)


class ForbiddenError(GlowErrorBase):
    """The request contained valid data and was understood by the server, but the server is refusing action.
    This may be due to the user not having the necessary permissions for a resource or needing an account of some sort,
    or attempting a prohibited action (e.g. creating a duplicate record where only one is allowed).
    """

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=403, detail=detail)


class NotFoundError(GlowErrorBase):
    """The requested resource could not be found but may be available in the future."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=404, detail=detail)


class RequestTimeoutError(GlowErrorBase):
    """The server timed out waiting for the request."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=408, detail=detail)


class ConflictError(GlowErrorBase):
    """Indicates that the request could not be processed because of conflict in the current state of the resource,
    such as an edit conflict between multiple simultaneous updates.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=409, detail=detail)


class GoneError(GlowErrorBase):
    """The requested resource is no longer available"""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=410, detail=detail)


class UnsupportedMediaTypeError(GlowErrorBase):
    """The request entity has a media type which the server or resource does not support."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=415, detail=detail)


class UnprocessableEntityError(GlowErrorBase):
    """The request was well-formed but was unable to be followed due to semantic errors."""

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=422, detail=detail)


class LockedError(GlowErrorBase):
    """The resource that is being accessed is locked.

    ``detail`` can be a dictionary, e.g. ``{"message": ..., "holder_id": ...}`` for project write locks.
    """

    def __init__(self, detail: str | dict[str, Any]) -> None:
        super().__init__(status_code=423, detail=detail)


class InternalError(GlowErrorBase):
    """A generic error message, given when an unexpected condition was encountered
    and no more specific message is suitable.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(status_code=500, detail=detail)


class MalformedSolutionError(InternalError):
    """An internal error thrown when the solution is known to be invalid."""

    def __init__(self, detail: str) -> None:
        message = f"{malformed_solution_error_prefix}: {detail}"
        super().__init__(detail=message)


class MalformedDatabaseError(InternalError):
    """An internal error thrown when the database is known to be invalid."""

    def __init__(self, detail: str) -> None:
        message = f"{malformed_database_error_prefix}: {detail}"
        super().__init__(detail=message)


EXCEPTIONS_BY_CODE: dict[int, type[Exception]] = {
    400: BadRequestError,
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
    408: RequestTimeoutError,
    409: ConflictError,
    415: UnsupportedMediaTypeError,
    422: UnprocessableEntityError,
    423: LockedError,
    500: InternalError,
}
