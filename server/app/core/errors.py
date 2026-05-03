from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse


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

    @app.exception_handler(Exception)
    async def handle_exception(_: Request, exc: Exception):
        return ORJSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": str(exc)}},
        )
