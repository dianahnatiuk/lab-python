"""Доменні помилки; перетворюються на HTTP-відповіді в main.py."""


class AppError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(AppError):
    status_code = 404


class AccessDeniedError(AppError):
    status_code = 403


class InvalidTransitionError(AppError):
    status_code = 409


class InvalidInputError(AppError):
    status_code = 422
