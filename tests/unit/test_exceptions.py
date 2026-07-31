from utils.exceptions import (
    AppException,
    ForbiddenError,
    InventoryError,
    NotFoundError,
    UnauthorizedError,
)


def test_exception_defaults():
    assert NotFoundError().status_code == 404
    assert UnauthorizedError().status_code == 401
    assert ForbiddenError().status_code == 403
    assert InventoryError().status_code == 409
    exc = AppException("x", 418, "teapot")
    assert exc.code == "teapot"
