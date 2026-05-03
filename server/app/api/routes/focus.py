from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.routes.auth import get_current_user
from app.features.focus.schemas import FocusMutationResponse, FocusOverviewResponse, FocusWatchRequest
from app.features.focus.service import service

router = APIRouter()


@router.get("/overview", response_model=FocusOverviewResponse)
async def get_focus_overview(
    job_id: str | None = Query(default=None),
    current_user=Depends(get_current_user),
):
    return service.get_overview(current_user=current_user, selected_job_id=job_id)


@router.post("/watch", response_model=FocusMutationResponse)
async def watch_account(payload: FocusWatchRequest, current_user=Depends(get_current_user)):
    return service.watch_account(current_user=current_user, payload=payload)


@router.delete("/watch/{account}", response_model=FocusMutationResponse)
async def unwatch_account(account: str, current_user=Depends(get_current_user)):
    return service.unwatch_account(current_user=current_user, account=account)


@router.delete("/logs/{job_id}", response_model=FocusMutationResponse)
async def hide_focus_log(job_id: str, current_user=Depends(get_current_user)):
    return service.hide_log(current_user=current_user, job_id=job_id)
