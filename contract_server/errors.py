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
