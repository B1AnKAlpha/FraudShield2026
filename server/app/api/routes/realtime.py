from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.features.realtime.schemas import RealtimeSummary
from app.features.realtime.service import service

router = APIRouter()


@router.get("/summary", response_model=RealtimeSummary)
async def summary():
    return service.summary()


@router.get("/stream")
async def stream():
    return StreamingResponse(service.stream(), media_type="text/event-stream")
