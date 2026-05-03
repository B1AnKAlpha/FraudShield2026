from fastapi import APIRouter

from app.features.detection.schemas import (
    DetectionRequest,
    DetectionResponse,
    UploadBatchRequest,
)
from app.features.detection.service import DetectionService

router = APIRouter()
service = DetectionService()


@router.post("/single", response_model=DetectionResponse)
async def detect_single(payload: DetectionRequest):
    return service.detect_single(payload)


@router.post("/batch")
async def detect_batch(payload: UploadBatchRequest):
    return service.detect_batch(payload)
