from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.routes.auth import get_current_user
from app.features.auth.service import AuthService
from app.features.realtime.schemas import RealtimeSummary
from app.features.realtime.service import service

router = APIRouter()
_auth_service = AuthService()


@router.get("/summary", response_model=RealtimeSummary)
async def summary(current_user=Depends(get_current_user)):
    return service.summary()


@router.get("/stream")
async def stream(token: str = Query(..., description="Bearer token for SSE auth")):
    _auth_service.get_user_by_token(token)
    return StreamingResponse(service.stream(), media_type="text/event-stream")
