"""Domain 422 error shape: summary message plus per-field details."""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel


class ValidationIssue(BaseModel):
    field: str
    message: str
    value: Any | None = None


def validation_http_exception(issues: list[ValidationIssue]) -> HTTPException:
    fields = ", ".join(dict.fromkeys(i.field for i in issues))
    return HTTPException(
        status_code=422,
        detail={
            "summary": f"Claim validation failed: {len(issues)} error(s) in fields {fields}",
            "errors": [i.model_dump() for i in issues],
        },
    )


def coverage_http_exception(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "summary": f"Coverage check failed: {exc}",
            "errors": [ValidationIssue(field="coverage", message=str(exc)).model_dump()],
        },
    )
