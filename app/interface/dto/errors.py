"""Shared API error DTOs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    """Error detail object for the public API error envelope."""

    code: str = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Human-readable summary of the failure.")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured metadata to help clients debug the error.",
    )


class ErrorEnvelope(BaseModel):
    """Standardized error envelope shared across HTTP endpoints."""

    error: ErrorBody = Field(description="Normalized error payload.")
