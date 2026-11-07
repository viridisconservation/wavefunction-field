# SPDX-License-Identifier: Apache-2.0
"""Fleet-harness error taxonomy (PROTOCOL §2.3)."""

from __future__ import annotations

from typing import Literal

ErrorType = Literal[
    "PermissionError",
    "ValidationError",
    "BudgetError",
    "ContextError",
    "BackendError",
    "RuntimeError",
]

HTTP_STATUS: dict[str, int] = {
    "ValidationError": 400,
    "PermissionError": 403,
    "ContextError": 409,
    "BudgetError": 429,
    "BackendError": 503,
    "RuntimeError": 500,
}


class WFPError(Exception):
    """A protocol error carrying the harness taxonomy envelope."""

    def __init__(
        self,
        error_type: ErrorType,
        message: str,
        *,
        field: str = "",
        constraint: str = "",
        extra: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type: ErrorType = error_type
        self.message = message
        self.field = field
        self.constraint = constraint
        self.extra = dict(extra or {})

    def envelope(self) -> dict[str, object]:
        out: dict[str, object] = {
            "error_type": self.error_type,
            "message": self.message,
        }
        if self.field:
            out["field"] = self.field
        if self.constraint:
            out["constraint"] = self.constraint
        out.update(self.extra)
        return out


def validation(message: str, field: str = "", constraint: str = "") -> WFPError:
    return WFPError("ValidationError", message, field=field, constraint=constraint)


def permission(message: str, field: str = "") -> WFPError:
    return WFPError("PermissionError", message, field=field)


def context(message: str, field: str = "") -> WFPError:
    return WFPError("ContextError", message, field=field)


def budget(message: str, constraint: str = "") -> WFPError:
    return WFPError("BudgetError", message, constraint=constraint)
