"""Standardised HTTP error response schemas for AIRIS.

These models document the error envelope returned by the exception handlers
registered in ``app/main.py``.  They are injected into the OpenAPI schema by
``app/core/openapi.py`` so that Swagger UI and ReDoc can render accurate type
information for all error status codes.

The models are intentionally lightweight — they exist for documentation, not
for constructing error responses in application code (handlers return plain
dicts for performance).
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HTTPErrorDetail(BaseModel):
    """
    Generic HTTP error response.

    Returned by the Starlette HTTPException handler for 400 / 401 / 403 / 404
    / 409 and most other 4xx responses.  The ``detail`` field carries either a
    plain string or a structured dict produced by the service layer.
    """

    detail: str | dict[str, Any] | list[Any] = Field(
        ...,
        description=(
            "Human-readable error detail. Plain string for simple errors; "
            "dict for structured domain errors (e.g. conflict codes)."
        ),
        examples=[
            "Invalid credentials.",
            {"error": "CLIENT_NAME_CONFLICT", "message": "A client with this name already exists."},
        ],
    )

    model_config = {
        "json_schema_extra": {
            "example": {"detail": "Not found."},
        }
    }


class ValidationErrorItem(BaseModel):
    """Single field-level validation error (Pydantic v2 format)."""

    loc: list[str | int] = Field(
        ...,
        description="Error location path — list of field names and/or array indices.",
        examples=[["body", "email"]],
    )
    msg: str = Field(..., description="Human-readable validation failure message.")
    type: str = Field(..., description="Pydantic v2 error type code (e.g. 'value_error', 'missing').")


class ValidationErrorResponse(BaseModel):
    """
    422 Unprocessable Entity response.

    Returned by the ``RequestValidationError`` handler when request body or
    query parameters fail Pydantic validation.
    """

    success: bool = Field(False, description="Always ``false`` for error responses.")
    error: str = Field("Validation Error", description="Error category label.")
    details: list[ValidationErrorItem] = Field(
        ..., description="One item per failing field."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": False,
                "error": "Validation Error",
                "details": [
                    {
                        "loc": ["body", "email"],
                        "msg": "value is not a valid email address",
                        "type": "value_error.email",
                    }
                ],
            }
        }
    }


class ServerErrorResponse(BaseModel):
    """
    500 Internal Server Error response.

    Returned by the global ``Exception`` handler for unhandled exceptions.
    The ``error`` field is a safe, truncated representation of the exception
    message (max 2 000 characters).
    """

    success: bool = Field(False, description="Always ``false`` for error responses.")
    detail: str = Field("Internal server error", description="Top-level error description.")
    error: str = Field(..., description="Truncated exception message (max 2 000 chars).")
    exception_type: str = Field(..., description="Python exception class name.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": False,
                "detail": "Internal server error",
                "error": "Unexpected condition encountered",
                "exception_type": "RuntimeError",
            }
        }
    }
