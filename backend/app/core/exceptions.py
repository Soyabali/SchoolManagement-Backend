import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")


class AppError(Exception):
    """Base for domain errors raised by services; mapped to a JSON error response."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"

    def __init__(self, message: str, *, details: object | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


def _error(status_code: int, code: str, message: str, details: object | None = None):
    body: dict[str, object] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details  # type: ignore[index]
    return JSONResponse(status_code=status_code, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, AuthenticationError) else None
        response = _error(exc.status_code, exc.code, exc.message, exc.details)
        if headers:
            response.headers.update(headers)
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        return _error(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        # Drop the submitted input from the response so passwords are never echoed back.
        details = [
            {"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "validation_error", "Invalid request", details
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error(_: Request, exc: IntegrityError):
        # Only the constraint name is exposed, never the offending values.
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        logger.warning("integrity error", extra={"constraint": constraint})
        return _error(
            status.HTTP_409_CONFLICT,
            "constraint_violation",
            "The request conflicts with existing data",
            {"constraint": constraint} if constraint else None,
        )

    @app.exception_handler(OperationalError)
    async def db_unavailable(_: Request, exc: OperationalError):
        logger.error("database unavailable", exc_info=exc)
        return _error(
            status.HTTP_503_SERVICE_UNAVAILABLE, "database_unavailable", "Database unavailable"
        )

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        logger.exception("unhandled error", exc_info=exc)
        return _error(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", "Internal server error"
        )
