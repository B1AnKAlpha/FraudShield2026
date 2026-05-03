from fastapi import APIRouter

from app.features.system.service import SystemService

router = APIRouter()
service = SystemService()


@router.get("/overview")
async def overview():
    return service.overview()
