from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.routes.auth import get_current_user
from app.features.params.schemas import (
    AdvancedModelParamsUpdateRequest,
    DynamicModelParamsUpdateRequest,
    FraudModelParamsUpdateRequest,
    ParamsOverviewResponse,
    SaveMessageResponse,
    UpdateCheckResponse,
)
from app.features.params.service import service

router = APIRouter()


@router.get("/overview", response_model=ParamsOverviewResponse)
async def overview(current_user=Depends(get_current_user)):
    return service.overview()


@router.put("/fraud-model", response_model=SaveMessageResponse)
async def save_fraud_model(payload: FraudModelParamsUpdateRequest, current_user=Depends(get_current_user)):
    return service.save_fraud_model(payload)


@router.put("/advanced-model", response_model=SaveMessageResponse)
async def save_advanced_model(payload: AdvancedModelParamsUpdateRequest, current_user=Depends(get_current_user)):
    return service.save_advanced_model(payload)


@router.put("/dynamic-model", response_model=SaveMessageResponse)
async def save_dynamic_model(payload: DynamicModelParamsUpdateRequest, current_user=Depends(get_current_user)):
    return service.save_dynamic_model(payload)


@router.post("/actions/software-update", response_model=UpdateCheckResponse)
async def update_software(current_user=Depends(get_current_user)):
    return service.update_software_version()


@router.post("/actions/model-update", response_model=UpdateCheckResponse)
async def update_model(current_user=Depends(get_current_user)):
    return service.update_model_version()


@router.post("/actions/parameter-update", response_model=UpdateCheckResponse)
async def update_parameter(current_user=Depends(get_current_user)):
    return service.update_parameter_version()
