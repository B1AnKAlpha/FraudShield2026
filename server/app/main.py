from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.routes import analysis, auth, detection, focus, health, params, realtime, reports, system
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    yield


app = FastAPI(
    title="FraudShield 2026 API",
    version="0.1.0",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["实时分析"])
app.include_router(focus.router, prefix="/api/focus", tags=["重点监测"])
app.include_router(params.router, prefix="/api/params", tags=["参数调整"])
app.include_router(system.router, prefix="/api/system", tags=["系统"])
app.include_router(realtime.router, prefix="/api/realtime", tags=["实时流"])
app.include_router(detection.router, prefix="/api/detection", tags=["检测"])
app.include_router(reports.router, prefix="/api/reports", tags=["报告"])
