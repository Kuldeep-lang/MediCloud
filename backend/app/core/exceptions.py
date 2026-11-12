"""Domain exceptions raised by services and mapped to HTTP responses in main.py.

Services never import FastAPI; they raise these instead, which keeps business
logic independent of the web layer and easy to unit test.
"""


class AppError(Exception):
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class BusinessRuleError(AppError):
    status_code = 400


class PermissionDeniedError(AppError):
    status_code = 403
