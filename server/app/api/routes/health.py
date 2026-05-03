from datetime import datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@router.get("/ready")
async def ready():
    return {"status": "ready"}
