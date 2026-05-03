from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.api.routes.auth import get_current_user
from app.features.analysis.schemas import (
    AnalysisJobCreateResponse,
    AnalysisJobDetailResponse,
    AnalysisJobListResponse,
    AnalysisReportResponse,
)
from app.features.analysis.service import service

router = APIRouter()


@router.post("/jobs", response_model=AnalysisJobCreateResponse)
async def create_analysis_job(
    text_payload: str = Form(default=""),
    files: list[UploadFile] = File(default=[]),
    current_user=Depends(get_current_user),
):
    return service.create_job(current_user=current_user, text_payload=text_payload, files=files)


@router.get("/jobs", response_model=AnalysisJobListResponse)
async def list_analysis_jobs(current_user=Depends(get_current_user)):
    return service.list_jobs(current_user)


@router.get("/jobs/{job_id}", response_model=AnalysisJobDetailResponse)
async def get_analysis_job(job_id: str, current_user=Depends(get_current_user)):
    return service.get_job(job_id, current_user)


@router.get("/jobs/{job_id}/report", response_model=AnalysisReportResponse)
async def get_analysis_report(job_id: str, current_user=Depends(get_current_user)):
    return service.get_report(job_id, current_user)


@router.get("/jobs/{job_id}/report.pdf")
async def get_analysis_report_pdf(job_id: str, current_user=Depends(get_current_user)):
    pdf_path = service.get_report_pdf_path(job_id, current_user)
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{job_id}.pdf",
        content_disposition_type="inline",
    )
