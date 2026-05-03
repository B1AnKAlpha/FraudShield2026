from fastapi import APIRouter, Depends

from app.api.routes.auth import get_current_user
from app.features.reports.schemas import ReportItem, ReportListResponse
from app.features.reports.service import ReportService

router = APIRouter()
service = ReportService()


@router.get("", response_model=ReportListResponse)
async def list_reports(current_user=Depends(get_current_user)):
    return service.list_reports()


@router.get("/{report_id}", response_model=ReportItem)
async def get_report(report_id: str, current_user=Depends(get_current_user)):
    return service.get_report(report_id)
