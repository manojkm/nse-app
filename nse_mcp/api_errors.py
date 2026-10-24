"""Error types shared by the data sources."""

from __future__ import annotations


class APIError(Exception):
    """A failed upstream call, with a message that is safe to show users."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class DemoNotFound(APIError):
    def __init__(self, message: str):
        super().__init__(message, status=404)
