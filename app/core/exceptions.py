"""Domain exceptions and a single place that turns them into human-readable errors."""
from __future__ import annotations


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: list[str] | None = None, hint: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []
        self.hint = hint


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_error"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class AuthRequired(AppError):
    status_code = 401
    code = "auth_required"


class TooManyAttempts(AppError):
    status_code = 429
    code = "too_many_attempts"


class PayloadTooLarge(AppError):
    status_code = 413
    code = "payload_too_large"


class ServiceUnavailable(AppError):
    status_code = 503
    code = "service_unavailable"
