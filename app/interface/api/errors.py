"""Shared HTTP error helpers and validation handlers."""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.governance import PolicyViolation
from app.interface.dto.errors import ErrorBody, ErrorEnvelope


class ApiError(Exception):
    """Structured API exception for dependency and handler-level failures."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def serialize_validation_errors(
    exc: ValidationError | RequestValidationError,
) -> list[dict[str, Any]]:
    """Return JSON-safe validation errors for the public error envelope."""
    return json.loads(json.dumps(exc.errors(), default=str))


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the stable JSON error envelope used by the API."""
    payload = ErrorEnvelope(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers=headers,
    )


async def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Normalize FastAPI request validation failures into the public error shape."""
    del request
    return error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="INVALID_REQUEST",
        message="Request validation failed.",
        details={"errors": serialize_validation_errors(exc)},
    )


async def api_error_exception_handler(
    request: Request,
    exc: ApiError,
) -> JSONResponse:
    """Render structured API exceptions with the public error envelope."""
    del request
    return error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        headers=exc.headers,
    )


async def policy_violation_exception_handler(
    request: Request,
    exc: PolicyViolation,
) -> JSONResponse:
    """Render policy failures with the public error envelope."""
    del request
    return error_response(
        status_code=status.HTTP_403_FORBIDDEN,
        code=exc.code,
        message=str(exc),
        details=exc.details,
    )
