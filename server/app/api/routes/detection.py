from fastapi import APIRouter, Depends

from app.api.routes.auth import get_current_user
from app.features.detection.schemas import (
    DetectionRequest,
    DetectionResponse,
    UploadBatchRequest,
)
from app.features.detection.service import DetectionService

router = APIRouter()
service = DetectionService()


@router.post("/single", response_model=DetectionResponse)
async def detect_single(payload: DetectionRequest, current_user=Depends(get_current_user)):
    return service.detect_single(payload)


@router.post("/batch")
async def detect_batch(payload: UploadBatchRequest, current_user=Depends(get_current_user)):
    return service.detect_batch(payload)
