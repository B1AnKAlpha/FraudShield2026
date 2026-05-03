from fastapi import APIRouter, Depends

from app.api.routes.auth import get_current_user
from app.features.system.service import SystemService

router = APIRouter()
service = SystemService()


@router.get("/overview")
async def overview(current_user=Depends(get_current_user)):
    return service.overview()
