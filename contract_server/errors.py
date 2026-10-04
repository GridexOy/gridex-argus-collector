"""The `Error` payload shared by every non-2xx response in the OpenAPI contract."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ApiError(Exception):
    """Raised inside a handler to short-circuit straight to an error response."""

    status: int
    code: str
    detail: str
    retryable: bool = False
    request_id: str = field(default="local")

    def body(self) -> dict[str, object]:
        return {
            "code": self.code,
            "detail": self.detail,
            "retryable": self.retryable,
            "request_id": self.request_id,
        }


def invalid(detail: str) -> ApiError:
    """400 invalid_input."""
    return ApiError(400, "invalid_input", detail)


def not_found(detail: str) -> ApiError:
    """404 for an unknown job/batch/worker/path (code invalid_input)."""
    return ApiError(404, "invalid_input", detail)


def conflict(code: str, detail: str) -> ApiError:
    """409 with the given code."""
    return ApiError(409, code, detail)


def unprocessable(code: str, detail: str) -> ApiError:
    """422 with the given code."""
    return ApiError(422, code, detail)
