"""Shared HTTP error helpers and validation handlers."""

from __future__ import annotations

import json
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.interface.dto.errors import ErrorBody, ErrorEnvelope


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
) -> JSONResponse:
    """Build the stable JSON error envelope used by the API."""
    payload = ErrorEnvelope(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


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
