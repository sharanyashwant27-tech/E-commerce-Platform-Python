"""Domain and application exceptions with HTTP mapping."""

from typing import Any, Optional


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str = "An error occurred",
        status_code: int = 400,
        code: str = "app_error",
        details: Optional[Any] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found", details: Any = None):
        super().__init__(message, 404, "not_found", details)


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Not authenticated", details: Any = None):
        super().__init__(message, 401, "unauthorized", details)


class ForbiddenError(AppException):
    def __init__(self, message: str = "Permission denied", details: Any = None):
        super().__init__(message, 403, "forbidden", details)


class ConflictError(AppException):
    def __init__(self, message: str = "Conflict", details: Any = None):
        super().__init__(message, 409, "conflict", details)


class ValidationError(AppException):
    def __init__(self, message: str = "Validation failed", details: Any = None):
        super().__init__(message, 422, "validation_error", details)


class PaymentError(AppException):
    def __init__(self, message: str = "Payment failed", details: Any = None):
        super().__init__(message, 402, "payment_error", details)


class InventoryError(AppException):
    def __init__(self, message: str = "Insufficient inventory", details: Any = None):
        super().__init__(message, 409, "inventory_error", details)
