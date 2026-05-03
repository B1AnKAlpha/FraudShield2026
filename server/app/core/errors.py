import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "APP_ERROR"):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError):
        return ORJSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        messages = []
        for err in exc.errors():
            loc = " → ".join(str(part) for part in err.get("loc", []))
            messages.append(f"{loc}: {err.get('msg', '验证失败')}")
        return ORJSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "message": "；".join(messages)}},
        )

    @app.exception_handler(Exception)
    async def handle_exception(_: Request, exc: Exception):
        logger.exception("Unhandled exception: %s", exc)
        return ORJSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "服务内部异常，请稍后重试"}},
        )
